# DATA SOURCES — Market Data Abstraction Layer

**Generated:** 2026-05-18

## OVERVIEW

Market data abstraction layer with factory pattern — normalizes OHLCV, fundamentals, and sentiment across crypto, US stocks, CN/HK stocks, forex, futures, and MOEX.

## STRUCTURE

- `base.py` — Abstract base data source class
- `factory.py` — Provider selection (returns correct source by market type)
- Market implementations: `crypto.py`, `us_stock.py`, `forex.py`, `futures.py`, `cn_stock.py`, `hk_stock.py`, `asia_stock_kline.py`, `moex.py`, `tencent.py`, `cn_hk_fundamentals.py`
- Cross-cutting: `cache_manager.py`, `circuit_breaker.py`, `rate_limiter.py`, `errors.py`

## WHERE TO LOOK

| Concern | File |
|---------|------|
| Data source base class | `base.py` |
| Factory / provider selection | `factory.py` |
| Crypto (CCXT) | `crypto.py` |
| US stocks (yfinance) | `us_stock.py` |
| Forex | `forex.py` |
| Futures | `futures.py` |
| China A-shares | `cn_stock.py` |
| Cache layer | `cache_manager.py` |
| Circuit breaker | `circuit_breaker.py` |
| Rate limiter | `rate_limiter.py` |

## CONVENTIONS

- **Factory pattern**: `factory.py` selects the right source by market label — callers never instantiate sources directly
- **CCXT for crypto**, **yfinance for US stocks**: primary libraries with timeout/env config
- **Rate limiting + circuit breaker**: every external data source wraps requests through `rate_limiter.py` / `circuit_breaker.py`
- **Timeouts**: configured via `DATA_SOURCE_TIMEOUT` env var (default 30s)
- **Error hierarchy**: `errors.py` defines typed exceptions per source type

## ANTI-PATTERNS

- Do NOT add market-specific logic outside its dedicated file — each market gets its own source module
- Do NOT bypass the factory — always use `Factory.get_source(market_type)` instead of instantiating directly
- Do NOT hardcode API URLs — use env vars (e.g. `FINNHUB_API_KEY`, `TIINGO_API_KEY`)
