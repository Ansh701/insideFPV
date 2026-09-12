# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Confirmed by the assignment: React, TypeScript, Vite, and a FastAPI/PostgreSQL backend. Deployment targets are a static frontend on Vercel or Render and the API/database/cron on Render.

## Users

Primary users are drone builders in India who repeatedly check specialist electronics retailers for flight controllers, companion computers, Raspberry Pi boards, HATs, and carrier boards. A second explicit audience is the engineering evaluator, who needs to inspect system health, source failures, history, state transitions, and demo behavior quickly.

## Product Purpose

RotorWatch reduces repetitive stock checking. It monitors supported retailers politely, stores authoritative current state and immutable history, alerts users only on meaningful favorable transitions, and lets the same Telegram conversation search products or manage watches. Success means a trustworthy demo and an explainable, maintainable system—not maximum feature count.

## Positioning

The product’s distinctive mechanism is deterministic-first evidence tracking: retailer adapters produce auditable snapshots, ambiguous evidence alone reaches an ordered low-cost LLM failover chain, and user answers always come from stored or explicitly refreshed data.

## Operating Context

Users interact primarily through Telegram alerts and commands. The web interface is an operations console used to inspect products, watches, monitoring runs, failures, and alerts or to trigger a check. Product availability is volatile and retailer access or markup can fail independently.

## Capabilities and Constraints

- Supported retailers: Robu, ThinkRobotics, Zbotic, and Evelta.
- Normalized states: `IN_STOCK`, `OUT_OF_STOCK`, `PREORDER`, and `UNKNOWN`.
- Required seeded targets: Raspberry Pi 5, a Pi 5-compatible HAT, and Holybro Pixhawk 6X.
- Daily monitoring by default, configurable and invoked through the same service from cron, CLI, API, and demo mode.
- Telegram is complete first; WhatsApp is a documented future provider.
- No Redis, Celery, RAG, vector database, microservices, or browser scraping unless a retailer later proves it necessary.

## Brand Commitments

Brief-derived and binding: modern, premium, Gen-Z, technical, polished, clean, slightly futuristic, and drone/electronics inspired. Use restrained glass/liquid-glass surfaces, controlled transparency, premium gradients, rounded high-value cards, purposeful motion, and an intentional light-default/dark theme. Avoid rainbow color, excessive neon, unreadable transparency, childish gaming motifs, and chart decoration.

## Evidence on Hand

The repository contains captured/sanitized retailer fixtures and deterministic demo data. No customer testimonials, usage metrics, commercial claims, logo, or proprietary photography were supplied; the interface must not fabricate them. Dashboard values come from the backend API.

## Product Principles

1. Evidence before inference.
2. Favorable transitions, never initialization noise.
3. One failure must not collapse unrelated monitoring work.
4. Every status must communicate source and freshness.
5. Operational clarity outranks decorative dashboard density.

## Accessibility & Inclusion

The assignment requires semantic HTML, keyboard navigation, visible focus, sufficient contrast, meaningful async announcements, reduced-motion support, mobile-first responsiveness, and no horizontal overflow at 320px and wider.
