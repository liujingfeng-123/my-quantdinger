# PROJECT KNOWLEDGE BASE

**Generated:** 2026-05-18
**Commit:** dc9a935
**Branch:** main

## OVERVIEW

**QuantDinger** — Self-hosted AI Quant Operating System. Python/Flask backend + Vue frontend, Docker Compose deployment. Crypto/US stocks/forex trading, AI analysis, backtesting, strategy runtime, multi-user billing.

## STRUCTURE

```
QuantDinger/
├── backend_api_python/   # Flask API (source code)
│   ├── app/routes/       # REST endpoints
│   ├── app/services/     # Core business logic
│   ├── app/data_sources/ # Market data abstraction layer
│   ├── app/data_providers/ # Market-specific data providers
│   ├── app/utils/        # PostgreSQL, config, logging helpers
│   ├── migrations/       # init.sql schema
│   ├── tests/            # ~27 test files
│   └── run.py            # Entrypoint
├── mcp_server/           # MCP server (PyPI: quantdinger-mcp)
├── docs/                 # Product & strategy documentation
├── scripts/              # Secret key generation, i18n tools
└── docker-compose.yml    # Postgres + Redis + Backend + Frontend
```

## WHERE TO LOOK

| Task | Location |
|------|----------|
| REST endpoints | `backend_api_python/app/routes/` |
| Backtesting engine | `backend_api_python/app/services/backtest.py` |
| AI analysis services | `backend_api_python/app/services/fast_analysis.py` |
| Strategy lifecycle | `backend_api_python/app/services/strategy_lifecycle.py` |
| Live trading executors | `backend_api_python/app/services/live_trading/` |
| Broker integrations | `backend_api_python/app/services/{alpaca,ibkr,mt5}_trading/` |
| LLM integration | `backend_api_python/app/services/llm.py` |
| Market data sources | `backend_api_python/app/data_sources/` |
| Data providers | `backend_api_python/app/data_providers/` |
| Agent Gateway API | `backend_api_python/app/routes/agent_v1/` |
| MCP server | `mcp_server/src/quantdinger_mcp/server.py` |
| DB schema | `backend_api_python/migrations/init.sql` |
| Environment config | `backend_api_python/env.example` |

## CONVENTIONS

- **Env-driven config**: All runtime behavior via `backend_api_python/.env` (copy from `env.example`)
- **Postgres + Redis**: Required infrastructure; pool config per `env.example`
- **PyPI-published MCP**: `mcp_server/` published as `quantdinger-mcp` on PyPI
- **Threaded workers**: `ThreadedConnectionPool` for DB, thread-based strategy executor
- **CCXT + yfinance**: Primary crypto + stock data libraries
- **Multi-user RBAC**: admin/manager/user/viewer roles; `user_id` isolation in queries

## ANTI-PATTERNS (THIS PROJECT)

- **Never commit `SECRET_KEY` placeholder** — `SECRET_KEY=quantdinger-secret-key-change-me` blocks container start
- **Never ship exchange API keys** in code or config; always via `.env`
- **Never suppress TLS verification** — `LIVE_TRADING_SSL_VERIFY=false` only as last resort
- **Never `as any`/`@ts-ignore`** — not applicable (Python project), but same principle: no silent error suppression
- **Never modify `migrations/init.sql` without migration strategy** — uses `CREATE TABLE IF NOT EXISTS`

## UNIQUE STYLES

- `IndicatorStrategy` (dataframe signals) + `ScriptStrategy` (event-driven `on_bar`) — two distinct strategy authoring models
- Agent Gateway (`/api/agent/v1`) with token-scoped permissions (R=read, B=backtest, T=trade)
- Strategy auto-restore on startup via `DISABLE_RESTORE_RUNNING_STRATEGIES`
- USDT payment with amount-suffix matching (single fixed address per chain)
- Brand config via env vars (`BRAND_*`) — no frontend rebuild needed for rebranding

## COMMANDS

```bash
# Start stack
docker-compose up -d --build

# Dev server (local Python)
cd backend_api_python && python run.py

# Tests
cd backend_api_python && python -m pytest tests/

# MCP server
cd mcp_server && pip install -e . && quantdinger-mcp
```

## NOTES

- Frontend source is in **separate repo** (QuantDinger-Vue), published as GHCR image
- Mobile app: **QuantDinger-Mobile** (open source)
- `FRONTEND_URL` must be set correctly for CORS/OAuth redirects
- IBKR/MT5 require local desktop TWS/terminal — not available on cloud-only deployments
- Agent tokens are **paper-only by default** — live trading requires `AGENT_LIVE_TRADING_ENABLED=true`
- v3.0.10 removed bundled `frontend/dist` — now always pulls from GHCR
