# MCP SERVER — Model Context Protocol for AI Agents

**Generated:** 2026-05-18

## OVERVIEW

Thin MCP server (`quantdinger-mcp` on PyPI) that wraps the Agent Gateway REST API as MCP tools — lets Cursor, Claude Code, Codex, and other MCP clients drive QuantDinger without custom HTTP code.

## STRUCTURE

```
mcp_server/
├── pyproject.toml          # Package config → publishes to PyPI
├── Dockerfile              # Containerized deployment
├── railway.json            # Railway deployment template
├── src/quantdinger_mcp/
│   ├── __init__.py
│   └── server.py           # Main server (tools, transports)
└── tests/
```

## WHAT IT EXPOSES

| Tool | Class | Purpose |
|------|-------|---------|
| `whoami` | R | Inspect agent token |
| `list_markets` | R | Markets available to token |
| `search_symbols` | R | Symbols within a market |
| `get_klines` | R | OHLCV bars |
| `get_price` | R | Latest price |
| `list_strategies` | R | Tenant's strategies |
| `get_strategy` | R | One strategy detail |
| `submit_backtest` | B | Queue a backtest job |
| `get_job` | R | Poll job status/results |
| `regime_detect` | B | Synchronous regime detection |
| `submit_structured_tune` | B | Queue grid/random tuning |

## CONVENTIONS

- **No live trading from MCP**: only Read (R) and Backtest (B) tools exposed
- **Env-only config**: `QUANTDINGER_BASE_URL`, `QUANTDINGER_AGENT_TOKEN` required; `QUANTDINGER_MCP_TRANSPORT` optional
- **Three transports**: stdio (default, for desktop IDEs), SSE, Streamable HTTP
- **Single-file server**: all tool definitions in `server.py` — no routing split
- **httpx for upstream**: calls Agent Gateway REST endpoints with configurable timeout

## ANTI-PATTERNS

- Do NOT add Trading (T) class tools — live trading from MCP is intentionally out of scope
- Do NOT hardcode the Agent Gateway URL — always use `QUANTDINGER_BASE_URL` env var
- Do NOT embed agent tokens in config files — env vars only
- Do NOT duplicate Agent Gateway logic — MCP server is a thin proxy, not a reimplementation
