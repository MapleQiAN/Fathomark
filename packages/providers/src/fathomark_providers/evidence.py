"""Data-provider protocol, normalization, and SEC EDGAR evidence providers."""

import hashlib
import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import ClassVar, Protocol, runtime_checkable
from urllib.parse import quote
from urllib.request import Request, urlopen

from fathomark_core.schemas import EvidenceItem, ScopeSnapshot

from fathomark_providers.llm import ProviderError


@runtime_checkable
class EvidenceProvider(Protocol):
    name: str
    version: str

    def fetch(self, scope: ScopeSnapshot) -> list[EvidenceItem]: ...


class EvidenceNormalizationError(ValueError):
    """Evidence returned by providers cannot be safely normalized."""


@dataclass(frozen=True)
class EvidenceNormalizationResult:
    """Canonical evidence and an audit-friendly count of excluded records."""

    evidence: tuple[EvidenceItem, ...]
    dropped_after_cutoff: int
    dropped_duplicates: int


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
    ) -> EvidenceNormalizationResult:
        by_content_hash: dict[str, EvidenceItem] = {}
        hashes_by_id: dict[str, str] = {}
        dropped_after_cutoff = 0
        dropped_duplicates = 0

        for item in items:
            if item.published_date > data_cutoff:
                dropped_after_cutoff += 1
                continue

            existing_hash = hashes_by_id.setdefault(item.id, item.content_hash)
            if existing_hash != item.content_hash:
                raise EvidenceNormalizationError(
                    f"evidence id {item.id!r} has conflicting content hashes"
                )

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
            dropped_duplicates=dropped_duplicates,
        )

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

    def fetch(self, scope: ScopeSnapshot) -> list[EvidenceItem]:
        raw = json.loads(self._dump_path.read_text(encoding="utf-8"))
        return [EvidenceItem.model_validate(e) for e in raw["evidence"]]


class _SecTransport(Protocol):
    def get_json(self, url: str, *, headers: dict[str, str]) -> object: ...

    def get_text(self, url: str, *, headers: dict[str, str]) -> str: ...


class _UrlLibSecTransport:
    def __init__(self, timeout_seconds: float):
        self._timeout_seconds = timeout_seconds

    def get_json(self, url: str, *, headers: dict[str, str]) -> object:
        return json.loads(self._get(url, headers=headers))

    def get_text(self, url: str, *, headers: dict[str, str]) -> str:
        return self._get(url, headers=headers)

    def _get(self, url: str, *, headers: dict[str, str]) -> str:
        request = Request(url, headers=headers)
        with urlopen(request, timeout=self._timeout_seconds) as response:
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
    _ARCHIVES_URL = (
        "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
    )
    _FILING_FORMS = frozenset({"10-K", "10-Q"})
    _ACCESSION_RE = re.compile(r"\d{10}-\d{2}-\d{6}")

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

    def fetch(self, scope: ScopeSnapshot) -> list[EvidenceItem]:
        try:
            cik, company_name = self._resolve_ticker(scope.symbol)
            submissions = self._transport.get_json(
                self._SUBMISSIONS_URL.format(cik=cik), headers=self._headers
            )
            filings = self._recent_filings(submissions)
            return self._filing_evidence(
                filings=filings,
                cik=cik,
                company_name=company_name,
                data_cutoff=scope.data_cutoff,
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


def _extract_html_text(document: str) -> str:
    parser = _HtmlTextExtractor()
    parser.feed(document)
    parser.close()
    return parser.text()
