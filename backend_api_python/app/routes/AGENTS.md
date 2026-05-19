# ROUTES — REST API Endpoints

**Generated:** 2026-05-18

## OVERVIEW

Flask REST endpoints — thin HTTP layer that delegates to services. Auth, strategy, backtest, market data, AI analysis, broker integrations, billing, and the Agent Gateway.

## WHERE TO LOOK

| Endpoint Group | File | Notes |
|----------------|------|-------|
| Auth / login | `auth.py` | JWT-based |
| User CRUD | `user.py` | Admin + self-service |
| Strategies | `strategy.py` | CRUD + start/stop |
| Backtests | `backtest.py` | Submit + results |
| Indicators | `indicator.py` | IDE + execution |
| K-line data | `kline.py` | OHLCV + indicators |
| Market list | `market.py` | Available markets |
| Portfolio | `portfolio.py` | Positions + P&L |
| Quick trade | `quick_trade.py` | One-click orders |
| AI analysis | `fast_analysis.py` | Main AI entry point |
| AI chat | `ai_chat.py` | Conversational |
| Agent Gateway | `agent_v1/` | Token-scoped API |
| Broker APIs | `ibkr.py`, `mt5.py`, `alpaca.py` | Per-broker |
| Settings | `settings.py` | App + brand config |
| Billing | `billing.py` | Credits + membership |
| Dashboard | `dashboard.py` | Aggregated views |

## CONVENTIONS

- **Prefix**: all routes under `/api/` namespace
- **Auth**: JWT required except login/register/health; `@jwt_required()` decorator
- **Agent Gateway**: under `/api/agent/v1/` with separate token auth (not JWT)
- **Error responses**: standard JSON shape with `error` field
- **Pagination**: `page` + `page_size` query params where applicable

## ANTI-PATTERNS

- Do NOT put business logic in routes — routes call services and return JSON
- Do NOT skip auth checks — every non-public endpoint must verify JWT or agent token
- Do NOT hardcode market names — use `current_app.config` or service layer enums
