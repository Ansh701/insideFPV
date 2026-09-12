# Drone Shopping Assistant Implementation Plan

> **For agentic workers:** Execute inline in this session. Use test-driven development for behavior and verification-before-completion for every completion claim.

**Goal:** Deliver the complete, locally runnable monitoring, Telegram/chat, admin UI, demo, and deployment-ready documentation requested in the approved assignment.

**Architecture:** A clean FastAPI modular monolith owns all business logic and PostgreSQL state. A thin React/Vite client consumes typed REST responses; cron, CLI, demo, and admin calls converge on one async monitor service.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, asyncpg, httpx, BeautifulSoup/lxml, pytest, React 19, TypeScript, Vite, CSS.

**Spec:** `docs/superpowers/specs/2026-09-11-drone-shopping-assistant-design.md`

## Global constraints

- PostgreSQL is the primary persistent database; SQLite may be used only for fast isolated tests.
- Deterministic extraction always precedes LLM use.
- LLM order is Gemini, OpenAI, Anthropic, then deterministic fallback; providers are never called in parallel.
- Monitoring concurrency, interval, HTTP timeout, retry, model, and cooldown settings are environment-driven.
- All four retailer adapters, SSRF controls, baseline/change logic, Telegram idempotency, admin protection, demo flow, and requested UX states are mandatory.

### Task 1: Foundation and schema

**Files:** `backend/pyproject.toml`, `backend/app/config.py`, `backend/app/db.py`, `backend/app/models.py`, `backend/alembic.ini`, `backend/migrations/`, foundation tests.

**Produces:** `Settings`, async SQLAlchemy engine/session dependency, status/run/alert enums, eight core tables plus processed Telegram updates, clean Alembic migration, and repeatable seed service.

- [ ] Write configuration/model/seed tests and confirm missing behavior fails.
- [ ] Implement typed settings, schema, migration, and seed; run focused tests.

### Task 2: Safe retailer acquisition

**Files:** `backend/app/sources/`, `backend/app/services/url_security.py`, sanitized HTML fixtures, adapter and SSRF tests.

**Produces:** `RetailerAdapter`, `AdapterRegistry`, four adapters, `ProductExtraction`, URL canonicalization, safe DNS/redirect validation, async timeout/retry fetch, and bounded category discovery.

- [ ] Write fixture parser and malicious URL tests; confirm red.
- [ ] Implement shared structured extraction and retailer-specific evidence rules; run focused tests.

### Task 3: LLM service

**Files:** `backend/app/services/llm/`, LLM failover tests.

**Produces:** common `LLMProvider` contract, typed provider responses, ordered configured-provider selection, one retry, one repair, transient/permanent failure classification, cooldown, and deterministic classification/chat fallback.

- [ ] Write the twelve required failover/schema/timeout tests; confirm red.
- [ ] Implement minimal HTTP providers and orchestration; run focused tests.

### Task 4: Monitoring and alert state machine

**Files:** `backend/app/services/monitor.py`, `change_detection.py`, `alerting.py`, `backend/app/jobs/monitor.py`, monitor/change tests.

**Produces:** reusable monitor pipeline, SHA-256 fingerprints, immutable snapshots, first-observation baseline, favorable transitions, event fingerprints, per-product error isolation, persisted run metrics, and delivery-after-persistence.

- [ ] Write baseline, transition, duplicate, retailer-failure, LLM-down, and Telegram-failure tests; confirm red.
- [ ] Implement state machine and reusable entry point; run focused tests.

### Task 5: Search, watchlist, chat, Telegram, and REST

**Files:** `backend/app/services/{search,watchlist,chat}.py`, `backend/app/messaging/`, `backend/app/api/`, `backend/app/main.py`, API/service tests.

**Produces:** filtered/fuzzy product search, URL/name watch management, factual status/history/compare/check responses, deterministic slash and natural command parser, Telegram webhook idempotency, outbound transport, typed pagination/error responses, readiness, and admin authorization.

- [ ] Write watchlist, search, chat, webhook, outbound, and API tests; confirm red.
- [ ] Implement services and routes; run focused then full backend tests.

### Task 6: Deterministic demo

**Files:** `backend/app/scripts/demo_monitor.py`, demo fixtures/state, demo tests.

**Produces:** repeatable OOS baseline then in-stock transition through the production monitor/change/alert pipeline, guarded by demo mode.

- [ ] Write sequence and production-guard tests; confirm red.
- [ ] Implement demo fetch injection and command; run focused tests.

### Task 7: Responsive admin UI

**Files:** `frontend/` React/Vite application, UI tests, `PRODUCT.md`, final `DESIGN.md`.

**Produces:** flight-console dashboard, product/search/history, watchlist, monitoring/failures, alerts, manual monitor action, theme persistence, onboarding, inline validation, accessible responsive navigation, and loading/success/error/empty states.

- [ ] Write component behavior tests and confirm red.
- [ ] Implement API client and UI; run tests, lint, type-check, build, and bounded desktop/mobile visual inspection.

### Task 8: Operations and documentation

**Files:** `README.md`, `.env.example`, `docker-compose.yml`, Dockerfiles, `render.yaml`, security headers/static config.

**Produces:** accurate Mermaid architecture, complete local/demo/Telegram/deployment guide, extension and trade-off documentation, simple PostgreSQL/web/cron deployment configuration, and no committed secrets.

- [ ] Add operational files and verify their commands against the repository.
- [ ] Scan for placeholders/secrets and align documentation to measured results.

### Task 9: Final verification

**Produces:** recorded actual results for backend format/lint/type/tests, migration+seed on clean PostgreSQL when available, FastAPI boot/health/readiness, manual/demo monitor, frontend lint/type/test/build, live retailer reachability checks, and responsive UI screenshots.

- [ ] Run every applicable quality gate from a clean state and investigate failures at their root cause.
- [ ] Report unavailable environment gates explicitly—never as successful—and provide exact commands for the reviewer.
