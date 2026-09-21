import hashlib
from datetime import UTC, date, datetime
from pathlib import Path

import fathomark_providers
import pytest
from fathomark_core.schemas import EvidenceItem, ScopeSnapshot
from fathomark_providers import (
    CompanyIRDocument,
    CompanyIREvidenceProvider,
    EvidenceNormalizationError,
    FixtureEvidenceProvider,
    MarketBar,
    MarketDataResult,
    ProviderError,
    StooqMarketDataProvider,
)

ROOT = Path(__file__).parents[3]

SCOPE = ScopeSnapshot(
    symbol="ADBE",
    exchange="NASDAQ",
    research_role="core",
    horizon="5-10y",
    research_date=date(2026, 9, 3),
    data_cutoff=date(2026, 9, 3),
    framework_ref="common-stock@1.0.0",
)


def test_fixture_provider_returns_typed_evidence():
    provider = FixtureEvidenceProvider(
        ROOT / "examples" / "fixtures" / "adbe_2026-09-03" / "provider_dump.json"
    )
    result = provider.fetch(SCOPE)
    assert isinstance(result, fathomark_providers.ProviderResult)
    assert {e.id for e in result.evidence} == {"ev_001", "ev_002"}
    assert all(e.excerpt for e in result.evidence)  # dump carries excerpts
    assert result.observations == ()
    assert provider.name == "fixture-edgar"


def _evidence(
    evidence_id: str,
    *,
    content_hash: str,
    published_date: date,
    grade: str = "B",
) -> EvidenceItem:
    return EvidenceItem(
        id=evidence_id,
        source_name=f"Source {evidence_id}",
        source_class="filings",
        url=f"https://example.test/{evidence_id}",
        published_date=published_date,
        data_period_end=None,
        accessed_at=datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
        grade=grade,
        content_hash=content_hash,
        excerpt="Recorded evidence.",
    )


def test_evidence_normalizer_filters_cutoff_and_keeps_best_duplicate():
    normalizer_type = getattr(fathomark_providers, "EvidenceNormalizer", None)
    assert normalizer_type is not None

    result = normalizer_type().normalize(
        [
            _evidence(
                "after_cutoff",
                content_hash="sha256:after",
                published_date=date(2026, 9, 4),
            ),
            _evidence(
                "duplicate_b",
                content_hash="sha256:duplicate",
                published_date=date(2026, 9, 2),
                grade="B",
            ),
            _evidence(
                "duplicate_a",
                content_hash="sha256:duplicate",
                published_date=date(2026, 9, 1),
                grade="A",
            ),
            _evidence(
                "unique",
                content_hash="sha256:unique",
                published_date=date(2026, 9, 3),
            ),
        ],
        data_cutoff=date(2026, 9, 3),
    )

    assert [item.id for item in result.evidence] == ["duplicate_a", "unique"]
    assert result.dropped_after_cutoff == 1
    assert result.dropped_duplicates == 1
    assert result.canonical_id_by_input_id == {
        "duplicate_b": "duplicate_a",
        "duplicate_a": "duplicate_a",
        "unique": "unique",
    }


def test_evidence_normalizer_rejects_one_id_with_conflicting_content():
    with pytest.raises(EvidenceNormalizationError, match="conflicting content"):
        fathomark_providers.EvidenceNormalizer().normalize(
            [
                _evidence(
                    "ev_conflict",
                    content_hash="sha256:first",
                    published_date=date(2026, 9, 1),
                ),
                _evidence(
                    "ev_conflict",
                    content_hash="sha256:second",
                    published_date=date(2026, 9, 2),
                ),
            ],
            data_cutoff=date(2026, 9, 3),
        )


def test_evidence_normalizer_drops_stale_and_future_items_when_policy_is_given():
    result = fathomark_providers.EvidenceNormalizer().normalize(
        [
            _evidence(
                "stale",
                content_hash="sha256:stale",
                published_date=date(2025, 1, 1),
            ),
            _evidence(
                "future",
                content_hash="sha256:future",
                published_date=date(2026, 9, 4),
            ),
            _evidence(
                "fresh",
                content_hash="sha256:fresh",
                published_date=date(2026, 8, 1),
            ),
        ],
        data_cutoff=date(2026, 9, 10),
        research_date=date(2026, 9, 3),
        freshness={"filings": {"max_age_days": 130}},
    )

    assert [item.id for item in result.evidence] == ["fresh"]
    assert result.dropped_after_cutoff == 0
    assert result.dropped_stale == 2
    assert result.stale_evidence_ids == ("future", "stale")


def test_evidence_normalizer_keeps_source_class_without_policy():
    item = _evidence(
        "other",
        content_hash="sha256:other",
        published_date=date(2020, 1, 1),
    ).model_copy(update={"source_class": "other"})

    result = fathomark_providers.EvidenceNormalizer().normalize(
        [item],
        data_cutoff=date(2026, 9, 3),
        research_date=date(2026, 9, 3),
        freshness={"filings": {"max_age_days": 130}},
    )

    assert [e.id for e in result.evidence] == ["other"]
    assert result.dropped_stale == 0


def test_metric_normalizer_converts_usd_millions_to_canonical_observation():
    raw_type = getattr(fathomark_providers, "RawMetricObservation", None)
    normalizer_type = getattr(fathomark_providers, "MetricNormalizer", None)
    result_type = getattr(fathomark_providers, "ProviderResult", None)
    assert raw_type is not None
    assert normalizer_type is not None
    assert result_type is not None

    raw = raw_type(
        metric="revenue",
        value=5.87,
        unit="USDm",
        basis="quarterly",
        data_date=date(2026, 5, 29),
        evidence_id="ev_001",
    )
    observation = normalizer_type().normalize(raw)
    result = result_type(evidence=(), observations=(observation,))

    assert observation.metric == "revenue"
    assert observation.value == 5_870_000
    assert observation.unit == "USD"
    assert observation.currency == "USD"
    assert observation.basis == "quarterly"
    assert result.observations == (observation,)


def test_company_ir_provider_fetches_allowlisted_document_as_traceable_evidence():
    url = "https://investors.adobe.com/news/2026-update.html"
    transport = _RecordedSecTransport(
        {}, {url: "<html><body><h1>Adobe update</h1><p>Revenue grew.</p></body></html>"}
    )
    document = CompanyIRDocument(
        id="ir:adbe:2026-update",
        source_name="Adobe Investor Relations",
        url=url,
        published_date=date(2026, 8, 20),
        data_period_end=date(2026, 7, 31),
    )
    provider = CompanyIREvidenceProvider(
        documents_by_symbol={"ADBE": (document,)},
        user_agent="Fathomark research@example.com",
        allowed_hosts={"investors.adobe.com"},
        transport=transport,
        now=lambda: datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
    )

    result = provider.fetch(SCOPE)

    assert provider.name == "company-ir"
    assert result.observations == ()
    assert result.evidence[0].source_class == "ir"
    assert result.evidence[0].excerpt == "Adobe update Revenue grew."
    assert result.evidence[0].data_period_end == date(2026, 7, 31)
    assert result.evidence[0].accessed_at == datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
    assert transport.text_calls == [
        (
            url,
            {
                "User-Agent": "Fathomark research@example.com",
                "Accept": "text/html",
            },
        )
    ]


def test_company_ir_provider_rejects_unallowlisted_or_missing_documents():
    unsafe = CompanyIRDocument(
        id="ir:unsafe",
        source_name="Untrusted",
        url="https://evil.example/exfiltrate",
        published_date=date(2026, 8, 20),
    )
    provider = CompanyIREvidenceProvider(
        documents_by_symbol={"ADBE": (unsafe,)},
        user_agent="Fathomark research@example.com",
        allowed_hosts={"investors.adobe.com"},
        transport=_RecordedSecTransport({}, {}),
    )
    with pytest.raises(ProviderError, match="allowlisted"):
        provider.fetch(SCOPE)

    empty = CompanyIREvidenceProvider(
        documents_by_symbol={},
        user_agent="Fathomark research@example.com",
        allowed_hosts={"investors.adobe.com"},
        transport=_RecordedSecTransport({}, {}),
    )
    with pytest.raises(ProviderError, match="no IR documents"):
        empty.fetch(SCOPE)


def test_stooq_market_provider_parses_cutoff_bounded_ohlcv_csv():
    url = "https://stooq.com/q/d/l/?s=adbe.us&i=d"
    transport = _RecordedSecTransport(
        {},
        {
            url: "Date,Open,High,Low,Close,Volume\n"
            "2026-09-04,350,360,345,355,1200\n"
            "2026-09-03,340,350,335,348,1100\n"
            "2026-09-02,330,345,325,340,1000\n"
        },
    )
    provider = StooqMarketDataProvider(
        user_agent="Fathomark research@example.com",
        transport=transport,
        now=lambda: datetime(2026, 9, 5, 12, 0, tzinfo=UTC),
    )

    result = provider.fetch(SCOPE)

    assert isinstance(result, MarketDataResult)
    assert provider.name == "stooq"
    assert result.symbol == "ADBE"
    assert [bar.trading_date for bar in result.bars] == [
        date(2026, 9, 2),
        date(2026, 9, 3),
    ]
    assert result.bars[-1] == MarketBar(
        symbol="ADBE",
        trading_date=date(2026, 9, 3),
        open=340.0,
        high=350.0,
        low=335.0,
        close=348.0,
        volume=1100.0,
    )
    assert result.source_url == url
    assert result.content_hash.startswith("sha256:")
    assert result.accessed_at == datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
    assert transport.text_calls[0][1] == {
        "User-Agent": "Fathomark research@example.com",
        "Accept": "text/csv",
    }


def test_stooq_market_provider_rejects_invalid_rows_and_symbol_injection():
    url = "https://stooq.com/q/d/l/?s=adbe.us&i=d"
    transport = _RecordedSecTransport(
        {},
        {url: "Date,Open,High,Low,Close,Volume\n2026-09-03,340,330,335,348,1100\n"},
    )
    provider = StooqMarketDataProvider(
        user_agent="Fathomark research@example.com", transport=transport
    )

    with pytest.raises(ProviderError, match="invalid OHLC relationship"):
        provider.fetch(SCOPE)

    with pytest.raises(ProviderError, match="unsupported market symbol"):
        provider.fetch(SCOPE.model_copy(update={"symbol": "ADBE/../../etc"}))


def test_stooq_market_provider_rejects_duplicate_trading_dates():
    url = "https://stooq.com/q/d/l/?s=adbe.us&i=d"
    row = "2026-09-03,340,350,335,348,1100"
    transport = _RecordedSecTransport(
        {}, {url: f"Date,Open,High,Low,Close,Volume\n{row}\n{row}\n"}
    )
    provider = StooqMarketDataProvider(
        user_agent="Fathomark research@example.com", transport=transport
    )

    with pytest.raises(ProviderError, match="duplicate date"):
        provider.fetch(SCOPE)


class _RecordedSecTransport:
    def __init__(self, json_responses, text_responses):
        self._json_responses = json_responses
        self._text_responses = text_responses
        self.json_calls = []
        self.text_calls = []

    def get_json(self, url, *, headers):
        self.json_calls.append((url, headers))
        return self._json_responses[url]

    def get_text(self, url, *, headers):
        self.text_calls.append((url, headers))
        return self._text_responses[url]


def test_sec_edgar_provider_builds_cutoff_bounded_filing_evidence_and_metrics():
    provider_type = getattr(fathomark_providers, "SecEdgarEvidenceProvider", None)
    assert provider_type is not None

    ticker_url = "https://www.sec.gov/files/company_tickers_exchange.json"
    submissions_url = "https://data.sec.gov/submissions/CIK0000796343.json"
    companyfacts_url = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000796343.json"
    filing_url = (
        "https://www.sec.gov/Archives/edgar/data/796343/"
        "000079634326000109/adbe-20260529.htm"
    )
    transport = _RecordedSecTransport(
        {
            ticker_url: {
                "fields": ["cik", "name", "ticker", "exchange"],
                "data": [[796343, "Adobe Inc.", "ADBE", "Nasdaq"]],
            },
            submissions_url: {
                "filings": {
                    "recent": {
                        "form": ["10-Q", "8-K"],
                        "filingDate": ["2026-06-15", "2026-09-04"],
                        "reportDate": ["2026-05-29", "2026-09-03"],
                        "accessionNumber": [
                            "0000796343-26-000109",
                            "0000796343-26-000120",
                        ],
                        "primaryDocument": ["adbe-20260529.htm", "adbe-8k.htm"],
                    }
                }
            },
            companyfacts_url: {
                "facts": {
                    "us-gaap": {
                        "RevenueFromContractWithCustomerExcludingAssessedTax": {
                            "units": {
                                "USD": [
                                    {
                                        "form": "10-Q",
                                        "filed": "2026-06-15",
                                        "start": "2025-11-30",
                                        "end": "2026-05-29",
                                        "accn": "0000796343-26-000109",
                                        "val": 10_000_000_000,
                                    },
                                    {
                                        "form": "10-Q",
                                        "filed": "2026-06-15",
                                        "start": "2026-02-28",
                                        "end": "2026-05-29",
                                        "accn": "0000796343-26-000109",
                                        "val": 5_870_000_000,
                                    },
                                ]
                            }
                        },
                        "SalesRevenueNet": {
                            "units": {
                                "USD": [
                                    {
                                        "form": "10-Q",
                                        "filed": "2026-06-15",
                                        "start": "2026-02-28",
                                        "end": "2026-05-29",
                                        "accn": "0000796343-26-000109",
                                        "val": 5_800_000_000,
                                    }
                                ]
                            }
                        },
                        "NetIncomeLoss": {
                            "units": {
                                "USD": [
                                    {
                                        "form": "10-Q",
                                        "filed": "2026-06-15",
                                        "start": "2026-02-28",
                                        "end": "2026-05-29",
                                        "accn": "0000796343-26-000109",
                                        "val": 1_600_000_000,
                                    }
                                ]
                            }
                        },
                        "NetCashProvidedByUsedInOperatingActivities": {
                            "units": {
                                "USD": [
                                    {
                                        "form": "10-Q",
                                        "filed": "2026-06-15",
                                        "start": "2026-02-28",
                                        "end": "2026-05-29",
                                        "accn": "0000796343-26-000109",
                                        "val": 2_150_000_000,
                                    }
                                ]
                            }
                        },
                    }
                }
            },
        },
        {filing_url: "<html><body><p>Revenue grew by 11%.</p></body></html>"},
    )
    provider = provider_type(
        user_agent="Fathomark research@example.com",
        transport=transport,
        now=lambda: datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
    )

    result = provider.fetch(SCOPE)
    assert isinstance(result, fathomark_providers.ProviderResult)

    assert len(result.evidence) == 1
    item = result.evidence[0]
    assert item.id == "sec:0000796343:0000796343-26-000109"
    assert item.source_name == "Adobe Inc. Form 10-Q"
    assert item.source_class == "filings"
    assert item.url == filing_url
    assert item.published_date == date(2026, 6, 15)
    assert item.data_period_end == date(2026, 5, 29)
    assert item.accessed_at == datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
    assert item.grade == "A"
    assert item.excerpt == "Revenue grew by 11%."
    assert (
        item.content_hash
        == "sha256:" + hashlib.sha256(b"Revenue grew by 11%.").hexdigest()
    )
    assert [
        (
            observation.metric,
            observation.value,
            observation.basis,
            observation.data_date,
            observation.evidence_id,
        )
        for observation in result.observations
    ] == [
        (
            "revenue",
            5_870_000_000,
            "quarterly",
            date(2026, 5, 29),
            "sec:0000796343:0000796343-26-000109",
        ),
        (
            "net_income",
            1_600_000_000,
            "quarterly",
            date(2026, 5, 29),
            "sec:0000796343:0000796343-26-000109",
        ),
        (
            "operating_cash_flow",
            2_150_000_000,
            "quarterly",
            date(2026, 5, 29),
            "sec:0000796343:0000796343-26-000109",
        ),
    ]
    assert [url for url, _ in transport.json_calls] == [
        ticker_url,
        submissions_url,
        companyfacts_url,
    ]
    assert [url for url, _ in transport.text_calls] == [filing_url]
    assert all(
        headers["User-Agent"] == "Fathomark research@example.com"
        for _, headers in [*transport.json_calls, *transport.text_calls]
    )
