# Backlog

Companion to [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md). Sprints are logical, dependency-ordered batches — not time-boxed. Move to the next sprint once the current one's commits are reviewed and merged.

Sizing rule: a commit either fully completes one or more tasks, or a task is broken into multiple complete commits. Nothing half-finished lands mid-task.

Checkboxes track status: `[ ]` not started, `[~]` in progress, `[x]` done (merged).

---

## Sprint 1 — Performance tracking: backend & data

Gets real Finnhub price data flowing into the database on a schedule. No API/UI yet — this sprint is plumbing.

- [ ] **1.1 — Data model**: `PriceSnapshot` and `PortfolioSnapshot` SQLAlchemy models + Alembic migration.
  - `app/models/price_snapshot.py`, `app/models/portfolio_snapshot.py`, migration in `alembic/versions/`.
  - One commit: models + migration together (migration is meaningless without the models it targets).

- [ ] **1.2 — Finnhub client + config**: a thin client wrapping `/quote`, plus config wiring.
  - `app/core/config.py`: add `finnhub_api_key`.
  - `.env.example`: add `FINNHUB_API_KEY`.
  - `app/services/finnhub_service.py`: `get_quote(ticker) -> QuoteResult` (price, timestamp), using `httpx` (already a dependency).
  - Unit test with a mocked HTTP response — no live API calls in tests.
  - One commit.

- [ ] **1.3 — Poll cycle logic**: the function a scheduler will eventually call.
  - `app/services/price_service.py` (or extend `finnhub_service.py`): given all distinct tickers across holdings, fetch quotes, write `PriceSnapshot` rows, update each `Holding.current_price_cents`/`last_priced_at`, compute + write `PortfolioSnapshot` rows per portfolio.
  - Tests against the transactional Postgres fixture (existing pattern in `tests/conftest.py`), Finnhub client mocked.
  - One commit. Depends on 1.1 and 1.2.

- [ ] **1.4 — Scheduler wiring**: APScheduler job that calls 1.3 on an interval, market-hours aware.
  - New module (e.g. `app/core/scheduler.py`): weekday + 9:30am–4:00pm ET window check, 15-minute interval trigger.
  - Wire into `app/main.py` startup/shutdown (start scheduler on app startup, shut down cleanly).
  - Test the market-hours predicate directly (pure function, easy to unit test with fixed datetimes) — don't test the scheduler itself running on a timer.
  - One commit. Depends on 1.3.

**Sprint 1 exit criteria**: running the app locally, the scheduler fires during market hours and `price_snapshots`/`portfolio_snapshots` rows appear; `holdings.current_price_cents` updates independent of trades.

---

## Sprint 2 — Performance tracking: API & frontend

Exposes the data from Sprint 1 and visualizes it.

- [ ] **2.1 — Performance API endpoints**: read endpoints for chart data.
  - `GET /portfolios/{portfolio_id}/performance?range=1D|1W|1M` → `PortfolioSnapshot` series.
  - `GET /portfolios/{portfolio_id}/holdings/{holding_id}/performance?range=1D|1W|1M` → `PriceSnapshot` series for that holding's ticker.
  - New schemas in `app/schemas/`, service functions, routes following the existing ownership-scoped 404 pattern.
  - Route tests mirroring `tests/test_portfolios.py` / `tests/test_holding.py` conventions.
  - One commit.

- [ ] **2.2 — Frontend data layer**: chart library + API/store wiring, no UI yet.
  - `npm install chart.js vue-chartjs` in `frontend/`.
  - `frontend/src/api/`: calls for the two new endpoints.
  - `frontend/src/stores/portfolio.ts` (or a new store): state + actions for performance series, range selection.
  - One commit.

- [ ] **2.3 — Portfolio-level chart**: renders on `PortfolioDetailView`.
  - New component (e.g. `frontend/src/components/portfolio/PerformanceChart.vue`), range toggle (1D/1W/1M), loading/empty states.
  - One commit. Depends on 2.1, 2.2.

- [ ] **2.4 — Per-holding chart (expand-in-place)**: click a holdings-table row to reveal that ticker's chart inline.
  - Extends the existing table in `PortfolioDetailView.vue` — expandable row or popover, reusing the chart component from 2.3 where possible.
  - One commit. Depends on 2.1, 2.2.

- [ ] **2.5 — P&L display**: unrealized gain/loss ($ and %) per holding and portfolio total.
  - Pure computation from existing `avg_cost_basis_cents`/`current_price_cents` (extend `frontend/src/utils/money.ts`), rendered in the holdings table and portfolio header.
  - No backend change needed. One commit, independent of 2.1–2.4 (can land anytime after Sprint 1, even in parallel).

**Sprint 2 exit criteria**: opening a portfolio shows a live-updating performance chart and per-holding charts backed by real Finnhub data, plus visible P&L.

---

## Sprint 3 — Agent foundation

Proves the DeepSeek/Anthropic-contract mechanics work, then builds the tool-use loop. No app integration yet.

- [ ] **3.1 — Spike: DeepSeek tool-calling smoke test**.
  - Add `anthropic` to `requirements.txt`; config wiring for `ANTHROPIC_API_KEY`/`ANTHROPIC_BASE_URL` (already set locally, but should be documented in `.env.example` and read via `app/core/config.py`).
  - `tests/test_agent_smoke.py`: one test that sends a single message with one trivial tool defined (e.g. an `add(a, b)` tool) and asserts a `tool_use` block comes back with the right input — proves tool-calling actually works against the DeepSeek endpoint before anything else is built on top of that assumption.
  - One commit. **This is a checkpoint** — if DeepSeek's tool-calling semantics don't match what the loop needs, surface that before Sprint 3 continues, not after.

- [ ] **3.2 — Tool implementations**: the three portfolio tools as plain Python functions + their Anthropic tool-schema definitions.
  - `get_holdings`, `get_price_history`, `get_trade_history` — likely in a new `app/services/agent_tools.py`.
  - Each takes `db`, the server-bound `portfolio_id`, and only the model-controlled params from the spec (ticker/range) — never `portfolio_id` itself from the model.
  - Unit tests calling each function directly against the test DB.
  - One commit. Depends on Sprint 1/2 data model (uses `PriceSnapshot`, `Holding`, `Trade`).

- [ ] **3.3 — Agent loop**: the hand-rolled tool-use loop.
  - New module (e.g. `app/services/agent_service.py`): system prompt (analytical-not-prescriptive constraint + disclaimer instruction), `deepseek-chat` model, temperature `0.2`, loop cap of 6 round trips, dispatches `tool_use` blocks to the functions from 3.2, returns final text.
  - Test with the real client against a live/mocked portfolio (decide during implementation whether to mock the API call or let this one hit DeepSeek for real, given it's inherently an integration point).
  - One commit. Depends on 3.1, 3.2.

**Sprint 3 exit criteria**: a Python-level call to the agent service, given a portfolio_id, returns a coherent analysis string, with tool calls visibly happening in between (e.g. via logging).

---

## Sprint 4 — Agent integration

Wires the agent into the app.

- [ ] **4.1 — Analyze endpoint**: `POST /portfolios/{portfolio_id}/analyze`.
  - Ownership check (existing pattern), calls the Sprint 3 agent service, returns the report text. No persistence (ephemeral, per spec).
  - Route test — likely mocking the agent service call so tests don't hit DeepSeek.
  - One commit.

- [ ] **4.2 — Frontend "Analyze portfolio" UI**.
  - Button on `PortfolioDetailView`, loading state (this call may take a few seconds due to the tool loop), report rendered in a panel/modal, visible disclaimer text.
  - One commit. Depends on 4.1.

**Sprint 4 exit criteria**: clicking "Analyze portfolio" in the running app produces a real, tool-informed written analysis.

---

## Explicitly not in this backlog

Carried over from the spec's out-of-scope lists — not forgotten, just deliberately deferred:

- Historical price backfill / paid data plan
- YTD/ALL chart ranges
- Holiday-aware market calendar
- Dedicated holding detail page/route
- Persisted agent analyses (`AgentReport` table)
- Conversational/multi-turn agent UI
- User-configurable agent prompt/model/temperature
