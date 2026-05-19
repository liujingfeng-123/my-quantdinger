# SERVICES — Core Business Logic

**Generated:** 2026-05-18

## OVERVIEW

Strategy runtime, AI analysis, backtesting, trading execution, billing, and user services — the engine room of QuantDinger.

## WHERE TO LOOK

| Task | File |
|------|------|
| AI market analysis | `fast_analysis.py` |
| LLM integration | `llm.py` |
| Strategy lifecycle | `strategy_lifecycle.py` |
| Backtesting engine | `backtest.py` |
| Live trading executors | `live_trading/` |
| Alpaca trading | `alpaca_trading/` |
| IBKR trading | `ibkr_trading/` |
| MT5 trading | `mt5_trading/` |
| USDT payment processing | `usdt_payment/` + `usdt_payment_service.py` |
| K-line / market data | `kline.py` |
| Pending order worker | `pending_order_worker.py` |
| Portfolio monitor | `portfolio_monitor.py` |
| User management | `user_service.py` |
| Billing / credits | `billing_service.py` |
| Strategy compilation | `strategy_compiler.py` |
| Signal notifier | `signal_notifier.py` |
| Security / rate limiting | `security_service.py` |
| AI calibration | `ai_calibration.py` |

## CONVENTIONS

- **Single responsibility per file**: strategy lifecycle, compiler, script runtime, and snapshot are separate files
- **Subdirectories for broker adapters**: each broker (alpaca/ibkr/mt5) has its own subdir with isolated dependencies
- **Thread-based execution**: strategy runtime uses thread pool, not asyncio
- **Postgres-backed memory**: analysis memory, strategy state, backtest results all in PostgreSQL
- **Env-gated workers**: pending order, portfolio monitor, reflection workers are opt-in via env vars

## ANTI-PATTERNS

- Do NOT add broker logic outside its dedicated subdir — `exchange_execution.py` is the only cross-cutting abstraction
- Do NOT call routes directly from services — services return values, routes handle HTTP concerns
- Do NOT hardcode provider names — use the data sources factory layer instead
