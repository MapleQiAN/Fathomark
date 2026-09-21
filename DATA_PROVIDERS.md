# Data provider and redistribution policy

Fathomark separates provider retrieval from the host-owned evidence contract.
Every persisted item needs a stable ID, source class/name, publication date,
content hash, provenance and a cutoff-compatible date. Providers must not
silently rewrite conflicting IDs or turn missing data into estimates.

## Allowed repository content

- Small, synthetic or public-domain examples needed for tests.
- Recorded responses that are licensed for redistribution and contain no
  credentials, personal data, or paid-only material.
- The included ADBE fixture, which is historical test material and is not a
  current market-data feed.

## Operator responsibilities

Before enabling a provider, verify its terms for retrieval, caching,
redistribution, attribution, rate limits and commercial use. Keep paid or
restricted responses outside the repository; store only an approved hash,
metadata, or redacted cassette when that is permitted. Preserve source URLs,
dates and license notices in generated reports.

The host owns cutoff, freshness, duplicate, unit and currency normalization.
Provider code may collect and parse data, but it may not change framework
weights, publish an approved version, or write the core database directly.

## Company IR adapter

`CompanyIREvidenceProvider` accepts an operator-maintained document manifest for
each symbol. The manifest supplies the publication date and period metadata;
the adapter does not guess dates from page prose. Every URL must be HTTPS and
its hostname must be in the explicit allowlist; redirects are checked against
the same allowlist. Keep the manifest small, bounded, and reviewed, and use an
identifiable `User-Agent` as required by the source.

## Market data adapter

`MarketDataProvider` returns validated daily OHLCV bars and preserves the
source URL, access time and raw-response hash. The included
`StooqMarketDataProvider` is a replaceable public-data adapter for US symbols;
it applies the research cutoff while parsing, rejects malformed or duplicate
rows, and restricts redirects to `stooq.com`. Inject a recorded transport for
CI and tests. Stooq availability, rate limits, licensing and redistribution
terms remain operator responsibilities; no live market call is required by CI.
