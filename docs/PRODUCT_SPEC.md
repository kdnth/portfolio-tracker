# Product Spec: Performance Tracking + Embedded Analysis Agent

Status: draft, pending review
Last updated: 2026-08-20

This spec covers two additions to Portfolio Tracker:

1. **Performance tracking** — real market price data via Finnhub, with historical charts for individual holdings and whole portfolios.
2. **Analysis agent** — an embedded, tool-using agent (built on the Anthropic Messages API contract) that analyzes a portfolio on request.

Both are portfolio-piece features: the point is to demonstrate the engineering, not to ship a brokerage-grade product. Scope is deliberately trimmed where the trade-off is "more impressive" vs. "actually necessary."

This doc is the reference for the build. Decisions recorded here shouldn't be re-litigated without discussion — if reality forces a change, update this doc in the same commit.

---

## Feature 1: Performance Tracking (Finnhub + Twelve Data)

### Goal

Show real market price movement for each holding and for a portfolio as a whole, as a chart, using live data instead of "last trade price."

### Data source

- **Finnhub free tier** for live pricing. `/quote` (current price) is available free; `/stock/candle` (historical) is not — it 403s on free keys. No paid Finnhub plan.
- **Twelve Data free tier** for a bounded historical backfill. Free tier includes `/time_series` with daily historical bars (800 API credits/day) — unlike Finnhub, whose free tier excludes historical data entirely. Used only to backfill the most recent 30 days of daily closes the first time a ticker is ever tracked; Finnhub remains the source for everything going forward from there. See "Historical backfill" below.
- Config: `FINNHUB_API_KEY` and `TWELVE_DATA_API_KEY` env vars. Add both to `app/core/config.py` and `.env.example`.

### Price ingestion

- A scheduled background job (via `APScheduler`, already in `requirements.txt` but currently unused) polls Finnhub `/quote` for every distinct ticker held across all portfolios.
- **Intraday polling**, market-hours aware: only runs roughly 9:30am–4:00pm ET, Monday–Friday. No holiday calendar precision — just a weekday + time-window check. Off-hours, the scheduler simply doesn't fire.
- Default interval: **every 15 minutes** during market hours. (Adjustable; at free-tier rate limits of 60 req/min this has enormous headroom for a portfolio-project scale of tickers.)
- Each poll cycle:
  1. Fetch `/quote` for every distinct ticker across all holdings.
  2. Write a `PriceSnapshot` row per ticker.
  3. Update each `Holding.current_price_cents` / `last_priced_at` from the new quote — **Finnhub becomes the source of truth for current price**, not the last trade. (Trades still drive share count and cost basis — that logic is unchanged.)
  4. Recompute and write one `PortfolioSnapshot` row per portfolio (sum of that portfolio's holdings' market value, using current share counts).

### Historical backfill (Twelve Data)

- **Trigger**: a trade creates a *new* `Holding` for a ticker (first time it's held in that portfolio) **and** no `PriceSnapshot` row exists for that ticker anywhere in the app yet (first time it's ever been tracked, across all users/portfolios). Prevents redundant backfills and wasted API credits for a ticker someone else already tracks.
- **Runs synchronously**, inside the trade-creation request, immediately after the new `Holding` is created — matches the codebase's existing synchronous style; there's no background-task infrastructure yet and adding one just for this would be disproportionate. Trade-off, accepted: the *first* trade on a genuinely new ticker takes somewhat longer (one external API call, roughly 200–500ms) than a normal trade.
- **Failure is non-fatal to the trade.** A Twelve Data error (bad symbol, rate limit, network failure) is logged and swallowed — the trade and holding are created regardless; that ticker simply has no history until the next live Finnhub poll picks it up. The core operation (recording a trade) must never fail because of an enrichment step.
- **Fetches the most recent 30 daily closes** via Twelve Data's `/time_series` (`interval=1day`, `outputsize=30`). Each day's close becomes one `PriceSnapshot` row, timestamped at that day's 4:00pm ET (market close), converted to UTC for storage. Same `ON CONFLICT DO NOTHING` idempotency as the live poll cycle (Sprint 1's `_record_price_snapshot`).
- **Resolution seam, expected not a bug**: backfilled points are one-per-day; live Finnhub-polled points are intraday (multiple per day during market hours). A 1M chart will visibly shift from daily resolution (older, backfilled) to finer intraday resolution (recent, live) — that's correct behavior given the two different data sources, not a rendering glitch.
- **Bounded, not full history.** This is a fixed 30-day window, not since-inception backfill — YTD/ALL ranges remain out of scope (see below).

### Data model additions

```
PriceSnapshot
  id
  ticker            (str, indexed)
  price_cents       (int)
  as_of             (datetime, indexed)
  UNIQUE(ticker, as_of)

  Shared across all users/portfolios holding the same ticker — one row per
  ticker per poll cycle, not per holding.

PortfolioSnapshot
  id
  portfolio_id      (FK -> portfolios.id, indexed)
  total_market_value_cents (int)
  as_of             (datetime, indexed)
```

Both are pure history tables — nothing reads them except performance chart endpoints. New Alembic migration required.

### API additions

Following the existing ownership-scoped pattern (404 on cross-user access, service layer owns the logic):

| Method | Path | Notes |
|---|---|---|
| `GET` | `/portfolios/{portfolio_id}/performance?range=1D\|1W\|1M` | `PortfolioSnapshot` series for the chart |
| `GET` | `/portfolios/{portfolio_id}/holdings/{holding_id}/performance?range=1D\|1W\|1M` | `PriceSnapshot` series for that holding's ticker |

Ranges supported: **1D (intraday), 1W, 1M**. With the 30-day backfill, 1M is now meaningfully populated as soon as a ticker is first tracked, rather than needing weeks of live polling to accumulate. YTD/ALL remain explicitly out of scope — the backfill window is fixed at 30 days, not since-inception. Revisit once there's a reason to extend the window.

### Frontend

- **Chart library: Chart.js + vue-chartjs.**
- **Portfolio-level chart**: on `PortfolioDetailView`, above or near the holdings table.
- **Per-holding chart**: no new route. Clicking a holding row expands it in place (or opens a small popover/modal) to show that ticker's chart, scoped to the existing table — no new `HoldingDetailView` page for now.
- **P&L display**: alongside price data, show unrealized gain/loss in both **$ and %** vs. cost basis — per holding, and totaled for the portfolio. Computed from `avg_cost_basis_cents` vs. `current_price_cents`, which are already on the `Holding` record (no new endpoint needed for this part).

### Explicitly out of scope (v1)

- No backfill beyond the most recent 30 days (no full since-inception history).
- No YTD/ALL ranges.
- No holiday-aware market calendar (just weekday + time window).
- No per-holding detail page/route.
- No paid data plan on either Finnhub or Twelve Data.

---

## Feature 2: Embedded Analysis Agent

### Goal

An agent, embedded in the app, that analyzes a portfolio's holdings and performance on request and returns a written analysis. This is the primary "I can build and embed agents" portfolio piece — the mechanics matter more than the polish, and the build should stay legible to a first-time agent builder rather than get abstracted behind a framework.

### Runtime

- **Built against the Anthropic Messages API contract**, using the `anthropic` Python SDK (new dependency — not yet in `requirements.txt`).
- **Requests are routed to DeepSeek**, not Anthropic, via `ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic` (already set locally) and `ANTHROPIC_API_KEY` (already set locally) — both already present as env vars. DeepSeek offers an Anthropic-compatible endpoint; the SDK and request/response shape are the real Anthropic Messages API, only the backend model differs. This is a deliberate cost-saving choice for a repeatedly-demoed portfolio project — same agent-building mechanics you'd use with native Claude, cheaper inference.
- **Model:** `deepseek-chat` (DeepSeek-V3.2, non-reasoning, supports function calling).
- ⚠️ **Risk flag, not yet verified:** tool-calling behavior on DeepSeek's Anthropic-compatible endpoint hasn't been confirmed to match Claude's tool-use semantics exactly (forced `tool_choice`, multi-turn tool results, etc.). First backlog task should be a small spike proving a single tool-call round-trip works end-to-end before building the full loop.
- **No SDK-managed agent loop.** The tool-use loop (call model → inspect response for `tool_use` blocks → execute the matching Python function → send `tool_result` back → repeat) is hand-written in application code, on purpose, so every step of "what makes this agentic" is visible and readable — not hidden inside a framework.
- **Temperature: low** (proposed default `0.2`) — the point is grounded, consistent analysis of real data, not creative variation.
- **Loop safety cap:** hard limit of ~6 tool-call round trips per analysis before forcing a final text response, to bound latency/cost.

### Interaction model

- **One-shot, not conversational.** An "Analyze portfolio" button on `PortfolioDetailView` triggers a single request; the agent runs its tool loop server-side and returns one final report, rendered in a panel/modal.
- **Ephemeral — not persisted.** No `AgentReport` table. Re-running calls the agent again from scratch. (Chosen to avoid extra Neon/Railway storage and complexity for a portfolio project; can revisit later if wanted.)

### Tools

The agent gets a small, fixed toolset, each implemented as a plain Python function the loop dispatches to. **`portfolio_id` is never a tool parameter the model controls** — it's bound server-side from the authenticated request (same ownership check as existing routes), so the model can only ever see data for the portfolio the user actually opened. This mirrors the existing 404-on-cross-user-access pattern.

| Tool | Params (model-controlled) | Returns |
|---|---|---|
| `get_holdings` | *(none)* | Ticker, shares, avg cost basis, current price, unrealized P&L for every holding in this portfolio |
| `get_price_history` | `ticker`, `range` (`1D`\|`1W`\|`1M`) | `PriceSnapshot` series — server validates the ticker belongs to a holding in this portfolio before querying |
| `get_trade_history` | `ticker` (optional) | Trades for this portfolio, optionally filtered by ticker |

### Scope of reasoning

- The agent may use **portfolio data (via tools) plus its own general knowledge** (e.g., sector context, what a company does, general volatility characteristics) — it isn't restricted to only what the tools return.
- Because that edges toward opinion/commentary on real holdings, the system prompt should require the response to **stay analytical (what happened, why it might have happened, notable patterns) rather than prescriptive** (no "you should buy/sell X"), and the report should carry a brief, visible disclaimer that this isn't financial advice.

### Explicitly out of scope (v1)

- No conversational chat / multi-turn UI.
- No persistence of past analyses.
- No user-editable prompts or model/temperature settings from the UI.
- No non-portfolio tools (e.g., no live web search) — the general-knowledge component comes from the model's own training, not additional tool calls.

---

## Decisions log

Kept here for traceability — if you're wondering "why did we do it this way," it's probably answered below.

| Decision | Choice | Why |
|---|---|---|
| Price ingestion | Scheduled job | Enables real history for charts; on-demand-only would mean no meaningful chart |
| Historical backfill | Twelve Data, 30 daily closes, on first-ever tracking of a ticker | Finnhub free tier has no historical endpoint; Twelve Data's free tier genuinely includes daily `/time_series` (unlike Alpha Vantage's 25-req/day limit, too restrictive to be useful) — lets charts show real history immediately instead of waiting weeks for live polling to accumulate it. Bounded to 30 days to keep scope and API usage contained |
| Backfill execution | Synchronous, inside the trade-creation request | Matches existing synchronous codebase style; no background-task infra exists yet and building one just for this would be disproportionate. Accepted cost: first trade on a new ticker is slower |
| Price source of truth | Finnhub overwrites `current_price_cents` | The entire point of the feature is market-accurate value, not last-trade value |
| History storage | Separate `PriceSnapshot` (by ticker) + `PortfolioSnapshot` (by portfolio) tables | Avoids duplicating ticker history per user; portfolio rollup precomputed for fast chart reads |
| Poll cadence | 15 min, market-hours aware | Meaningful intraday movement without wasting calls overnight/weekends |
| Chart ranges | 1D / 1W / 1M only | YTD/ALL would need since-inception backfill, not just the fixed 30-day window |
| Holding chart placement | Expand-in-place on existing table | Avoids a new route/page for v1 |
| Chart library | Chart.js + vue-chartjs | Well-documented, easy Tailwind theming, sized right for this project |
| Agent capability | Tool-using loop, not single-shot prompt | This is the actual "agent" — the thing being demonstrated |
| Agent interaction | One-shot button, not chat | Keeps scope small; no conversation state to manage |
| Agent persistence | None (ephemeral) | Avoids added DB cost for a portfolio project |
| Agent build method | Hand-rolled loop against raw Messages API | User's first agent build — process must stay visible, not abstracted by an SDK |
| Agent backend | DeepSeek via Anthropic-compatible endpoint | Existing env vars, real cost savings, same API contract/mechanics as Claude |
| Agent knowledge scope | Portfolio data + general knowledge | More insightful output; mitigated with a "no prescriptive advice" system prompt constraint and disclaimer |
| Agent temperature | Low (~0.2) | Grounded, consistent analysis over creative variation |

---

## Open items to revisit later (not blocking v1)

- Whether to eventually persist agent analyses (`AgentReport` table) for a history view.
- Whether to add a per-holding detail page/route once there's more to put on it.
- Whether YTD/ALL ranges become worth adding once enough snapshot history exists.
- Whether DeepSeek's tool-calling parity holds up in practice, or whether the loop needs DeepSeek-specific handling.
- Whether to extend the Twelve Data backfill window beyond 30 days, or move backfill to a background task if the synchronous trade-creation delay becomes annoying.
