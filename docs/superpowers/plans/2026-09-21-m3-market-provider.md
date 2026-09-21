# M3 Market Data Provider Implementation Plan

**Goal:** Add a replaceable public daily-market-data adapter without making
live network access a CI requirement.

- [x] Add failing tests for cutoff-bounded OHLCV parsing, trace metadata,
  malformed rows, duplicate rows and symbol validation.
- [x] Implement `MarketDataProvider`, validated `MarketBar`/
  `MarketDataResult`, and the allowlisted `StooqMarketDataProvider`.
- [x] Export the protocol and adapter and document the operator-owned
  licensing/rate-limit boundary.

Validation: provider contract tests, full offline test suite, Ruff and
`git diff --check` pass. Live Stooq availability and redistribution terms are
not verified by CI.
