# RotorWatch

RotorWatch is a lightweight AI-assisted shopping and availability monitor for drone builders in India. It tracks products from Robu, ThinkRobotics, Zbotic, and Evelta; preserves immutable availability history; detects meaningful favorable transitions; sends Telegram alerts; and supports product search and watchlist operations through both chat and a thin operations console.

The engineering priority is deterministic evidence and graceful failure. Retailer markup is parsed before any LLM is considered. PostgreSQL remains the authority for status, price, history, and watches. AI converts ambiguous evidence or unrecognized natural language into validated application schemas; it never queries the database or performs a business action directly.

## Problem statement

Specialist drone and electronics stock changes unpredictably. A product can remain unavailable for weeks, become available for pre-order, or appear in a category page without warning. Repeated manual checks are slow and do not preserve history. RotorWatch performs polite, bounded checks and alerts only after a watched product makes a favorable transition.

## Features

- Four isolated retailer adapters with JSON-LD/embedded JSON first and retailer-specific rules second.
- Normalized `IN_STOCK`, `OUT_OF_STOCK`, `PREORDER`, and `UNKNOWN` states.
- Immutable snapshots, price history, SHA-256 content fingerprints, and monitor-run records.
- Baseline-first change detection: the first observation never creates a false restock alert.
- Deduplicated Telegram alerts whose delivery failure does not roll back stock truth, plus a protected bounded retry action.
- Ordered Gemini → OpenAI → Anthropic failover with one-provider-at-a-time execution.
- Deterministic chat commands and search that remain useful with no LLM credentials.
- Dynamic watch additions by catalog name or supported retailer URL.
- Bounded category discovery for Flight Controllers and Companion Computers, with deterministic relevance rules that reject obvious accessories and unrelated catalog items.
- Search by name, category, availability, price, retailer, and manufacturer, with typo suggestions.
- A connected React operations console for products, history, watches, monitor runs, failures, and alerts.
- Protected manual monitor action plus reusable scheduled CLI and deterministic demo commands.
- Light-default and intentional dark themes with locally persisted preference.
- SSRF controls, webhook verification, input validation, request IDs, security headers, and state-changing endpoint rate limits.

## Architecture

RotorWatch is a clean modular monolith. HTTP handlers are thin boundaries around reusable application services; the monitor is not embedded in a FastAPI request handler and the frontend never receives provider secrets.

```mermaid
flowchart TD
    U[Telegram user] --> TG[Telegram Bot API]
    B[Browser] -->|one public HTTPS origin| WEB
    subgraph WEB[Render Web Service: rotorwatch]
        API[FastAPI / Uvicorn]
        UI[Compiled React/Vite assets]
        UI -->|relative /api requests| API
    end
    API --> WH[Telegram webhook route]
    API --> REST[REST API routes]
    API -->|SPA fallback for client routes only| UI
    TG --> WH
    CRON[Render Cron / manual CLI] --> MON[Monitoring service]
    REST --> CHAT[Chat service]
    REST --> MON
    WH --> CHAT

    CHAT --> DETCMD[Deterministic intent parser]
    DETCMD -->|recognized| OPS[Validated application operations]
    DETCMD -->|unknown| LLM[LLM service]
    LLM --> GEM[Gemini]
    GEM -. provider failure .-> OA[OpenAI]
    OA -. provider failure .-> ANT[Anthropic]
    ANT -. provider failure .-> FALLBACK[Deterministic fallback]
    LLM --> OPS

    MON --> DISC[Bounded category discovery]
    MON --> REG[Retailer adapter registry]
    DISC --> REG
    REG --> ROBU[Robu adapter]
    REG --> THINK[ThinkRobotics adapter]
    REG --> ZB[Zbotic adapter]
    REG --> EV[Evelta adapter]
    ROBU --> FETCH[Safe async HTTP client]
    THINK --> FETCH
    ZB --> FETCH
    EV --> FETCH
    FETCH --> EXTRACT[Structured and deterministic extraction]
    EXTRACT -->|ambiguous only| LLM
    EXTRACT --> CHANGE[Snapshot and change detector]
    LLM --> CHANGE
    CHANGE --> DB[(PostgreSQL)]
    CHANGE --> ALERT[Alert dispatcher]
    ALERT --> TG
    OPS --> DB
    API --> DB
    CRON --> DB
```

The root multi-stage Docker build uses Node 22 only to compile `frontend/dist`, then copies those static files into a Python 3.12 slim runtime. Production contains no Node process or Vite development server. FastAPI owns the one public origin: API, health, readiness, webhook, and development-doc paths retain backend semantics, while fixed static assets and known client-side paths receive the React application.

### Data flow

1. A cron job, CLI command, admin request, chat check, or demo invokes `MonitorService.run()`.
2. Full scheduled/admin runs scan only the configured category pages, collect at most 50 adapter-recognized product links per category, and insert canonical unseen products.
3. Products are checked concurrently behind a small configurable semaphore.
4. The safe HTTP client validates scheme, retailer domain, resolved addresses, redirects, response size, timeout, and retry conditions.
5. The adapter prefers schema.org Product JSON-LD or embedded product/variant JSON, then deterministic site-specific selectors and wording. ThinkRobotics Shopify prices are parsed from the selected/default variant when available and from the main product price block otherwise.
6. Only an `UNKNOWN` deterministic result sends trimmed product evidence to the LLM service.
7. A validated snapshot is appended. The product's current projection is updated from that observation.
8. The new valid snapshot is compared with the previous valid snapshot. The first valid snapshot is a baseline.
9. Favorable transitions create one alert per active watch, guarded by a deterministic unique fingerprint.
10. Observations commit before outbound Telegram delivery. A failed delivery is recorded as `FAILED`; it cannot erase a true stock observation and can be retried through the protected admin action.
11. One failed retailer, product, category scan, LLM provider, or Telegram request does not stop unrelated products.

## Why these technologies

### FastAPI

FastAPI is not required because the project uses AI. It is a good fit because the application combines asynchronous retailer calls, Telegram webhooks, validated Pydantic request/response boundaries, external LLM calls, and a reusable scheduled service behind a small REST API.

### PostgreSQL

Products, retailers, users, watches, snapshots, alerts, and runs have strong relationships. PostgreSQL provides transactions, unique constraints, JSONB attributes, precise numeric prices, and `pg_trgm` support for fuzzy suggestions. MongoDB offers no clear advantage for this state-heavy relational workload.

### Telegram first

The assignment permits Telegram and/or WhatsApp. Telegram has a direct webhook contract, simple bot setup, and low demo friction. A small `MessagingProvider` boundary leaves room for a future WhatsApp implementation without weakening the complete Telegram path.

### Cron instead of Celery and Redis

Monitoring is low-frequency and configurable, daily by default. A separate, idempotent command invoked by Render Cron is easier to deploy, test, debug, and operate than Celery plus Redis. FastAPI workers do not start their own scheduler.

### No RAG or vector database

The current dataset is structured and transactional. Dominant operations are filters, relational joins, status, price, comparison, category, and time-ordered history. PostgreSQL is simpler and more deterministic than embeddings, a vector store, or RAG. Those tools would only become justified if the product later searches a large body of unstructured manuals or documentation semantically.

## Database design

The initial Alembic migration creates nine compact tables:

| Table | Purpose and important integrity rules |
| --- | --- |
| `retailers` | Supported source metadata; unique name and domain. |
| `products` | Canonical current product projection; unique canonical URL and retailer/external-id identity. |
| `product_snapshots` | Immutable status/price/evidence history, source/provider, content hash, timestamp, and isolated error. |
| `watchlist_items` | Persistent user/product watches; unique user/product pair prevents duplicates. |
| `category_watches` | Bounded source pages for Flight Controllers and Companion Computers; unique retailer/category/query. |
| `alerts` | Favorable transition events and delivery result; unique SHA-256 event fingerprint prevents duplicate notification creation. |
| `monitor_runs` | Trigger, timestamps, completion status, checked/changed/alert/error counts, and bounded error summary. |
| `telegram_users` | Minimum routing metadata: Telegram user ID, chat ID, optional public profile fields, and enabled state. |
| `processed_telegram_updates` | Unique Telegram `update_id` for webhook retry idempotency. |

All persisted timestamps are timezone-aware and UTC. The UI formats them in `Asia/Kolkata`. Prices use `Decimal`/PostgreSQL `NUMERIC`, not binary floating point. Product attributes use JSONB on PostgreSQL and portable JSON in tests.

`0001_initial_schema.py` also enables `pg_trgm` on PostgreSQL. Automated tests use SQLite only as an isolated fast service/API test database; PostgreSQL is the primary and deployment database, and clean-boot verification is performed against PostgreSQL 17.

## Product status and change detection

Retailer wording is normalized into one enum:

- `IN_STOCK`
- `OUT_OF_STOCK`
- `PREORDER`
- `UNKNOWN`

Ambiguous evidence remains `UNKNOWN`; it is never guessed into stock. Error snapshots are preserved for diagnostics but do not become the previous *valid* state used for favorable transition comparison. Product responses derive a safe `latest_check_error` from the newest snapshot (for example, a retailer HTTP 403 or timeout) while keeping internal exception detail out of the frontend.

Alerting transitions are:

| Previous valid state | New state | Event |
| --- | --- | --- |
| `OUT_OF_STOCK` or `UNKNOWN` | `IN_STOCK` | `BACK_IN_STOCK` |
| `PREORDER` | `IN_STOCK` | `BACK_IN_STOCK` |
| `OUT_OF_STOCK` or `UNKNOWN` | `PREORDER` | `PREORDER_OPENED` |
| First observation | Any state | No event; baseline only |
| Same state repeated | Same state | No event |

Price changes are retained naturally in snapshots. Price-change alerts are intentionally not part of the mandatory path.

The event fingerprint hashes user ID, product ID, previous snapshot ID, state transition, and current content hash with SHA-256. SHA-256 is used as a one-way fingerprint, not described as encryption.

## Retailer source architecture

`RetailerAdapter` owns source-specific behavior:

- `can_handle(url)`
- structured/deterministic `parse_product(html, url)`
- normalized content trimming
- SHA-256 fingerprinting
- bounded `discover_products(html, source_url, limit)`
- retailer name and domain

The registry resolves an adapter; monitor, watchlist, and discovery services contain no scattered domain conditionals. Adding a retailer requires:

1. Implement one adapter under `backend/app/sources/`.
2. Register it in `default_registry()`.
3. Add sanitized source fixtures and adapter tests.
4. Add supported category URLs only when their markup is reliable.

No monitor-service rewrite is required. Plain HTTP is used for every current source. There is no CAPTCHA bypass, authentication bypass, browser automation, or anti-bot workaround.

ThinkRobotics exposes two current storefront shapes. Variant products embed a Shopify JSON array with price values in paise; RotorWatch selects the variant referenced by the main add-to-cart form, falling back to the first advertised variant in source order. That price becomes `current_price`, while sanitized variant name, availability, price, and SKU values remain in product attributes. Products without variant JSON use the first selling-price value in `.product-main__price`. A higher crossed-out value is retained as `compare_at_price`; it never replaces the selling price. All persisted product prices use `Decimal` and currency `INR`. Compact commerce fields are included in the content fingerprint even though full scripts are removed.

Discovery is relevance-first rather than a general retailer crawl. Candidate URL slugs must deterministically match the configured watch category. Raspberry Pi boards and credible Jetson/SBC kits qualify as companion computers; actual HAT/carrier/interface boards use the HAT category; cables, cameras, SD cards, power supplies, Pico boards, screws, and similar accessories do not qualify. Existing history is not deleted. Successful monitoring corrects the current category projection from source titles, and the default product search excludes `Other`; an explicit `category=Other` query still retrieves retained records.

### Current sources and live development check

| Retailer | Adapter/fixture coverage | Limited live path checked on 12 Sep 2026 |
| --- | --- | --- |
| Robu | Structured and deterministic fixture parsing | `https://robu.in/product-category/raspberry-pi-5/` responded with HTTP 403 to the plain development client. Failure was isolated. |
| ThinkRobotics | Shopify variant JSON plus main-price fallback | Raspberry Pi 5, Pixhawk Pro 6C Kit, APM Pixhawk Power Module, Raspberry Pi AI HAT+, and one current pre-order page were reachable. Titles, `INR` prices, status, variants, and narrow categories parsed deterministically. |
| Zbotic | Structured and deterministic fixture parsing | `https://zbotic.in/product/holybro-pixhawk-6x-icm-45686/` responded with HTTP 403. Failure was isolated. |
| Evelta | Structured and deterministic fixture parsing | `https://evelta.com/raspberry-pi-5-with-2-4-8gb-ram/` responded with HTTP 403. Failure was isolated. |

The fixture tests are the repeatable contract; CI never depends on live retailers. The 12 Sep 2026 live check made eight sequential requests with no retries: five small representative ThinkRobotics checks and one check for each other retailer. ThinkRobotics yielded deterministic selling prices for in-stock, out-of-stock, pre-order, sale, and variant cases. Robu, Zbotic, and Evelta returned HTTP 403 to the plain client; these failures were isolated and were not bypassed. Run the development-only check with `python -m app.scripts.live_check`; it exits non-zero when any source is unavailable.

## Multi-provider LLM design

The common application contracts are validated Pydantic `ProductExtraction` and `ChatIntent` schemas. Monitoring and chat depend only on `LLMService`; provider routing lives entirely inside the LLM subsystem.

Provider priority is required and fixed:

```text
Gemini → OpenAI → Anthropic → deterministic fallback
```

- Gemini is primary because of the project preference, lightweight model availability, structured extraction capability, and cost profile.
- OpenAI is the independent first fallback for Gemini quota, rate-limit, timeout, credential, network, or outage failures.
- Anthropic is the final provider fallback when the first two cannot serve the request.

This is failover, not voting or load balancing. Providers are never called in parallel and execution stops at the first valid response. That avoids unnecessary cost, token use, and latency.

Each provider receives at most one conservative transient retry. A validation failure receives at most one inexpensive repair prompt; a second invalid response moves to the next configured provider. Transient failures can place the provider into a short process-local cooldown. No Redis is added for cooldown state.

Programming errors are not blindly treated as provider outages: unexpected exceptions propagate for diagnosis. Provider/network/rate/quota/server failures are classified by the provider boundary and may fail over.

Model names are configuration, not business logic:

```dotenv
GEMINI_MODEL=gemini-2.5-flash-lite
OPENAI_MODEL=gpt-5-mini
ANTHROPIC_MODEL=claude-haiku-4-5
```

These are the documented deployment defaults. Provider ordering, HTTP envelopes, schema validation, retry, repair, cooldown, and failover are tested without paid requests; the named hosted models were not called because no API credentials were supplied. Operators may replace them with currently available small structured-output-capable models. Individual keys are optional. Unconfigured providers are skipped without error.

When all configured providers fail, ambiguous product classification becomes `UNKNOWN`, a fallback snapshot is still saved, and remaining products continue. For chat, deterministic commands still work and an unrecognized message falls back to help instead of fabricating an answer.

### Where AI is used

- Ambiguous product evidence after structured and deterministic parsing cannot establish a status.
- Natural-language chat not already recognized by the deterministic command parser needs conversion into one supported intent.

### Where AI is not used

- Reading or writing PostgreSQL.
- Deciding authorization, URL safety, transition rules, alert identity, or Telegram routing.
- Deterministically parseable retailer pages.
- Product filters, fuzzy suggestions, status history, price comparison, or current-state answers.
- Arbitrary network access or SQL generation.

LLM evidence is stripped of scripts, styles, navigation, header/footer noise, duplicate whitespace, and capped at 12,000 characters. Provider free text is never persisted as database truth without schema validation.

## Telegram, chat, and watchlists

`POST /webhooks/telegram` validates Telegram's secret header when configured. A unique persisted `update_id` prevents Telegram retries from executing a business command twice. User/watch state commits before the outbound response; a response delivery failure returns a processed/failed-delivery acknowledgement without repeating the command.

Supported deterministic messages include:

```text
/help
/watchlist
/watch <name or supported URL>
/unwatch <name>
/status <name>
/history <name>
/check <name>

show flight controllers in stock
show companion computers under 15000
is Raspberry Pi 5 available?
show the history for Pixhawk 6X
watch Raspberry Pi 5
stop watching Raspberry Pi 5
show my watchlist
check Raspberry Pi 5 now
```

Structured LLM intent parsing additionally supports `COMPARE_PRODUCTS`. The application executes each validated intent. Status answers include stored status, price, retailer, last-checked time, and source URL; no model knowledge is presented as live inventory.

A user can add any existing catalog product by name or a product URL on a supported domain. Adding a new product needs no code change or deployment. Adding a new retailer does require an adapter because retailer evidence is source-specific. Duplicate watches are rejected by both service logic and a database uniqueness constraint. Removing a watch disables it rather than destroying history.

## SSRF and security controls

User-supplied product URLs are restricted to HTTP/HTTPS, supported retailer hostnames, standard ports, and paths without embedded credentials. Tracking parameters and fragments are removed during canonicalization. The client rejects localhost, loopback, RFC1918/private, link-local, multicast, unspecified, documentation, metadata-service, and other non-global addresses. DNS is validated before every request, and every redirect is canonicalized and resolved again to limit DNS rebinding/redirect attacks. Public well-known NAT64 addresses are accepted correctly.

Other controls include:

- Secrets loaded only from environment/deployment secret storage through Pydantic Settings.
- No provider key or bot token in frontend JavaScript, API responses, seed data, or logs.
- Constant-time comparison for admin and Telegram webhook secrets.
- Production rejects a placeholder/short admin secret and Telegram-without-webhook-secret configuration.
- The state-changing admin monitor endpoint requires `X-Admin-Secret`.
- Process-local per-IP/path rate limits protect state-changing endpoints without adding Redis.
- Production CORS is disabled by default because the browser and API share an origin; local development keeps an explicit Vite allowlist.
- Trusted-host middleware derives the exact Render hostname from `RENDER_EXTERNAL_HOSTNAME` and also accepts an explicitly configured custom-domain host.
- Request timeouts, redirect limits, and a 2 MB response cap protect retailer acquisition.
- ORM-bound parameters rather than LLM-generated or interpolated SQL.
- Request IDs plus CSP, permissions policy, `nosniff`, referrer policy, and frame-denial response headers.
- Generic production-safe internal errors; no stack trace, SQL, filesystem path, token, or environment dump in API responses.
- HTTPS/TLS is terminated at Render and used at the Telegram boundary.

API keys are not stored in PostgreSQL. Base64 is not used as security, and no custom cryptography is introduced.

## API

Development OpenAPI documentation is available at `/docs`; schema endpoints are disabled in production.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Process liveness; no dependency details. |
| `GET` | `/ready` | PostgreSQL readiness probe; returns 503 when unavailable. |
| `GET` | `/api/dashboard/summary` | Compact dashboard metrics and last run. |
| `GET` | `/api/products` | Paginated search and filters plus optional fuzzy suggestion. |
| `GET` | `/api/products/{id}` | One current product projection. |
| `GET` | `/api/products/{id}/history` | Immutable observation history. |
| `GET` | `/api/watchlist` | Active watches for a Telegram/demo user. |
| `POST` | `/api/watchlist` | Add by exactly one product name or supported URL. |
| `DELETE` | `/api/watchlist/{id}` | Disable one active watch. |
| `GET` | `/api/monitor/runs` | Latest runs and failure summaries. |
| `POST` | `/api/admin/monitor/run` | Protected full monitor/discovery run. |
| `GET` | `/api/alerts` | Latest transition and delivery records. |
| `POST` | `/api/admin/alerts/retry` | Protected bounded retry of failed Telegram alerts. |
| `POST` | `/api/chat` | Reuse Telegram chat behavior for demo/testing. |
| `POST` | `/webhooks/telegram` | Idempotent Telegram ingress. |

Search parameters are `query`, `category`, `availability`, `min_price`, `max_price`, `retailer`, `manufacturer`, `limit`, and `offset`. With no category, results default to Flight Controllers, Companion Computers, and HATs & Carrier Boards; pass `category=Other` explicitly to inspect retained unrelated/accessory records. Numeric price filters naturally exclude `NULL` prices. Product results include a sanitized latest-check explanation when the newest snapshot is an error. API models never expose ORM objects directly. Application-defined failures use an `error` object with a stable `code`, a human message describing what/why, and a recovery `action`.

## Frontend and UX

The React/TypeScript/Vite console is intentionally thin and calls the FastAPI API only. It provides Dashboard, Products, Watchlist, Monitoring, and Alerts views; product history drawer; optimistic-looking but server-confirmed watch actions; manual monitoring; health/failure summaries; and source links. Product Intelligence defaults to “All relevant categories,” keeps `Other` explicitly selectable, and exposes availability, category, retailer, minimum-price, and maximum-price filters. Unknown checks show “Last attempt” and a sanitized reason instead of implying live certainty.

Production requests are relative (`/api/...`) and therefore same-origin. Direct navigation and refresh work for `/products`, `/watchlist`, `/monitoring`, and `/alerts`; the browser history API keeps the address bar in sync. FastAPI's fallback never captures `/api`, `/health`, `/ready`, `/webhooks`, `/docs`, `/redoc`, `/openapi.json`, or `/assets` failures.

- Fast responses render directly without flashing a loader.
- A quiet initial state avoids loader flash under roughly one second.
- Known-layout long loads use a left-to-right animated skeleton after the threshold.
- The indeterminate monitor action uses changing factual stage text without fake percentages.
- Empty panels explain why they are empty and what to do next; zero failures is shown as a positive healthy state.
- Errors name the failure and recovery and preserve the last successful response when possible.
- Successful watch and monitor actions provide inline/toast-style feedback.
- Forms use labels, server and client validation, retained values, required-state gating, and a live URL length count.
- Keyboard focus, skip navigation, semantic headings, `aria-live`, explicit status text, and reduced-motion behavior are included.
- Light mode is default. Dark mode is deliberately designed and locally persisted.

The responsive shell was render-checked without document overflow at 320, 375, 430, 768, 1024, 1440, and 1920 pixels. The visual system is documented in `DESIGN.md`.

## Seed data

The repeatable seed creates:

- Four retailers.
- Raspberry Pi 5 (ThinkRobotics).
- Raspberry Pi 5-compatible HAT (Zbotic/Waveshare).
- Holybro Pixhawk 6X (Zbotic).
- Flight Controllers and Companion Computers category watches for all four retailers.
- One minimal local dashboard/demo Telegram identity (`telegram_user_id=0`).
- Three enabled initial watchlist items for that identity.

Rerunning the seed is safe; existing canonical products, category watches, users, and watch identities are not duplicated.

## Local setup

### Prerequisites

- Python 3.12+
- Node.js 20.19+ or 22.12+ (Vite 7 requirement)
- Docker Desktop, or a local PostgreSQL 17 instance

### 1. Configure and start PostgreSQL

```powershell
Copy-Item .env.example .env
docker compose up -d postgres
```

The compose file starts only PostgreSQL on `localhost:5432`. The development credentials in compose are local-only defaults; replace them outside local development.

### 2. Install, migrate, and seed the backend

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
alembic upgrade head
python -m app.scripts.seed
```

macOS/Linux activation is `source .venv/bin/activate`; all following Python module commands are otherwise identical.

### 3. Start FastAPI

```powershell
uvicorn app.main:app --reload
```

Check `http://localhost:8000/health`, `http://localhost:8000/ready`, and development docs at `http://localhost:8000/docs`.

### 4. Start the frontend

```powershell
Set-Location ..\frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api`, `/health`, `/ready`, and `/webhooks` to FastAPI at `http://127.0.0.1:8000`, preserving separate local development without production CORS coupling. `VITE_API_BASE_URL` is an optional local override in `frontend/.env.local`; the production build leaves it empty.

### 5. Optional combined production container

With PostgreSQL running and reachable from Docker Desktop:

```powershell
Set-Location ..
docker build -t rotorwatch .
docker run --rm -p 10000:10000 `
  -e APP_ENV=production `
  -e APP_BASE_URL=http://localhost:10000 `
  -e DATABASE_URL=postgresql+asyncpg://drone:drone@host.docker.internal:5432/drone_assistant `
  -e ADMIN_SECRET=local-container-only-change-this-12345 `
  rotorwatch
```

Open `http://localhost:10000`; that one process serves both the compiled console and API. The startup script migrates and seeds before accepting traffic. Use deployment secret storage rather than command-line values outside local development.

## Monitoring commands

Every command below reuses `MonitorService`.

Scheduled/manual CLI run, including bounded category discovery:

```powershell
Set-Location backend
python -m app.jobs.monitor
```

Protected admin run:

```powershell
$headers = @{ "X-Admin-Secret" = $env:ADMIN_SECRET }
Invoke-RestMethod -Method Post -Headers $headers http://localhost:8000/api/admin/monitor/run
```

`MONITOR_INTERVAL` documents the intended frequency and the deployment scheduler uses it operationally; the included Render cron is daily at 01:30 UTC (07:00 IST). Change the cron expression and keep `MONITOR_INTERVAL` aligned when deploying a different frequency.

## Deterministic demo mode

Demo mode replaces only the input HTML. It uses a JSON-LD fixture and the same adapter parse, snapshot, transition, alert creation, and Telegram dispatch path as production monitoring.

```powershell
$env:DEMO_MODE = "true"
python -m app.scripts.demo_monitor  # establishes OUT_OF_STOCK baseline
python -m app.scripts.demo_monitor  # transitions to IN_STOCK and creates alert
```

Demo mode refuses to run unless `DEMO_MODE=true` and also refuses to run when `APP_ENV=production`. With no Telegram token the real alert record is created and delivery is honestly marked `SKIPPED`; with a configured test bot/chat it travels through the real Telegram transport.

## Telegram configuration

1. Create a bot with BotFather and keep the token in deployment secret storage.
2. Set a high-entropy `TELEGRAM_WEBHOOK_SECRET`. On Render, the public URL is derived from `RENDER_EXTERNAL_URL`; set `APP_BASE_URL` only for a custom domain.
3. Register the webhook with Telegram:

```text
POST https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook
url=https://<rotorwatch-host>/webhooks/telegram
secret_token=<TELEGRAM_WEBHOOK_SECRET>
```

4. Send `/help` to the bot. The first valid message creates or updates only the minimum Telegram routing record.

Do not put `TELEGRAM_BOT_TOKEN`, any LLM key, or `ADMIN_SECRET` in Vite variables.

## Environment variables

See `.env.example` for a runnable template.

| Variable | Required | Purpose |
| --- | --- | --- |
| `APP_ENV` | Yes | `development`, `test`, or `production`. |
| `APP_BASE_URL` | No | Optional public origin override; otherwise localhost locally and `RENDER_EXTERNAL_URL` on Render. |
| `DATABASE_URL` | Yes | PostgreSQL URL; `postgres://` and `postgresql://` are normalized to asyncpg. |
| `CORS_ORIGINS` | Local/override | Optional exact cross-origin allowlist; unset production means same-origin CORS is disabled. |
| `TRUSTED_HOSTS` | Override | Optional accepted hosts; Render's exact external hostname is derived automatically. |
| `RENDER_EXTERNAL_URL` | Render-managed | Render-provided public URL; do not set manually. |
| `RENDER_EXTERNAL_HOSTNAME` | Render-managed | Render-provided exact hostname used by trusted-host validation; do not set manually. |
| `ADMIN_SECRET` | Production | Long random secret for state-changing admin actions. |
| `RATE_LIMIT_PER_MINUTE` | No | Per-process, per-client/path mutation limit; default 60. |
| `TELEGRAM_BOT_TOKEN` | Telegram | Server-side Bot API token. |
| `TELEGRAM_WEBHOOK_SECRET` | Telegram | Secret header verified on webhook ingress. |
| `GEMINI_API_KEY` | No | Enables primary LLM provider. |
| `GEMINI_MODEL` | No | Configurable primary small model. |
| `OPENAI_API_KEY` | No | Enables first provider fallback. |
| `OPENAI_MODEL` | No | Configurable first fallback small model. |
| `ANTHROPIC_API_KEY` | No | Enables final provider fallback. |
| `ANTHROPIC_MODEL` | No | Configurable final fallback small model. |
| `LLM_PROVIDER_TIMEOUT_SECONDS` | No | Per-call timeout; default 8. |
| `LLM_MAX_RETRIES` | No | Conservative retry count, validated at 0 or 1. |
| `LLM_PROVIDER_COOLDOWN_SECONDS` | No | Process-local transient-failure cooldown; default 60. |
| `MONITOR_INTERVAL` | No | Human-readable configured schedule intent; default `daily`. |
| `MONITOR_CONCURRENCY` | No | Product-check semaphore; default 5, maximum 20. |
| `REQUEST_TIMEOUT` | No | Retailer request timeout; default 12 seconds. |
| `REQUEST_MAX_RETRIES` | No | Retailer transient retries; default 1, maximum 2. |
| `USER_AGENT` | No | Polite identifiable retailer request agent. |
| `DEMO_MODE` | No | Explicit non-production demo guard; default false. |
| `VITE_API_BASE_URL` | Local frontend only | Optional dev API origin; empty production builds use the current origin. Never a secret. |

Any subset of LLM providers may be configured. With Gemini only, the chain ends in deterministic fallback. With no Gemini key, OpenAI becomes first. With only Anthropic, only Anthropic is called. With no keys, deterministic parsing, search, watchlists, history, and recognized commands still work.

## Tests and quality commands

Normal tests make no live retailer or paid LLM call.

```powershell
Set-Location backend
ruff format --check .
ruff check .
mypy app
pytest

Set-Location ..\frontend
npm run lint
npm run typecheck
npm run test -- --pool=threads --maxWorkers=1
npm run build
npm audit
```

Backend coverage includes all four fixture adapters; status parsing; baseline and favorable transitions; duplicate events; monitor isolation; discovery; every LLM failover/configuration/validation/timeout case; URL canonicalization and SSRF cases; watch CRUD; filters and typo suggestions; deterministic and LLM chat; Telegram ingress idempotency; outbound delivery success/failure; API health/readiness/admin protection; seed idempotency; and the real demo path.

## Deployment

### Recommended: one Render Blueprint

The root `render.yaml` creates one `RotorWatch` project with one `Production` environment containing exactly three resources: the public Docker web service `rotorwatch`, managed PostgreSQL `rotorwatch-db`, and native-Python daily cron `rotorwatch-daily-monitor`. In Render choose **New → Blueprint**, connect `https://github.com/Ansh701/insideFPV`, select branch `main`, keep the Blueprint path `render.yaml`, provide any `sync: false` secrets, and apply it.

The web image has two stages: Node 22 runs `npm ci` and `npm run build`; Python 3.12 slim installs the backend and receives only `frontend/dist`. Its production script runs `alembic upgrade head`, the idempotent seed, and then `exec uvicorn` on `0.0.0.0:${PORT:-10000}`. Render supplies `PORT`, `RENDER_EXTERNAL_URL`, and `RENDER_EXTERNAL_HOSTNAME`; do not duplicate them.

### Exact manual **New Web Service** screen

Use these values if creating the web service manually instead of applying the Blueprint:

| Render field | Exact value |
| --- | --- |
| Source repository | `https://github.com/Ansh701/insideFPV` |
| Name | `rotorwatch` |
| Project | `RotorWatch` |
| Environment | `Production` |
| Language / Runtime | `Docker` |
| Branch | `main` |
| Region | `Singapore` (same region as PostgreSQL) |
| Root Directory | Leave blank (repository root) |
| Dockerfile Path | `./Dockerfile` |
| Docker Build Context Directory | `.` |
| Docker Command | Leave blank; use the Dockerfile `CMD` |
| Compute / Instance Type | `Free` for evaluation |
| Health Check Path | `/health` |
| Pre-Deploy Command | Leave blank; startup performs migration and seed on the free-compatible path |
| Auto-Deploy | `On Commit` |
| Build Filters | Leave blank |
| Registry Credential | None |
| Persistent Disk | None; product state belongs in PostgreSQL |

Attach the managed database's internal connection string as `DATABASE_URL`. Configure these web-service variables exactly (values shown are defaults or value sources):

```dotenv
APP_ENV=production
DATABASE_URL=<rotorwatch-db internal connection string>
ADMIN_SECRET=<generated high-entropy secret, at least 24 characters>
TELEGRAM_BOT_TOKEN=<optional secret>
TELEGRAM_WEBHOOK_SECRET=<generated high-entropy secret>
GEMINI_API_KEY=<optional secret>
GEMINI_MODEL=gemini-2.5-flash-lite
OPENAI_API_KEY=<optional secret>
OPENAI_MODEL=gpt-5-mini
ANTHROPIC_API_KEY=<optional secret>
ANTHROPIC_MODEL=claude-haiku-4-5
LLM_PROVIDER_TIMEOUT_SECONDS=8
LLM_MAX_RETRIES=1
LLM_PROVIDER_COOLDOWN_SECONDS=60
MONITOR_INTERVAL=daily
MONITOR_CONCURRENCY=5
REQUEST_TIMEOUT=12
REQUEST_MAX_RETRIES=1
RATE_LIMIT_PER_MINUTE=60
USER_AGENT=RotorWatch/0.1 (+availability-monitor; contact=your-email@example.com)
DEMO_MODE=false
```

Do **not** set `PORT`, `RENDER_EXTERNAL_URL`, `RENDER_EXTERNAL_HOSTNAME`, `CORS_ORIGINS`, `TRUSTED_HOSTS`, or `VITE_API_BASE_URL` for the normal Render deployment. A custom domain is the exception: set `APP_BASE_URL=https://your-domain.example`; its hostname is then accepted exactly. Never expose provider, Telegram, database, or admin secrets through `VITE_` variables.

Create the cron in the same project/environment and region with Root Directory `backend`, runtime `Python`, Build Command `pip install .`, Start Command `python -m app.jobs.monitor`, and schedule `30 1 * * *` (01:30 UTC / 07:00 IST). Give it the same database URL, provider credentials/models, Telegram token, timeout/retry/concurrency settings, and `DEMO_MODE=false`. `render.yaml` wires these references automatically.

After deployment, verify the single URL at `/`, `/products`, `/api/dashboard/summary`, `/health`, and `/ready`, then register the Telegram webhook at `https://<rotorwatch-host>/webhooks/telegram`. No standalone static host, Node production process, Kubernetes, Redis, queue, or in-process scheduler is required.

## Idempotency and graceful degradation

| Duplicate/failure | Protection or behavior |
| --- | --- |
| Seed rerun | Canonical URL and natural-key lookups plus database uniqueness. |
| Duplicate product/watch | Unique canonical URL and user/product constraint. |
| Telegram webhook retry | Unique persisted `update_id`; duplicate returns without re-execution. |
| Retried monitoring event | Unique SHA-256 event fingerprint and nested transaction. |
| Admin double-click | State snapshots may repeat, but the same transition alert cannot duplicate. |
| LLM provider failover | Provider routing returns one validated intent/extraction before business execution. |
| One retailer/product failure | Error snapshot/run summary; other products continue. |
| Category discovery failure | Existing products are still monitored. |
| All LLMs fail | `UNKNOWN` or deterministic command fallback; monitoring continues. |
| Telegram fails | Observation remains committed; alert is marked failed. |
| PostgreSQL fails | `/ready` returns 503 and writes are not pretended successful. |
| Frontend request fails | Recoverable error or stale-data banner; no infinite spinner. |

## Known limitations and deliberate omissions

- Robu, Zbotic, and Evelta returned HTTP 403 to the limited plain-HTTP check from this development environment. The implementation does not bypass their controls. Their deterministic contracts are fixture-tested, and run-level/product-level failures are visible. Markup should be recaptured periodically from an allowed development context.
- Category URLs are seed configuration and can drift. Discovery is intentionally bounded and conservative, not a general crawler.
- Process-local rate limiting and LLM cooldown are appropriate to this assignment; multi-instance deployments would need a shared mechanism only after scale proves it necessary.
- Failed alerts can be retried in a bounded batch through the protected admin endpoint. Retry is intentionally operator-triggered rather than a new background queue or scheduler.
- Price history is stored, but price-change alerts are a bonus and are not implemented.
- The admin console uses a simple deployment secret rather than a user-authentication product. Full multi-admin auth is outside this take-home's core path.
- WhatsApp is not implemented. It can be added behind `MessagingProvider` after Telegram remains stable.
- Product search uses relational/fuzzy matching, not semantic document search. This is deliberate; no RAG/vector stack is present.
- Availability depends on public retailer evidence at check time and is displayed with freshness. RotorWatch does not promise retailer inventory correctness beyond that evidence.
- The configured Gemini/OpenAI/Anthropic model defaults were not live-called without credentials; normal tests use deterministic provider doubles and concrete HTTP-envelope tests, never paid APIs.

## Future improvements

1. Schedule the existing bounded failed-alert retry only if delivery volume warrants another operational job.
2. Add price-threshold watches using existing snapshot history.
3. Add authenticated multi-admin access only if the console becomes shared.
4. Periodically refresh sanitized fixtures and document retailer markup drift.
5. Add a WhatsApp provider without changing chat or monitoring services.
6. Introduce semantic documentation search only if large unstructured manuals become a real product requirement.

## Short demo sequence

1. Open the dashboard and show the three seeded watches and latest run health.
2. Set `DEMO_MODE=true`; run the demo once to establish `OUT_OF_STOCK` without an alert.
3. Run it again to produce `OUT_OF_STOCK → IN_STOCK`, one `BACK_IN_STOCK` event, and the Telegram transport result.
4. In Telegram, send `show flight controllers in stock`.
5. Send `show companion computers under 15000`.
6. Send `is Raspberry Pi 5 available?` and point out status, price, source, and freshness.
7. Send `watch <supported product URL>`, then `show my watchlist`.
8. Optionally run the mocked failover test showing Gemini unavailable and OpenAI succeeding; no key appears in the recording.

This sequence demonstrates the production change detector rather than a fake alert shortcut.
