"""Data-provider protocol, normalization, and SEC EDGAR evidence providers."""

import hashlib
import json
import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from types import MappingProxyType
from typing import ClassVar, Protocol, runtime_checkable
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from fathomark_core.schemas import EvidenceItem, MetricObservation, ScopeSnapshot

from fathomark_providers.llm import ProviderError


@runtime_checkable
class EvidenceProvider(Protocol):
    name: str
    version: str

    def fetch(self, scope: ScopeSnapshot) -> "ProviderResult": ...


class EvidenceNormalizationError(ValueError):
    """Evidence returned by providers cannot be safely normalized."""


@dataclass(frozen=True)
class EvidenceNormalizationResult:
    """Canonical evidence and an audit-friendly count of excluded records."""

    evidence: tuple[EvidenceItem, ...]
    dropped_after_cutoff: int
    dropped_stale: int
    stale_evidence_ids: tuple[str, ...]
    dropped_duplicates: int
    canonical_id_by_input_id: Mapping[str, str]


@dataclass(frozen=True)
class ProviderResult:
    """Evidence and normalized metrics returned by one data provider."""

    evidence: tuple[EvidenceItem, ...]
    observations: tuple[MetricObservation, ...]


@dataclass(frozen=True)
class RawMetricObservation:
    """A provider metric before the host standardizes its unit and currency."""

    metric: str
    value: float
    unit: str
    basis: str
    data_date: date
    evidence_id: str
    currency: str | None = None
    formula: str | None = None


class MetricNormalizationError(ValueError):
    """A provider metric cannot be converted without guessing its meaning."""


class MetricNormalizer:
    """Normalize explicit currency and non-XBRL unit aliases.

    Currency values are scaled to base currency units but are never converted
    between currencies. An FX rate is an evidence-backed observation and must
    be supplied by a later, explicit conversion step rather than guessed here.
    """

    _UNIT_ALIASES: ClassVar[dict[str, tuple[str, float, str | None]]] = {
        "USD": ("USD", 1.0, "USD"),
        "USDm": ("USD", 1_000_000.0, "USD"),
        "USD million": ("USD", 1_000_000.0, "USD"),
        "USD millions": ("USD", 1_000_000.0, "USD"),
        "EUR": ("EUR", 1.0, "EUR"),
        "EURm": ("EUR", 1_000_000.0, "EUR"),
        "EUR million": ("EUR", 1_000_000.0, "EUR"),
        "EUR millions": ("EUR", 1_000_000.0, "EUR"),
        "GBP": ("GBP", 1.0, "GBP"),
        "GBPm": ("GBP", 1_000_000.0, "GBP"),
        "GBP million": ("GBP", 1_000_000.0, "GBP"),
        "GBP millions": ("GBP", 1_000_000.0, "GBP"),
        "JPY": ("JPY", 1.0, "JPY"),
        "JPYm": ("JPY", 1_000_000.0, "JPY"),
        "JPY million": ("JPY", 1_000_000.0, "JPY"),
        "JPY millions": ("JPY", 1_000_000.0, "JPY"),
        "CNY": ("CNY", 1.0, "CNY"),
        "CNYm": ("CNY", 1_000_000.0, "CNY"),
        "CNY million": ("CNY", 1_000_000.0, "CNY"),
        "CNY millions": ("CNY", 1_000_000.0, "CNY"),
        "HKD": ("HKD", 1.0, "HKD"),
        "HKDm": ("HKD", 1_000_000.0, "HKD"),
        "HKD million": ("HKD", 1_000_000.0, "HKD"),
        "HKD millions": ("HKD", 1_000_000.0, "HKD"),
        "shares": ("shares", 1.0, None),
        "shares_m": ("shares", 1_000_000.0, None),
        "million shares": ("shares", 1_000_000.0, None),
        "count": ("count", 1.0, None),
        "counts": ("count", 1.0, None),
        "units": ("count", 1.0, None),
        "%": ("percent", 1.0, None),
        "percent": ("percent", 1.0, None),
        "bps": ("bps", 1.0, None),
        "basis_points": ("bps", 1.0, None),
        "ratio": ("ratio", 1.0, None),
        "x": ("ratio", 1.0, None),
    }
    _BASES: ClassVar[frozenset[str]] = frozenset({"annual", "quarterly"})

    def normalize(self, raw: RawMetricObservation) -> MetricObservation:
        if raw.basis not in self._BASES:
            raise MetricNormalizationError(f"unsupported metric basis: {raw.basis}")
        if not math.isfinite(raw.value):
            raise MetricNormalizationError("metric value must be finite")
        if not isinstance(raw.data_date, date):
            raise MetricNormalizationError("metric data_date must be a date")
        alias = self._UNIT_ALIASES.get(raw.unit)
        if alias is None:
            raise MetricNormalizationError(f"unsupported metric unit: {raw.unit}")
        canonical_unit, multiplier, inferred_currency = alias
        if inferred_currency is None and raw.currency is not None:
            raise MetricNormalizationError(
                f"currency {raw.currency!r} conflicts with {raw.unit} unit"
            )
        if inferred_currency is not None and raw.currency not in (
            None,
            inferred_currency,
        ):
            raise MetricNormalizationError(
                f"currency {raw.currency!r} conflicts with {raw.unit} unit"
            )
        return MetricObservation(
            metric=raw.metric,
            value=raw.value * multiplier,
            unit=canonical_unit,
            currency=inferred_currency,
            basis=raw.basis,
            formula=raw.formula,
            data_date=raw.data_date,
            evidence_id=raw.evidence_id,
        )


class EvidenceNormalizer:
    """Apply the host-owned cutoff and duplicate rules to provider evidence.

    Providers may overlap, but they cannot silently redefine an existing
    evidence identifier. Identical content is represented once, preferring a
    higher-grade source and then the earliest published source deterministically.
    """

    _GRADE_RANK: ClassVar[dict[str, int]] = {"A": 0, "B": 1, "C": 2}

    def normalize(
        self,
        items: Iterable[EvidenceItem],
        *,
        data_cutoff: date,
        research_date: date | None = None,
        freshness: Mapping[str, Mapping[str, object]] | None = None,
    ) -> EvidenceNormalizationResult:
        by_content_hash: dict[str, EvidenceItem] = {}
        hashes_by_id: dict[str, str] = {}
        usable: list[EvidenceItem] = []
        dropped_after_cutoff = 0
        dropped_stale = 0
        stale_evidence_ids: set[str] = set()
        dropped_duplicates = 0

        for item in items:
            if item.published_date > data_cutoff:
                dropped_after_cutoff += 1
                continue
            max_age_days = self._max_age_days(item.source_class, freshness)
            if (
                research_date is not None
                and max_age_days is not None
                and (
                    item.published_date > research_date
                    or item.published_date
                    < research_date - timedelta(days=max_age_days)
                )
            ):
                dropped_stale += 1
                stale_evidence_ids.add(item.id)
                continue

            existing_hash = hashes_by_id.setdefault(item.id, item.content_hash)
            if existing_hash != item.content_hash:
                raise EvidenceNormalizationError(
                    f"evidence id {item.id!r} has conflicting content hashes"
                )
            usable.append(item)

            existing = by_content_hash.get(item.content_hash)
            if existing is None:
                by_content_hash[item.content_hash] = item
                continue

            dropped_duplicates += 1
            if self._preference_key(item) < self._preference_key(existing):
                by_content_hash[item.content_hash] = item

        return EvidenceNormalizationResult(
            evidence=tuple(sorted(by_content_hash.values(), key=lambda item: item.id)),
            dropped_after_cutoff=dropped_after_cutoff,
            dropped_stale=dropped_stale,
            stale_evidence_ids=tuple(sorted(stale_evidence_ids)),
            dropped_duplicates=dropped_duplicates,
            canonical_id_by_input_id=MappingProxyType(
                {item.id: by_content_hash[item.content_hash].id for item in usable}
            ),
        )

    def _max_age_days(
        self,
        source_class: str,
        freshness: Mapping[str, Mapping[str, object]] | None,
    ) -> int | None:
        if freshness is None:
            return None
        policy = freshness.get(source_class)
        if policy is None:
            return None
        max_age_days = policy.get("max_age_days")
        if not isinstance(max_age_days, int) or isinstance(max_age_days, bool):
            raise EvidenceNormalizationError(
                f"freshness policy for {source_class!r} has invalid max_age_days"
            )
        if max_age_days < 0:
            raise EvidenceNormalizationError(
                f"freshness policy for {source_class!r} has negative max_age_days"
            )
        return max_age_days

    def _preference_key(self, item: EvidenceItem) -> tuple:
        return (
            self._GRADE_RANK[item.grade],
            item.published_date,
            item.source_name,
            item.url or "",
            item.id,
        )


class FixtureEvidenceProvider:
    """Reads recorded evidence from a JSON dump. Offline; for CI and demos."""

    def __init__(
        self, dump_path: Path, *, name: str = "fixture-edgar", version: str = "1.0.0"
    ):
        self.name = name
        self.version = version
        self._dump_path = Path(dump_path)

    def fetch(self, scope: ScopeSnapshot) -> ProviderResult:
        raw = json.loads(self._dump_path.read_text(encoding="utf-8"))
        return ProviderResult(
            evidence=tuple(EvidenceItem.model_validate(e) for e in raw["evidence"]),
            observations=(),
        )


@dataclass(frozen=True)
class CompanyIRDocument:
    """Operator-supplied metadata for one public investor-relations document."""

    id: str
    source_name: str
    url: str
    published_date: date
    data_period_end: date | None = None
    grade: str = "A"


class CompanyIREvidenceProvider:
    """Fetch explicitly configured, allowlisted company IR documents.

    IR pages rarely expose a universal machine-readable date contract, so the
    host requires operators to provide document metadata rather than guessing
    dates from page prose. URLs and redirects are restricted to the configured
    HTTPS host allowlist to keep this provider from becoming an SSRF proxy.
    """

    name = "company-ir"
    version = "1.0.0"

    def __init__(
        self,
        *,
        documents_by_symbol: Mapping[str, Sequence[CompanyIRDocument]],
        user_agent: str,
        allowed_hosts: set[str] | frozenset[str],
        transport: "_SecTransport | None" = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        timeout_seconds: float = 15.0,
    ):
        if not user_agent.strip():
            raise ValueError("company IR user_agent must not be empty")
        self._allowed_hosts = frozenset(host.lower() for host in allowed_hosts)
        if not self._allowed_hosts:
            raise ValueError("company IR allowed_hosts must not be empty")
        self._documents = {
            symbol.upper(): tuple(documents)
            for symbol, documents in documents_by_symbol.items()
        }
        self._headers = {"User-Agent": user_agent, "Accept": "text/html"}
        self._transport = transport or _UrlLibSecTransport(
            timeout_seconds, allowed_hosts=self._allowed_hosts
        )
        self._now = now

    def fetch(self, scope: ScopeSnapshot) -> ProviderResult:
        documents = self._documents.get(scope.symbol.upper(), ())
        if not documents:
            raise ProviderError(
                f"no IR documents configured for symbol {scope.symbol}",
                retriable=False,
            )
        evidence: list[EvidenceItem] = []
        for document in documents:
            parsed = urlsplit(document.url)
            if parsed.scheme != "https" or parsed.hostname is None:
                raise ProviderError(
                    f"IR URL must use HTTPS: {document.url}", retriable=False
                )
            if parsed.hostname.lower() not in self._allowed_hosts:
                raise ProviderError(
                    f"IR URL host is not allowlisted: {parsed.hostname}",
                    retriable=False,
                )
            try:
                html = self._transport.get_text(document.url, headers=self._headers)
            except ProviderError:
                raise
            except (OSError, TypeError, ValueError) as exc:
                raise ProviderError(
                    f"company IR request failed: {exc}", retriable=True
                ) from exc
            parser = _HtmlTextExtractor()
            parser.feed(html)
            excerpt = parser.text()
            if not excerpt:
                raise ProviderError(
                    f"company IR document is empty: {document.id}", retriable=False
                )
            content_hash = (
                "sha256:" + hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
            )
            evidence.append(
                EvidenceItem(
                    id=document.id,
                    source_name=document.source_name,
                    source_class="ir",
                    url=document.url,
                    published_date=document.published_date,
                    data_period_end=document.data_period_end,
                    accessed_at=self._now(),
                    grade=document.grade,
                    content_hash=content_hash,
                    excerpt=excerpt[:4000],
                )
            )
        return ProviderResult(evidence=tuple(evidence), observations=())


class _SecTransport(Protocol):
    def get_json(self, url: str, *, headers: dict[str, str]) -> object: ...

    def get_text(self, url: str, *, headers: dict[str, str]) -> str: ...


class _AllowlistedRedirectHandler(HTTPRedirectHandler):
    def __init__(self, allowed_hosts: frozenset[str]):
        self._allowed_hosts = allowed_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname is None:
            raise ProviderError("redirected URL is not HTTPS", retriable=False)
        if parsed.hostname.lower() not in self._allowed_hosts:
            raise ProviderError(
                f"redirected URL host is not allowlisted: {parsed.hostname}",
                retriable=False,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _UrlLibSecTransport:
    def __init__(
        self, timeout_seconds: float, *, allowed_hosts: frozenset[str] | None = None
    ):
        self._timeout_seconds = timeout_seconds
        self._allowed_hosts = allowed_hosts

    def get_json(self, url: str, *, headers: dict[str, str]) -> object:
        return json.loads(self._get(url, headers=headers))

    def get_text(self, url: str, *, headers: dict[str, str]) -> str:
        return self._get(url, headers=headers)

    def _get(self, url: str, *, headers: dict[str, str]) -> str:
        request = Request(url, headers=headers)
        opener = (
            build_opener(_AllowlistedRedirectHandler(self._allowed_hosts))
            if self._allowed_hosts is not None
            else None
        )
        response_context = (
            opener.open(request, timeout=self._timeout_seconds)
            if opener is not None
            else urlopen(request, timeout=self._timeout_seconds)
        )
        with response_context as response:
            return response.read().decode("utf-8", errors="replace")


class _HtmlTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self._chunks).split())


class SecEdgarEvidenceProvider:
    """Fetch recent, cutoff-bounded 10-K/10-Q filing excerpts from SEC EDGAR.

    The public SEC endpoints need no API key, but calls require an identifiable
    ``user_agent``. All source URLs are constructed from SEC-provided filing
    metadata and fixed SEC hosts, so a filing cannot redirect this provider to
    an arbitrary network location.
    """

    name = "sec-edgar"
    version = "1.0.0"

    _TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
    _SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
    _COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    _ARCHIVES_URL = (
        "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
    )
    _FILING_FORMS = frozenset({"10-K", "10-Q"})
    _ACCESSION_RE = re.compile(r"\d{10}-\d{2}-\d{6}")
    _METRIC_TAGS = (
        (
            "revenue",
            (
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "SalesRevenueNet",
            ),
        ),
        ("net_income", ("NetIncomeLoss",)),
        (
            "operating_cash_flow",
            ("NetCashProvidedByUsedInOperatingActivities",),
        ),
    )

    def __init__(
        self,
        *,
        user_agent: str,
        transport: _SecTransport | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        max_filings: int = 6,
        timeout_seconds: float = 15.0,
    ):
        if not user_agent.strip():
            raise ValueError("SEC EDGAR user_agent must not be empty")
        if not 1 <= max_filings <= 8:
            raise ValueError("max_filings must be between 1 and 8")
        self._headers = {"User-Agent": user_agent, "Accept": "application/json"}
        self._transport = transport or _UrlLibSecTransport(timeout_seconds)
        self._now = now
        self._max_filings = max_filings

    def fetch(self, scope: ScopeSnapshot) -> ProviderResult:
        try:
            cik, company_name = self._resolve_ticker(scope.symbol)
            submissions = self._transport.get_json(
                self._SUBMISSIONS_URL.format(cik=cik), headers=self._headers
            )
            filings = self._recent_filings(submissions)
            evidence = self._filing_evidence(
                filings=filings,
                cik=cik,
                company_name=company_name,
                data_cutoff=scope.data_cutoff,
            )
            companyfacts = self._transport.get_json(
                self._COMPANYFACTS_URL.format(cik=cik), headers=self._headers
            )
            observations = self._companyfacts_observations(
                companyfacts, evidence=evidence, data_cutoff=scope.data_cutoff
            )
            return ProviderResult(
                evidence=tuple(evidence), observations=tuple(observations)
            )
        except ProviderError:
            raise
        except (KeyError, OSError, TypeError, ValueError) as exc:
            raise ProviderError(f"SEC EDGAR request or response failed: {exc}") from exc

    def _resolve_ticker(self, symbol: str) -> tuple[str, str]:
        payload = self._transport.get_json(self._TICKERS_URL, headers=self._headers)
        if not isinstance(payload, dict):
            raise ProviderError("SEC ticker response is not an object")
        fields = payload.get("fields")
        records = payload.get("data")
        if not isinstance(fields, list) or not isinstance(records, list):
            raise ProviderError("SEC ticker response has no fields/data arrays")
        try:
            ticker_index = fields.index("ticker")
            cik_index = fields.index("cik")
            name_index = fields.index("name")
        except ValueError as exc:
            raise ProviderError("SEC ticker response lacks a required column") from exc
        for record in records:
            if not isinstance(record, list) or len(record) <= max(
                ticker_index, cik_index, name_index
            ):
                continue
            if str(record[ticker_index]).upper() == symbol.upper():
                try:
                    return f"{int(record[cik_index]):010d}", str(record[name_index])
                except (TypeError, ValueError) as exc:
                    raise ProviderError(
                        "SEC ticker response has an invalid CIK"
                    ) from exc
        raise ProviderError(
            f"SEC EDGAR has no CIK for symbol {symbol}", retriable=False
        )

    def _recent_filings(self, submissions: object) -> dict[str, list[object]]:
        if not isinstance(submissions, dict):
            raise ProviderError("SEC submissions response is not an object")
        filings = submissions.get("filings")
        recent = filings.get("recent") if isinstance(filings, dict) else None
        if not isinstance(recent, dict):
            raise ProviderError("SEC submissions response has no recent filings")
        required = (
            "form",
            "filingDate",
            "reportDate",
            "accessionNumber",
            "primaryDocument",
        )
        if any(not isinstance(recent.get(name), list) for name in required):
            raise ProviderError("SEC recent filings are missing required columns")
        lengths = {len(recent[name]) for name in required}
        if len(lengths) != 1:
            raise ProviderError("SEC recent filing columns have inconsistent lengths")
        return {name: recent[name] for name in required}

    def _filing_evidence(
        self,
        *,
        filings: dict[str, list[object]],
        cik: str,
        company_name: str,
        data_cutoff: date,
    ) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for index, form in enumerate(filings["form"]):
            filing_date = date.fromisoformat(str(filings["filingDate"][index]))
            if filing_date > data_cutoff or form not in self._FILING_FORMS:
                continue
            accession = str(filings["accessionNumber"][index])
            document = str(filings["primaryDocument"][index])
            if not self._ACCESSION_RE.fullmatch(accession):
                raise ProviderError("SEC filing has an invalid accession number")
            if not document or document.startswith("/") or ".." in Path(document).parts:
                raise ProviderError("SEC filing has an unsafe primary document path")
            url = self._ARCHIVES_URL.format(
                cik=str(int(cik)),
                accession=accession.replace("-", ""),
                document=quote(document, safe="/"),
            )
            raw_document = self._transport.get_text(url, headers=self._headers)
            excerpt = _extract_html_text(raw_document)
            if not excerpt:
                raise ProviderError("SEC filing document has no readable text")
            report_date = str(filings["reportDate"][index]).strip()
            accessed_at = self._now()
            if accessed_at.tzinfo is None:
                accessed_at = accessed_at.replace(tzinfo=UTC)
            evidence.append(
                EvidenceItem(
                    id=f"sec:{cik}:{accession}",
                    source_name=f"{company_name} Form {form}",
                    source_class="filings",
                    url=url,
                    published_date=filing_date,
                    data_period_end=date.fromisoformat(report_date)
                    if report_date
                    else None,
                    accessed_at=accessed_at,
                    grade="A",
                    content_hash="sha256:"
                    + hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
                    excerpt=excerpt,
                )
            )
            if len(evidence) == self._max_filings:
                break
        return evidence

    def _companyfacts_observations(
        self,
        companyfacts: object,
        *,
        evidence: list[EvidenceItem],
        data_cutoff: date,
    ) -> list[MetricObservation]:
        if not isinstance(companyfacts, dict):
            raise ProviderError("SEC companyfacts response is not an object")
        facts = companyfacts.get("facts")
        us_gaap = facts.get("us-gaap") if isinstance(facts, dict) else None
        if not isinstance(us_gaap, dict):
            raise ProviderError("SEC companyfacts response has no us-gaap facts")
        evidence_by_accession = {
            item.id.rsplit(":", 1)[-1]: item.id for item in evidence
        }
        normalizer = MetricNormalizer()
        observations: list[MetricObservation] = []
        for metric, tags in self._METRIC_TAGS:
            selected_raws: list[RawMetricObservation] = []
            for tag in tags:
                tag_payload = us_gaap.get(tag)
                units = (
                    tag_payload.get("units") if isinstance(tag_payload, dict) else None
                )
                facts_in_usd = units.get("USD") if isinstance(units, dict) else None
                if not isinstance(facts_in_usd, list):
                    continue
                eligible: list[RawMetricObservation] = []
                for fact in facts_in_usd:
                    raw = self._raw_metric(
                        metric=metric,
                        tag=tag,
                        fact=fact,
                        evidence_by_accession=evidence_by_accession,
                        data_cutoff=data_cutoff,
                    )
                    if raw is not None:
                        eligible.append(raw)
                if eligible:
                    # Prefer the first tag with at least one usable fact. A
                    # lower-priority tag may coexist in companyfacts with a
                    # different accession or period and must not silently
                    # supplement the selected primary tag.
                    selected_raws = eligible
                    break
            seen: set[tuple[str, str, str, date]] = set()
            for raw in selected_raws:
                key = (raw.metric, raw.evidence_id, raw.basis, raw.data_date)
                if key in seen:
                    continue
                observations.append(normalizer.normalize(raw))
                seen.add(key)
        return observations

    def _raw_metric(
        self,
        *,
        metric: str,
        tag: str,
        fact: object,
        evidence_by_accession: dict[str, str],
        data_cutoff: date,
    ) -> RawMetricObservation | None:
        if not isinstance(fact, dict):
            return None
        form = str(fact.get("form", ""))
        accession = str(fact.get("accn", ""))
        evidence_id = evidence_by_accession.get(accession)
        if form not in self._FILING_FORMS or evidence_id is None:
            return None
        try:
            filed = date.fromisoformat(str(fact["filed"]))
            start = date.fromisoformat(str(fact["start"]))
            end = date.fromisoformat(str(fact["end"]))
            value = float(fact["val"])
        except (KeyError, TypeError, ValueError):
            return None
        if filed > data_cutoff or end > data_cutoff:
            return None
        duration_days = (end - start).days
        if form == "10-Q" and 80 <= duration_days <= 100:
            basis = "quarterly"
        elif form == "10-K" and 330 <= duration_days <= 380:
            basis = "annual"
        else:
            return None
        return RawMetricObservation(
            metric=metric,
            value=value,
            unit="USD",
            basis=basis,
            data_date=end,
            evidence_id=evidence_id,
            formula=f"SEC XBRL us-gaap:{tag}",
        )


def _extract_html_text(document: str) -> str:
    parser = _HtmlTextExtractor()
    parser.feed(document)
    parser.close()
    return parser.text()
