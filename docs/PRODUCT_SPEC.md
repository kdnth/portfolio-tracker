# Product Spec: Performance Tracking + Embedded Analysis Agent

Status: draft, pending review
Last updated: 2026-08-21

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
- **Fetches hourly bars, not daily.** Twelve Data's `/time_series` (`interval=1h`, `outputsize` sized to cover the 30-day window). Verified live against our own free-tier key: a single call comfortably returns 3+ months of hourly history — no extra API cost over the daily call this used to make. Each bar becomes one `PriceSnapshot` row, timestamped using **the bar's own reported `datetime`** (parsed in the exchange's timezone from the response's `meta.exchange_timezone`, converted to UTC) — never a synthesized "market close" time. Same `ON CONFLICT DO NOTHING` idempotency as the live poll cycle (Sprint 1's `_record_price_snapshot`).
- **Today is never backfilled.** Twelve Data's entry for the current, not-yet-closed trading day is a *provisional* bar reflecting trading so far, not a real close — confirmed live: mid-session, it was byte-identical to the latest intraday bar. Backfill only writes bars for strictly completed prior days (in the exchange's local date); live Finnhub polling owns "today" exclusively for any actively-tracked ticker. This is what actually fixes a real production bug: the old daily-bar approach stamped every entry with a fixed 4pm-ET timestamp assuming a completed day, which for "today" meant a provisional, not-actually-final price got timestamped hours into the future relative to real time.
- **Bounded, not full history.** 30-day window (confirmed sufficient at hourly granularity in one API call) — no full since-inception backfill. YTD/ALL ranges remain out of scope (see below).

### Chart range behavior (canonical — read this before touching chart code)

Written down after a real production incident made clear this needed to be an explicit contract, not something implied by whatever the code happened to do: backfilled "today" data got a future timestamp (fixed above), and portfolio 1W/1M silently rendered the exact same narrow window as 1D with no indication anything was wrong.

**Holding charts** (ticker price, `PriceSnapshot`-backed):

| Range | Shape | Source | Notes |
|---|---|---|---|
| 1D | Single line, one point per sample | Live Finnhub polls only (15-min intervals, market hours) | Unchanged — already correct. Never touches backfilled data. |
| 1W | **Four lines**: open / close / top / bottom, one point per calendar day | `PriceSnapshot` rows for that ticker (backfill + live, whichever exist), grouped by calendar day in the exchange's local timezone | open = that day's first row's price, close = last row's price, top/bottom = max/min across that day's rows. |
| 1M | Same four-line shape as 1W, same per-day aggregation, wider date range | Same | Not a different code path from 1W — same aggregation, just a longer window. |

A day covered only by hourly backfill has ~7 samples to derive top/bottom from; a day covered by live 15-min polling has far more. Top/bottom get more accurate purely as a side effect of how long the ticker's been actively tracked — not a special case to code for, just fewer samples to work with on older days.

**The 1W/1M four-line view carries a visible disclaimer**, not just a tooltip aside: open/close/top/bottom are *derived from available samples*, not exact intraday records — a brief spike or dip that occurred and reversed within one backfilled hour, or within one live-polling gap, won't show up in top/bottom.

**Today's row on the 1W/1M holding chart is never treated as a complete day** — a real production incident showed the four lines were only visually distinct on the most recent day, because every other day's aggregation was over an hourly-or-denser sample set while "today" was mid-session and noisy. Handling is one of three states, decided server-side against **US Eastern time — never the viewer's local timezone**, since market hours are a property of the exchange, not the viewer:

| State | Behavior |
|---|---|
| Before market open (or a non-trading day) | Today is **omitted entirely** from the 1W/1M series — nothing real has happened yet. |
| Market open, not yet closed | Today is included with a real `open` (first sample) and a live-recomputed `high`/`low` (running max/min over whatever samples exist so far, recomputed fresh on every request, never cached) — but **`close_cents` is `null`**. There is no real close for a session still in progress; showing the latest live poll as if it were one would misrepresent an in-progress session as a settled value. |
| Market closed | Today is fully complete, exactly like any historical day — real `close` = the last sample of the day. |

The frontend renders a `null` `close_cents` as a genuine gap in the "Close" line (`spanGaps: false`), not a value bridged from yesterday's close.

**Portfolio charts** (`PortfolioSnapshot`-backed):

| Range | Shape | Source | Notes |
|---|---|---|---|
| 1D | Single line | `PortfolioSnapshot` rows within the last 24h | Unchanged. |
| 1W | Single line, **no OHLC treatment** | `PortfolioSnapshot` rows within the last 7 days | No four-line view — there's no per-portfolio backfill to derive open/close/top/bottom from. Just whatever real snapshots exist. |
| 1M | Single line, same as 1W | `PortfolioSnapshot` rows within the last 30 days | Same. |

**Portfolio-level data has no backfill mechanism at all** — `PortfolioSnapshot` only ever accumulates forward from whenever tracking or trading began (scheduled polls, plus the trade-time snapshot added after the "graph doesn't update on a new holding" bug). A portfolio tracked for only an hour shows an hour of real data for *every* range, including 1M, until real time actually passes. **This is accepted, not a bug** — see "Explicitly out of scope" for the deferred alternative (retroactively computed history).

**"Not enough data yet" state (both chart types)**: when the real data span for the selected range is too short to be meaningful, show an explicit message in place of the chart rather than silently rendering something that's technically correct but reads as broken. **Threshold: ceil(range ÷ 4) days of actual data span** — 1W requires at least **2 days**, 1M requires at least **7 days** (anchored to 28, the shortest calendar month, not our internal 30-day window: `ceil(28/4) = 7`). Below that, show the message instead of the chart. Most common case: portfolio 1W/1M on a newly-tracked portfolio; also applies to a holding chart where backfill failed and too little live history has accumulated since. 1D has no such threshold — it's already correct and not subject to this state.

**1W/1M must never render an hourly-granularity axis, on either chart type, regardless of how sparse the underlying data is.** Left to auto-detect, Chart.js's time scale picks axis granularity from the actual span of whatever data came back — a chart covering only a few real hours (e.g. a portfolio tracked since this morning, or a holding whose backfill failed) would render hourly ticks and look exactly like a broken 1D chart. The x-axis unit is forced to `'day'` whenever the selected range isn't 1D. This is independent of, and in addition to, the "not enough data" threshold above: that threshold hides charts that are too sparse to be meaningful at all, but the axis itself must never fall back to hourly even for a chart that does clear the threshold.

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
| `GET` | `/portfolios/{portfolio_id}/performance?range=1D\|1W\|1M` | `PortfolioSnapshot` series — always a flat `{as_of, total_market_value_cents}` list, regardless of range. See "Chart range behavior." |
| `GET` | `/portfolios/{portfolio_id}/holdings/{holding_id}/performance?range=1D\|1W\|1M` | `PriceSnapshot`-derived series. **Shape depends on range**: 1D returns a flat `{as_of, price_cents}` list; 1W/1M return one row per calendar day, `{date, open_cents, close_cents, high_cents, low_cents}`. See "Chart range behavior." |

Ranges supported: **1D (intraday), 1W, 1M**. YTD/ALL remain explicitly out of scope — the backfill window is fixed at 30 days, not since-inception.

### Frontend

- **Chart library: Chart.js + vue-chartjs.**
- **Portfolio-level chart**: on `PortfolioDetailView`, above or near the holdings table. Always a single simple line, all ranges — see "Chart range behavior."
- **Per-holding chart**: no new route. Clicking a holding row expands it in place to show that ticker's chart, scoped to the existing table — no new `HoldingDetailView` page for now. Renders as a single line (1D) or four lines — open/close/top/bottom (1W/1M) — per "Chart range behavior," with a visible disclaimer on the four-line view.
- **"Not enough data yet" state**: shown instead of a chart when the real data span doesn't meaningfully cover the selected range, on both chart types.
- **P&L display**: alongside price data, show unrealized gain/loss in both **$ and %** vs. cost basis — per holding, and totaled for the portfolio. Computed from `avg_cost_basis_cents` vs. `current_price_cents`, which are already on the `Holding` record (no new endpoint needed for this part).

### Explicitly out of scope (v1)

- No backfill beyond the most recent 30 days (no full since-inception history).
- No YTD/ALL ranges.
- No holiday-aware market calendar (just weekday + time window).
- No per-holding detail page/route.
- No paid data plan on either Finnhub or Twelve Data.
- No retroactive computed portfolio history (deriving historical portfolio value from historical share counts × backfilled ticker prices) — portfolio 1W/1M is limited to real accumulated `PortfolioSnapshot` history only, with an explicit "not enough data yet" state rather than a fabricated chart. Revisit if this limitation becomes annoying enough to justify the added complexity (see "Open items").

---

## Feature 2: Embedded Analysis Agent

### Goal

An agent, embedded in the app, that analyzes a portfolio's holdings and performance on request and returns a written analysis. This is the primary "I can build and embed agents" portfolio piece — the mechanics matter more than the polish, and the build should stay legible to a first-time agent builder rather than get abstracted behind a framework.

### Runtime

- **Built against the Anthropic Messages API contract**, using the `anthropic` Python SDK.
- **Model: Claude Haiku 4.5** (`claude-haiku-4-5-20251001`), extended thinking off — real Anthropic API, using existing prepaid credits rather than DeepSeek. `ANTHROPIC_BASE_URL` defaults to `https://api.anthropic.com` (optional in config, can be overridden).
- **Planned pivot to DeepSeek later**, once those credits run out — `ANTHROPIC_BASE_URL` was originally going to point at DeepSeek's Anthropic-compatible endpoint for cost savings on a repeatedly-demoed project. That's still the eventual plan, just not the starting point. `ANTHROPIC_BASE_URL` stays a configurable setting specifically so that pivot is a one-line env var change, not a code change. When it happens, the tool-calling smoke test (below) needs re-running against DeepSeek specifically — passing against real Claude doesn't guarantee DeepSeek's Anthropic-compatible endpoint matches tool-use semantics exactly.
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

## Feature 3: Analysis quota, RBAC, and public landing page

### Goal

Two additions once the agent was live: (1) a daily cap on analyses so a portfolio-piece demo doesn't run up real Anthropic spend if someone hammers the button, with a way for the owner to exempt themselves for testing; (2) a public landing page — a rundown of what the app does, links to login/register, and a live analysis demo against a fixed example portfolio so a visitor can see the actual agent output without creating an account.

### Authenticated analysis quota

- **3 analyses per user per day.** Counted from a new append-only `AnalysisRequestLog` table (`user_id`, `portfolio_id`, `created_at`) — one row per analysis actually run (not per attempt that got rejected by the quota).
- **Resets at a fixed calendar boundary: UTC midnight.** Not a rolling 24h window. Simple to reason about and to query (`count(*) where user_id = ? and created_at >= start_of_today_utc`); the "burn 3 right before midnight, get 3 more a minute later" edge case is accepted as a non-issue at this app's scale.
- **Enforced in `analyze_portfolio_route`**, before calling `analyze_portfolio`: count today's rows for this user, reject with `429` if `>= 3` (unless admin — see below). The rejection response states the limit and that it resets at UTC midnight.
- **Scope: per user, across all of that user's portfolios** — not per-portfolio. Three analyses total per day, on whichever portfolios they ask about.

### RBAC: `is_admin` flag (not a full role system)

- A single `is_admin: bool = False` column on `User`. No roles table, no permissions framework — the only thing it currently does is bypass the analysis quota. Deliberately minimal: the actual need is "let the owner test past 3/day," not a general permissions system nothing else currently asks for.
- **No self-serve admin UI.** Toggled via a one-off script (same shape as `scripts/rebackfill_stale_tickers.py`) run directly against the DB — this is a single-operator app, a UI for granting yourself admin would be pure overhead.

### Public landing page

- **New public route at `/`.** Currently `/` is the authenticated app shell's mount path (gated, redirects anonymous visitors to `/login`); that gets restructured so the authenticated app moves to `/portfolios` as its own top-level route (all existing URLs — `/portfolios`, `/portfolios/:id` — are unchanged, only the parent route's own path changes), freeing `/` for the new public `LandingView`. An authenticated visitor landing on `/` is redirected straight to `/portfolios` (same `guestOnly` pattern already used for `/login`/`/register`), since the landing page is for prospective/anonymous visitors.
- **Content:** a short rundown of what the app does (performance tracking + the analysis agent), and links to `/login` and `/register`.
- **Live demo, not a static screenshot.** The landing page renders one fixed, seeded demo portfolio (holdings + performance chart, via new public read endpoints reusing the existing schemas/components) and a real "Analyze" button that calls the real agent against that same demo portfolio — this is a portfolio piece demonstrating a real tool-using agent, so the demo should actually be one, not a captured transcript.
- **Demo portfolio is real data, not a mocked code path.** A dedicated seed script (`scripts/seed_demo_portfolio.py`) creates one fixed demo user/portfolio/holdings/trades. The demo analyze endpoint calls the exact same `analyze_portfolio()` function real users hit, just bound to this fixed `portfolio_id` (from config) instead of an authenticated user's own portfolio — no separate code path to keep in sync.

### Demo endpoint rate limiting (unauthenticated — no accounts to key off)

- **2 analyses per day, per visitor, keyed by IP address.** Tracked in a new `DemoAnalysisRequestLog` table (`ip_address`, `created_at`), same UTC-midnight reset as the authenticated quota.
- **Accepted limitation: IP is a leaky identity.** Shared/NAT'd networks (offices, some mobile carriers) can collide with each other under one IP, and it's trivially bypassed by switching networks or using a VPN. This is a known, accepted trade-off for a portfolio-piece demo, not a security boundary — chosen over per-visitor tracking without accounts being possible any more robustly than this.
- **Must read the real client IP through Railway's proxy**, not the proxy's own address — use the first hop of `X-Forwarded-For` when present, falling back to the raw connection address otherwise. (This app has hit proxy-related surprises in prod before — Neon's pooling behavior, `preDeployCommand` — so this gets called out explicitly rather than assumed to just work.)
- Each demo analysis call still runs the same bounded tool-loop (max 6 rounds, 1,500 max tokens) as any authenticated analysis, so the worst-case cost of a single call is already capped regardless of this endpoint's exposure.

### Explicitly out of scope (v1)

- No self-serve admin UI or general role/permission system — just the one `is_admin` bypass.
- No CAPTCHA or bot-detection on the demo endpoint beyond IP-based counting.
- No per-portfolio analysis quota — the 3/day limit is per user, total.
- No email/notification when a user hits their quota — just the `429` response, surfaced in the UI.

---

## Decisions log

Kept here for traceability — if you're wondering "why did we do it this way," it's probably answered below.

| Decision | Choice | Why |
|---|---|---|
| Price ingestion | Scheduled job | Enables real history for charts; on-demand-only would mean no meaningful chart |
| Historical backfill | Twelve Data, hourly bars (not daily), 30-day window, excludes today, on first-ever tracking of a ticker | Finnhub free tier has no historical endpoint at all (confirmed live: 403 on our own key, any resolution). Twelve Data's free tier includes hourly `/time_series` at the same cost as daily (confirmed live: 3+ months of hourly history in one call) — enables the 1W/1M four-line view. Excluding today avoids backfilling a provisional, not-yet-real closing price with a synthesized future timestamp — confirmed live as the root cause of a real production bug (a snapshot timestamped hours ahead of actual time) |
| Backfill execution | Synchronous, inside the trade-creation request | Matches existing synchronous codebase style; no background-task infra exists yet and building one just for this would be disproportionate. Accepted cost: first trade on a new ticker is slower |
| Price source of truth | Finnhub overwrites `current_price_cents` | The entire point of the feature is market-accurate value, not last-trade value |
| History storage | Separate `PriceSnapshot` (by ticker) + `PortfolioSnapshot` (by portfolio) tables | Avoids duplicating ticker history per user; portfolio rollup precomputed for fast chart reads |
| Poll cadence | 15 min, market-hours aware | Meaningful intraday movement without wasting calls overnight/weekends |
| Chart ranges | 1D / 1W / 1M only | YTD/ALL would need since-inception backfill, not just the fixed 30-day window |
| Holding chart 1W/1M shape | Four derived lines (open/close/top/bottom) per calendar day, not one point/day, not raw hourly | Directly answers "show as much data as possible" without a single daily-close line hiding all intraday movement, or a raw hourly line that's visually noisy at a 30-day scale. Explicit disclaimer since top/bottom are sampled, not exact |
| Portfolio chart historical depth | Real accumulated `PortfolioSnapshot` history only, no backfill; explicit "not enough data yet" state instead of a misleadingly narrow chart | No backfill mechanism exists for portfolio-level rollups (would require deriving historical value from historical share counts × backfilled prices — real feature work, deferred, see "Open items") |
| Holding chart placement | Expand-in-place on existing table | Avoids a new route/page for v1 |
| Chart library | Chart.js + vue-chartjs | Well-documented, easy Tailwind theming, sized right for this project |
| Agent capability | Tool-using loop, not single-shot prompt | This is the actual "agent" — the thing being demonstrated |
| Agent interaction | One-shot button, not chat | Keeps scope small; no conversation state to manage |
| Agent persistence | None (ephemeral) | Avoids added DB cost for a portfolio project |
| Agent build method | Hand-rolled loop against raw Messages API | User's first agent build — process must stay visible, not abstracted by an SDK |
| Agent backend | Real Anthropic API, Claude Haiku 4.5, no extended thinking | Existing prepaid Anthropic credits available; use those before pivoting to DeepSeek for ongoing cost savings once they're spent. `ANTHROPIC_BASE_URL` stays configurable so that pivot is a one-line env var change |
| Agent knowledge scope | Portfolio data + general knowledge | More insightful output; mitigated with a "no prescriptive advice" system prompt constraint and disclaimer |
| Agent temperature | Low (~0.2) | Grounded, consistent analysis over creative variation |
| Analysis quota scope/reset | 3/user/day, fixed UTC calendar day | Simple to reason about and query; per-user (not per-portfolio) matches how the limit was actually asked for |
| Admin exemption | Single `is_admin` boolean, no role system | Only need is bypassing this one quota for testing; a full RBAC system would be unused complexity |
| Demo endpoint quota | 2/IP/day, not a global site-wide cap | Chosen over a global cap despite IP being a leaky identity without real accounts — accepted trade-off for a demo, not a security boundary |
| Demo portfolio | Real seeded DB row, same `analyze_portfolio()` code path as authenticated users | Avoids a second, divergent "fake" code path just for the demo |

---

## Open items to revisit later (not blocking v1)

- Whether to eventually persist agent analyses (`AgentReport` table) for a history view.
- Whether to add a per-holding detail page/route once there's more to put on it.
- Whether YTD/ALL ranges become worth adding once enough snapshot history exists.
- When to pivot from Claude Haiku 4.5 to DeepSeek (once prepaid Anthropic credits run out), and whether DeepSeek's tool-calling parity holds up when that happens.
- Whether to build retroactive computed portfolio history (deriving past portfolio value from historical share counts × backfilled ticker prices) if the "portfolio charts have no backfill" limitation becomes annoying enough to justify the complexity.
- Whether to move backfill to a background task if the synchronous trade-creation delay (now a bit longer, fetching hourly instead of daily bars) becomes annoying.
