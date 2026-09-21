"""Replaceable public-market-data provider contracts and adapters."""

import csv
import hashlib
import io
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol, runtime_checkable
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from fathomark_core.schemas import ScopeSnapshot

from fathomark_providers.llm import ProviderError


@dataclass(frozen=True, slots=True)
class MarketBar:
    """One validated daily OHLCV observation."""

    symbol: str
    trading_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("market bar symbol must not be empty")
        values = (self.open, self.high, self.low, self.close, self.volume)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("market bar values must be finite")
        if any(value < 0 for value in values):
            raise ValueError("market bar values must not be negative")
        if self.high < max(self.open, self.close) or self.low > min(
            self.open, self.close
        ):
            raise ValueError("invalid OHLC relationship")
        if self.low > self.high:
            raise ValueError("invalid OHLC relationship")


@dataclass(frozen=True, slots=True)
class MarketDataResult:
    """Traceable market bars returned by a provider."""

    symbol: str
    bars: tuple[MarketBar, ...]
    source_url: str
    accessed_at: datetime
    content_hash: str

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("market result symbol must not be empty")
        if any(bar.symbol != self.symbol for bar in self.bars):
            raise ValueError("market bars must use the result symbol")
        if any(
            first.trading_date >= second.trading_date
            for first, second in zip(self.bars, self.bars[1:])
        ):
            raise ValueError("market bars must be sorted and unique by date")
        if not self.content_hash.startswith("sha256:"):
            raise ValueError("market result content_hash must be sha256-prefixed")


@runtime_checkable
class MarketDataProvider(Protocol):
    """Provider protocol for cutoff-bounded daily market data."""

    name: str
    version: str

    def fetch(self, scope: ScopeSnapshot) -> MarketDataResult: ...


class _MarketTextTransport(Protocol):
    def get_text(self, url: str, *, headers: dict[str, str]) -> str: ...


class _AllowlistedRedirectHandler(HTTPRedirectHandler):
    def __init__(self, allowed_hosts: frozenset[str]):
        self._allowed_hosts = allowed_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname is None:
            raise ProviderError("redirected market URL is not HTTPS", retriable=False)
        if parsed.hostname.lower() not in self._allowed_hosts:
            raise ProviderError(
                f"redirected market URL host is not allowlisted: {parsed.hostname}",
                retriable=False,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _UrlLibMarketTransport:
    def __init__(self, timeout_seconds: float, *, allowed_hosts: frozenset[str]):
        self._timeout_seconds = timeout_seconds
        self._allowed_hosts = allowed_hosts

    def get_text(self, url: str, *, headers: dict[str, str]) -> str:
        request = Request(url, headers=headers)
        opener = build_opener(_AllowlistedRedirectHandler(self._allowed_hosts))
        with opener.open(request, timeout=self._timeout_seconds) as response:
            return response.read().decode("utf-8", errors="replace")


class StooqMarketDataProvider:
    """Fetch daily US-equity OHLCV CSV from the public Stooq endpoint.

    This adapter intentionally owns only URL construction and parsing. The
    orchestrator still owns cutoff/freshness policy, and callers may inject a
    transport for recordings or another implementation for a different feed.
    """

    name = "stooq"
    version = "1.0.0"
    _BASE_URL = "https://stooq.com/q/d/l/"
    _ALLOWED_HOSTS = frozenset({"stooq.com"})
    _SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,15}$")
    _REQUIRED_COLUMNS = frozenset({"date", "open", "high", "low", "close", "volume"})

    def __init__(
        self,
        *,
        user_agent: str,
        transport: _MarketTextTransport | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        timeout_seconds: float = 15.0,
        max_bars: int = 10_000,
    ):
        if not user_agent.strip():
            raise ValueError("market user_agent must not be empty")
        if max_bars < 1:
            raise ValueError("market max_bars must be positive")
        self._headers = {"User-Agent": user_agent, "Accept": "text/csv"}
        self._transport = transport or _UrlLibMarketTransport(
            timeout_seconds, allowed_hosts=self._ALLOWED_HOSTS
        )
        self._now = now
        self._max_bars = max_bars

    def fetch(self, scope: ScopeSnapshot) -> MarketDataResult:
        symbol = scope.symbol.strip().upper()
        if not self._SYMBOL_RE.fullmatch(symbol):
            raise ProviderError(
                f"unsupported market symbol: {scope.symbol}", retriable=False
            )
        url = f"{self._BASE_URL}?s={symbol.lower()}.us&i=d"
        try:
            raw_csv = self._transport.get_text(url, headers=self._headers)
        except ProviderError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise ProviderError(
                f"Stooq market request failed: {exc}", retriable=True
            ) from exc
        bars = self._parse_csv(raw_csv, symbol=symbol, data_cutoff=scope.data_cutoff)
        accessed_at = self._now()
        if accessed_at.tzinfo is None:
            accessed_at = accessed_at.replace(tzinfo=UTC)
        return MarketDataResult(
            symbol=symbol,
            bars=tuple(bars),
            source_url=url,
            accessed_at=accessed_at,
            content_hash="sha256:"
            + hashlib.sha256(raw_csv.encode("utf-8")).hexdigest(),
        )

    def _parse_csv(
        self, raw_csv: str, *, symbol: str, data_cutoff: date
    ) -> list[MarketBar]:
        try:
            reader = csv.DictReader(io.StringIO(raw_csv))
            fieldnames = {
                str(field).strip().lower() for field in (reader.fieldnames or ())
            }
            if not self._REQUIRED_COLUMNS.issubset(fieldnames):
                raise ProviderError(
                    "Stooq response is missing OHLCV columns", retriable=False
                )
            bars: list[MarketBar] = []
            seen_dates: set[date] = set()
            for row in reader:
                if not any(str(value or "").strip() for value in row.values()):
                    continue
                normalized = {
                    str(key).strip().lower(): str(value or "").strip()
                    for key, value in row.items()
                }
                try:
                    trading_date = date.fromisoformat(normalized["date"])
                    if trading_date > data_cutoff:
                        continue
                    numbers = {
                        key: float(normalized[key])
                        for key in ("open", "high", "low", "close", "volume")
                    }
                    bar = MarketBar(symbol=symbol, trading_date=trading_date, **numbers)
                except (KeyError, TypeError, ValueError) as exc:
                    raise ProviderError(
                        f"Stooq response has an invalid row ({exc}): {normalized}",
                        retriable=False,
                    ) from exc
                if trading_date in seen_dates:
                    raise ProviderError(
                        f"Stooq response has duplicate date: {trading_date}",
                        retriable=False,
                    )
                seen_dates.add(trading_date)
                bars.append(bar)
                if len(bars) > self._max_bars:
                    raise ProviderError(
                        "Stooq response exceeds max_bars", retriable=False
                    )
            if not bars:
                raise ProviderError(
                    "Stooq response has no bars through data cutoff", retriable=False
                )
            return sorted(bars, key=lambda bar: bar.trading_date)
        except csv.Error as exc:
            raise ProviderError(
                f"Stooq response is not valid CSV: {exc}", retriable=False
            ) from exc
