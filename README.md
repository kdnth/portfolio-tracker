# Portfolio Tracker

A full-stack web app for tracking investment portfolios: create accounts, manage portfolios, record buy/sell trades, and view holdings with weighted-average cost basis.

Built as a portfolio project to practice backend design with FastAPI, typed frontend architecture, and deployment path (Postgres, containerized API, static SPA).

## Features

- User registration and login with JWT authentication
- Multiple portfolios per user
- Buy and sell trades that update holdings in the same request
- Weighted-average cost basis on buys
- Holdings view with market value derived from last trade price
- Ownership-scoped API routes (cross-user access returns 404)
- Deployed API on Railway, SPA on Netlify, Postgres on Neon

## Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI, Uvicorn, Pydantic v2 |
| Auth | JWT (python-jose), bcrypt (Passlib) |
| ORM / DB | SQLAlchemy 2, Alembic, PostgreSQL (psycopg3) |
| Frontend | Vue 3, TypeScript, Vite, Pinia, Vue Router, Tailwind CSS v4 |
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

### Ownership failures return 404, not 403

Looking up another user's portfolio, trades, or holdings returns "not found," not "forbidden.""

### Auth that avoids user enumeration on login

Login accepts username or email. Failed lookups and bad passwords both return the same unauthorized response.

### Frontend auth as infrastructure

A shared Axios client attaches the Bearer token, clears the session on 401, and redirects to login. Vue Router guards enforce `requiresAuth` and `guestOnly` routes, including post-login redirects.

### Typed SPA with a small UI kit

Views stay thin and call Pinia stores for domain state. Shared form primitives handle labels, errors, loading, and basic accessibility (`aria-*`, modal focus/escape behavior). Tailwind `@theme` tokens keep color and typography consistent.

### Schema migrations on release

Alembic migrations run as Railway's release command before the new container takes traffic. The API normalizes Neon-style `postgresql://` URLs to `postgresql+psycopg://` so deploy config stays simple.

### Tests against real Postgres with rollback

API tests use FastAPI's `TestClient` against Postgres. Each test runs in a transaction that rolls back, so tests stay isolated without rebuilding the database every run.

## Architecture

```text
Browser (Vue SPA on Netlify)
    |
    | HTTPS + JWT
    v
FastAPI (Docker on Railway)
    |
    | SQLAlchemy / Alembic
    v
PostgreSQL (Neon)
```

Backend layout:

```text
app/
  api/routes/     # HTTP adapters
  services/       # domain logic
  models/         # SQLAlchemy ORM
  schemas/        # Pydantic DTOs
  core/           # config, security, deps, exceptions
  db/             # engine and session
```

Domain model:

```text
User 1-* Portfolio 1-* Holding 1-* Trade
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
| `POST` | `/portfolios/{id}/trades` | Yes | Updates holdings |
| `GET` | `/portfolios/{id}/holdings` | Yes | Ownership-scoped |
| `GET` | `/health` | No | Deploy healthcheck |

## Local development

### Prerequisites

- Python 3.12+
- Node.js 22+
- PostgreSQL

### API

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# set DATABASE_URL and JWT_SECRET

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

## Deployment

Order: database, then API, then frontend. The SPA needs the public API URL at build time.

Detailed steps live in [`DEPLOY.md`](./DEPLOY.md). Summary:

1. **Neon** for Postgres (`sslmode=require`)
2. **Railway** from the repo root Docker image; set `DATABASE_URL`, `JWT_SECRET`, and `CORS_ORIGINS`
3. **Netlify** with `VITE_API_BASE_URL` pointing at the public Railway HTTPS URL

Use Railway's public domain for the frontend. The `*.railway.internal` hostname is private network only and is not reachable from the browser.

## Scope notes

This is an intentional MVP, not a brokerage clone.

- Prices come from recorded trades, not a live market feed
- No refresh tokens, rate limiting, or password reset yet
- Market value is computed on the client from holdings data

Those are the next steps if I decide to extend the project (scheduled price updates, richer P&L, stronger session handling).

## License

MIT. See [`LICENSE`](./LICENSE).
