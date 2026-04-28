# Logging — IBKR Portfolio Tracker

> Stage 4 output. Logging is in place; this doc captures what's there and conventions to keep.
> Status: **Implemented** — backend logger active, no major changes planned.

## Overview

The project uses Python's `logging` stdlib through a centralized helper at [backend/api/utils/logger.py](../../../../backend/api/utils/logger.py). Every module imports from there. Logs go to both stdout (visible in dev server output) and per-day files under `logs/`.

## Loggers

| Logger | Module | Purpose |
|---|---|---|
| `logger` (root) | most modules | General backend events |
| `api_logger` (`api.requests`) | route handlers | HTTP-shape events with the request middleware |

## Format

Standard format:
```
%(asctime)s [%(name)s] %(levelname)s %(message)s
```

Plus the project emoji conventions (per global `~/.claude/CLAUDE.md`):
- 📥 in
- 📤 out
- ✅ success
- ❌ error
- ⚠️ warning
- 🗄️ db
- 🚀 startup
- 📊 stats / read
- 📋 list
- 📑 corp actions
- ✂️ splits
- 🔄 sync
- 📡 fetch / network

Format inside log lines: `[ModuleName] verb: detail` (e.g. `📊 Listed 25 transactions (page 1/24)`).

## Log file locations

| File | Source |
|---|---|
| `logs/backend_<YYYY-MM-DD>.log` | Backend / business logic (the `logger` instance) |
| `logs/api_<YYYY-MM-DD>.log` | HTTP request/response middleware |
| `logs/frontend_<YYYY-MM-DD>.log` | Browser-side calls (logged via Next.js API proxy) |

## Levels

- **INFO** — happy-path events (sync started, rows inserted, route hit)
- **WARNING** — recoverable degradation (rate-limit-backoff, partial CA fetch failure, missing optional env var)
- **ERROR** — failures that abort an operation (Flex auth error, schema mismatch, unhandled exception in route)

`DEBUG` reserved for active troubleshooting only — never default.

## What NOT to log

Per global CLAUDE.md:
- Passwords
- API keys (IBKR Flex token shows only `xxxx...xxxx` prefix in startup log)
- PII (the project doesn't have any beyond the user's own positions)

## When to add a new log line

- At the start of any sync step (`logger.info("📊 Sync step: positions")`)
- On every state-changing DB write of meaningful size (insert N rows, delete N rows)
- On every external API call that hit the network (yfinance, Wikipedia, IBKR)
- On every error path with enough context to debug from the log alone
- NOT for routine reads (`SELECT * FROM ...`) — too chatty

## Cross-cutting middleware

[backend/api/middleware/logging_middleware.py](../../../../backend/api/middleware/logging_middleware.py) wraps every HTTP request to log: method + path + status + elapsed-ms via the `api_logger`.

## Front-end logging

The Next.js proxy at `frontend/app/api/proxy/[...path]/route.ts` writes incoming/outgoing HTTP events to `logs/frontend_<YYYY-MM-DD>.log`. UI components mostly use `console.error` / `console.warn` for browser-side debugging — those go to the dev tools, not the log file.

## Operational notes

- Log rotation: by-day filename, no automatic cleanup. Manual `rm logs/*_2026-01-*.log` if growth becomes a problem (unlikely at single-user scale).
- Dev server tails: `tail -f /tmp/uvicorn.log` shows the live backend log when started via the `nohup`/`run_in_background` patterns we use.
- Production deployment: N/A — this is a local-only app.

## Known gaps

- No structured JSON logs (line-format only). If we ever add log analysis tooling, switch to `python-json-logger`.
- No per-correlation-ID tracing across the FastAPI ↔ subprocess boundary (yfinance fetch in a thread). Acceptable for solo-user scale.
