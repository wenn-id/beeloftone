# Production Foundation Implementation Plan

> Execution: inline in this session, using executing-plans and test-driven-development. The user has requested coding now following the production tracking proposal.

**Goal:** Provide a runnable, persistent API for internal production tracking.

**Architecture:** FastAPI routes call a small SQLite-backed production service. Atomic ledger transactions preserve quantities and an authenticated audit trail.

**Tech Stack:** Python 3.12+, FastAPI, uvicorn, SQLite, unittest, HTTPX TestClient.

**Spec:** `docs/design.md`

## Constraints

All work lives in this new project. No existing repository or business data is modified. No public deployment. All production quantities are positive integer pcs. SQLite writes use one transaction per business action. Tests use temporary databases. No custom interface is built in this foundation.

## Task 1: Executable boundary and failing acceptance tests

Files: `pyproject.toml`, `beeloft/__init__.py`, `beeloft/api.py`, `tests/test_production.py`.

- [x] Create an application factory `create_app(database_path)` with the framework's docs and health endpoint.
- [x] Write API acceptance tests for SKU creation, an order and partial movements, QC/rework/reversal, idempotent retries, validation, role checks, concurrent transfers and persistence.
- [x] Run `python -m unittest discover -s tests -v`; verify missing API behavior fails before implementation.

## Task 2: Transactional production core

Files: `beeloft/schema.sql`, `beeloft/store.py`, `beeloft/models.py`, `beeloft/api.py`.

- [x] Initialize version 1 schema with SKU, users, orders, lines, balances, movements and request receipts.
- [x] Implement `Store.provision_user(name, role)`, `Store.authenticate(key)` and transactional connection context.
- [x] Implement `Store.create_product`, `Store.create_order`, `Store.move`, `Store.reverse` with permission checks, immutable audit and idempotency receipts in the same transaction.
- [x] Implement `Store.orders`, `Store.order`, `Store.history`; read summaries from persisted balances in one snapshot.
- [x] Bind typed request models to authenticated API routes; normalize errors to HTTP 401/403/404/409/422/503.
- [x] Run the acceptance tests and fix any failing invariant before continuing.

## Task 3: Runnable handoff and backup

Files: `beeloft/__main__.py`, `start.ps1`, `README.md`, `requirements.txt`, `.gitignore`, `docs/openapi.json`.

- [x] Add CLI `user`, `serve`, `backup`, and `demo`; keep demo data in its own database and refuse overwriting existing files.
- [x] Install dependencies in a project-isolated runtime, pin resolved packages, and export OpenAPI.
- [x] Verify backup restore and run a localhost HTTP smoke test through the actual server.
- [x] Record test output, inspect the final changes, initialize the new local git repository and commit the foundation.
- [x] Open the README or local API docs for the user and report the implemented scope and remaining limitations.
