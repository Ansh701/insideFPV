# Drone Shopping Assistant Design

## Goal

Build a small, production-shaped modular monolith that monitors supported Indian electronics retailers, records immutable availability history, detects favorable state transitions, alerts Telegram users, and answers product/watchlist questions from authoritative PostgreSQL data.

## Architecture

FastAPI exposes public health/read APIs, a Telegram webhook, and admin-protected state-changing APIs. A reusable async monitoring service is called by the CLI, admin endpoint, cron job, and demo command. Retailer-specific adapters fetch and parse pages through a registry; structured data and deterministic rules run before the ordered Gemini, OpenAI, Anthropic fallback chain. SQLAlchemy 2.x and asyncpg persist products, snapshots, watches, runs, alerts, users, and processed Telegram update IDs.

The React/Vite admin UI is deliberately thin: dashboard, catalog, watchlist, monitoring runs, and alerts share one API client. The default light theme and intentional dark theme use a technical flight-console visual language with restrained glass surfaces, accessible contrast, responsive layouts, and explicit loading, success, error, and empty states.

## Core data flow

1. A scheduled/manual/demo trigger starts one monitor run.
2. Products are checked concurrently behind a small semaphore.
3. The adapter validates/canonicalizes its URL, fetches with timeout and conservative retry, hashes normalized evidence, and extracts a typed product state.
4. Ambiguous evidence alone reaches the ordered LLM failover service; all failures become `UNKNOWN`.
5. Every observation creates an immutable snapshot. First observation establishes a baseline; later favorable transitions create deduplicated alert rows.
6. Alert delivery happens after observation persistence, so Telegram failure cannot erase product truth.
7. Telegram chat commands and structured LLM intents invoke application services; neither the LLM nor the client accesses the database directly.

## Boundaries and safety

- Dynamic product URLs are limited to HTTPS/HTTP URLs on the four registered retailer domains; localhost, private, loopback, link-local, metadata, credentials, unsafe ports, redirects outside the allowlist, and dangerous schemes are rejected.
- Admin writes require `X-Admin-Secret`; Telegram webhooks use the Telegram secret header and update-ID idempotency.
- Public schemas never expose ORM entities or secrets. Structured logs exclude HTML, tokens, authorization headers, database credentials, and message bodies.
- No Redis, Celery, queue, microservice, RAG, vector store, browser automation, password auth, or provider voting is introduced.

## Retailer findings

- Robu: WordPress/WooCommerce-style product and category pages; product/catalog stock labels plus structured product markup are preferred.
- ThinkRobotics: Shopify product data exposes `available`, variants, prices in minor units, and SKU; visible stock text is an additional signal.
- Zbotic: WooCommerce-style price, SKU, `Add to cart`, `Out of Stock`, and category inventory labels.
- Evelta: catalog/product pages expose price, shipping text, and explicit quantity such as `21 in stock`/`Only 1 in stock`; missing quantity remains ambiguous.

Fixtures capture these evidence shapes. Live websites remain development-only checks and never gate CI.

## Testing and deployment

Pytest covers adapters, normalization/SSRF, change detection and deduplication, LLM failover, monitoring isolation, search, watchlists, chat, Telegram idempotency/delivery, API contracts, demo sequencing, migration, and seed behavior. Frontend tests cover API state rendering and key interactions; ESLint, TypeScript, and Vite production builds are required.

Deployment uses one Render FastAPI web service, managed PostgreSQL, one Render cron invoking the same monitor module, and a Vercel or Render static Vite build. Secrets stay in deployment environment settings.

## Scope choices

Telegram is complete; WhatsApp is an extension point only. Category discovery is bounded to configured category/search URLs and safe candidate-link extraction. Price snapshots are mandatory, while price-change notifications are intentionally deferred. PostgreSQL text similarity is used when available, with deterministic similarity fallback in test/demo environments.
