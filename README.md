# Portfolio Tracker

A full-stack web app for tracking investment portfolios: create accounts, manage portfolios, record buy/sell trades, track real market performance, and get an AI-generated analysis of your holdings.

Built as a portfolio project to practice backend design with FastAPI, typed frontend architecture, a real external-API integration surface (market data + LLM), and a deployment path (Postgres, containerized API, static SPA).

## Features

- User registration and login with JWT authentication
- Multiple portfolios per user
- Buy and sell trades that update holdings in the same request
- Weighted-average cost basis on buys
- Live market prices via Finnhub, polled on a market-hours-aware schedule (9:30am–4:00pm ET, weekdays)
- 30-day historical price backfill via Twelve Data the first time a ticker is tracked
- Interactive performance charts — portfolio-level and per-holding, 1D/1W/1M ranges, real timestamps
- Unrealized gain/loss ($ and %) per holding and portfolio total
- AI portfolio analysis: a tool-using agent (Claude Haiku 4.5) that queries your actual holdings, price history, and trade history, then writes a grounded, non-prescriptive report
- Ownership-scoped API routes (cross-user access returns 404)
- Deployed API on Railway, SPA on Netlify, Postgres on Neon

## Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI, Uvicorn, Pydantic v2 |
| Auth | JWT (python-jose), bcrypt (Passlib) |
| ORM / DB | SQLAlchemy 2, Alembic, PostgreSQL (psycopg3) |
| Market data | Finnhub (live quotes), Twelve Data (historical backfill), APScheduler (polling) |
| AI agent | Anthropic Messages API (Claude Haiku 4.5), hand-rolled tool-use loop — no agent framework |
| Frontend | Vue 3, TypeScript, Vite, Pinia, Vue Router, Tailwind CSS v4 |
| Charts | Chart.js + vue-chartjs, chartjs-adapter-date-fns |
| Report rendering | marked + DOMPurify (sanitized markdown → HTML) |
| Tests | pytest with transactional fixtures |
| Deploy | Docker on Railway, Netlify, Neon |

## Engineering decisions

### Layered API

- Business rules live in services, never controllers. 
- Pydantic schemas are the request/response boundary
- SQLAlchemy models stay out of the HTTP layer

### Money as integer cents

Prices and cost basis are stored as `*_cents` integers e2e. Cent/dollar conversion happens client side

### Trades update holdings atomically

Recording a trade does more than insert a row. The service finds or creates the holding for that ticker, updates share count, recalculates average cost on buys, rejects oversells, and commits the trade and holding together.

### Money and shares are Decimal end-to-end, not float

Share counts round-trip through Postgres as `decimal.Decimal` (a `Numeric` column) — Python refuses to mix `Decimal` with `float` in arithmetic rather than silently losing precision. Rather than coercing at each call site, `TradeCreate.shares` is typed `Decimal` too, so the whole trade-recording path stays one consistent numeric type.

### Ownership failures return 404, not 403

Looking up another user's portfolio, trades, or holdings returns "not found," not "forbidden."

### Auth that avoids user enumeration on login

Login accepts username or email. Failed lookups and bad passwords both return the same unauthorized response.

### Frontend auth as infrastructure

A shared Axios client attaches the Bearer token, clears the session on 401, and redirects to login. Vue Router guards enforce `requiresAuth` and `guestOnly` routes, including post-login redirects.

### Typed SPA with a small UI kit

Views stay thin and call Pinia stores for domain state. Shared form primitives handle labels, errors, loading, and basic accessibility (`aria-*`, modal focus/escape behavior). Tailwind `@theme` tokens keep color and typography consistent.

### Market-hours-aware price polling

A scheduled job polls Finnhub every 15 minutes, but only 9:30am–4:00pm ET on weekdays — it skips silently outside that window rather than wasting API calls or storing meaningless overnight/weekend snapshots.

### One price history, shared across users

`PriceSnapshot` is keyed by ticker, not by holding — two users holding AAPL share the same price history rows instead of duplicating them per portfolio. `PortfolioSnapshot` is the only per-portfolio rollup, precomputed on each poll cycle for fast chart reads.

### Historical backfill is bounded and self-healing

The first trade on a genuinely new ticker triggers a 30-day backfill from Twelve Data, rate-limited client-side to the provider's actual free-tier cap (8 requests/minute) so the app never gets throttled by surprise. A backfill that fails (rate limit, bad symbol, network error) doesn't fail the trade — it just retries on the next trade recorded for that ticker, since a new `Holding` only gets created once.

### The agent's tool loop is hand-written, not framework-managed

Built directly against the Anthropic Messages API (the `anthropic` SDK) rather than an agent framework — the loop that calls the model, dispatches `tool_use` blocks to real Python functions, and feeds `tool_result`s back is application code, on purpose, so every step of "what makes this agentic" stays visible and readable. Capped at 6 tool-call rounds before forcing a final answer, so a model that never stops calling tools still terminates.

### The agent can't see what it isn't given

Tools take `portfolio_id` as a server-bound parameter the model never supplies — the agent can only ever query the portfolio the request was actually made for, mirroring the same ownership-scoping used everywhere else in the API.

### AI-generated report rendering is sanitized, not trusted

The agent's markdown output is parsed with `marked` and passed through `DOMPurify` before it ever reaches `v-html`. It's treated as untrusted content on the way to the DOM — not exempted just because it came from "our own" model.

### Schema migrations on deploy

Alembic migrations run as Railway's pre-deploy command (`railway.toml`'s `preDeployCommand`) after the build, before the new container takes traffic. The API normalizes Neon-style `postgresql://` URLs to `postgresql+psycopg://` so deploy config stays simple.

### Tests against real Postgres with rollback

API tests use FastAPI's `TestClient` against Postgres. Each test runs in a transaction that rolls back, so tests stay isolated without rebuilding the database every run. External APIs (Finnhub, Twelve Data) are mocked in tests by default; the agent's own tests include one real, unmocked integration call against the Anthropic API, since that's the thing that actually proves the tool-use loop works.

## Architecture

```text
Browser (Vue SPA on Netlify)
    |
    | HTTPS + JWT
    v
FastAPI (Docker on Railway) --- market-hours scheduler --- Finnhub (live quotes)
    |                                                   \-- Twelve Data (history backfill)
    |-- SQLAlchemy / Alembic --> PostgreSQL (Neon)
    |-- Anthropic Messages API --> Claude Haiku 4.5 (portfolio analysis agent)
```

Backend layout:

```text
app/
  api/routes/     # HTTP adapters
  services/       # domain logic (trades, pricing, scheduler, agent tools + loop)
  models/         # SQLAlchemy ORM
  schemas/        # Pydantic DTOs
  core/           # config, security, deps, exceptions
  db/             # engine and session
```

Domain model:

```text
User 1-* Portfolio 1-* Holding 1-* Trade

PriceSnapshot      -- by ticker, shared across every portfolio holding it
PortfolioSnapshot  -- by portfolio, precomputed value-over-time rollup
```

## API overview

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/auth/register` | No | Returns JWT |
| `POST` | `/auth/login` | No | Username or email |
| `GET` | `/users/me` | Yes | Current user |
| `POST` | `/portfolios/` | Yes | Create portfolio |
| `GET` | `/portfolios/` | Yes | List own portfolios |
| `GET` | `/portfolios/{id}` | Yes | Ownership-scoped |
| `GET` | `/portfolios/{id}/performance` | Yes | Portfolio value over time (`?range=1D\|1W\|1M`) |
| `POST` | `/portfolios/{id}/analyze` | Yes | Runs the AI agent, returns a written report |
| `POST` | `/portfolios/{id}/trades/` | Yes | Updates holdings; backfills history for new tickers |
| `GET` | `/portfolios/{id}/holdings/` | Yes | Ownership-scoped |
| `GET` | `/portfolios/{id}/holdings/{holding_id}/performance` | Yes | Ticker price history (`?range=1D\|1W\|1M`) |
| `GET` | `/health` | No | Deploy healthcheck |

## Local development

### Prerequisites

- Python 3.12+
- Node.js 22+
- PostgreSQL
- API keys: [Finnhub](https://finnhub.io) (free tier), [Twelve Data](https://twelvedata.com) (free tier), [Anthropic](https://console.anthropic.com) (pay-as-you-go)

### API

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# set DATABASE_URL, JWT_SECRET, FINNHUB_API_KEY, TWELVE_DATA_API_KEY, ANTHROPIC_API_KEY

alembic upgrade head
uvicorn app.main:app --reload
```

API docs: `http://localhost:8000/docs`

### Frontend

```bash
cp frontend/.env.example frontend/.env
# VITE_API_BASE_URL=http://localhost:8000

cd frontend
npm install
npm run dev
```

App: `http://localhost:5173`

### Tests

Create and migrate a Postgres test database (default name `portfolio_tracker_test`, or set `TEST_DATABASE_URL`), then:

```bash
pytest
```

The agent smoke test makes a real call against the Anthropic API and costs a small amount of real credit on every run.

## Deployment

Order: database, then API, then frontend. The SPA needs the public API URL at build time.

Detailed steps live in [`DEPLOY.md`](./DEPLOY.md). Summary:

1. **Neon** for Postgres (`sslmode=require`)
2. **Railway** from the repo root Docker image; set `DATABASE_URL`, `JWT_SECRET`, `CORS_ORIGINS`, `FINNHUB_API_KEY`, `TWELVE_DATA_API_KEY`, and `ANTHROPIC_API_KEY`
3. **Netlify** with `VITE_API_BASE_URL` pointing at the public Railway HTTPS URL

Use Railway's public domain for the frontend. The `*.railway.internal` hostname is private network only and is not reachable from the browser.

## Scope notes

This is an intentional MVP, not a brokerage clone.

- Historical backfill is bounded to the most recent 30 days, not full since-inception history — no YTD/ALL chart ranges yet
- No holiday-aware market calendar for the price scheduler — just a weekday/time-window check
- The AI analysis is one-shot, not conversational, and isn't persisted — re-running calls the agent again from scratch
- No refresh tokens, rate limiting, or password reset yet

Those are the next steps if I decide to extend the project further (since-inception history, YTD/ALL ranges, persisted analysis history, stronger session handling).

## License

MIT. See [`LICENSE`](./LICENSE).
