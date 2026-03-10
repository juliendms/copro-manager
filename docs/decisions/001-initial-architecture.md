# ADR-001: Initial Architecture Overview

**Status:** `accepted`
**Date:** 2026-03-09
**Affects:** `app.py`, `models.py`, `app_utils.py`, `owner_management/`, `charges_management/`, `templates/`

## Context
Copro-Manager is a local Flask application for managing condominium co-owners, charges, and payment tracking.
It is used by a single administrator (not a multi-tenant SaaS). The DB is a local SQLite file at `instance/app.db`.
This ADR captures the architectural state prior to a planned heavy refactor.

## Decision

### Stack
- **Backend:** Flask with SQLAlchemy (Flask-SQLAlchemy), SQLite via `instance/app.db`
- **Frontend:** HTMX for interactivity, BeerCSS (Material Design 3) for UI, minimal custom JS
- **Templating:** Jinja2; `templates/base.html` is the root layout shared by all pages

### Structure
```
app.py                    # App factory, root routes (index, initial_db_setup, flash_fragment)
app_utils.py              # Shared decorators (no_cache)
models.py                 # All SQLAlchemy models
owner_management/
    __init__.py           # Blueprint: owner_bp, prefix /owners
    routes.py             # Owner CRUD routes
    templates/            # Owner-specific templates
charges_management/
    __init__.py           # Blueprint: charges_bp, prefix (none set explicitly)
    routes.py             # Charges CRUD + email sending
    utils.py              # Charge-specific helpers
    templates/            # Charges-specific templates
templates/
    base.html             # Root layout (nav, dialog slot, flash messages)
    index.html            # Dashboard
    partials/             # Shared partials: nav, flash_messages, _empty_state
```

### Data Model
- **Owner** — name, lot_number, share (integer tantièmes). Has many **OwnerEmail**.
- **Charge** — description, total_amount, type (`common`|`extraordinary`), payment_schedule (`one_time`|`quarterly`), year, purpose, voting_date.
- **ChargeRepartition** — composite PK (charge_id, owner_id). Join table between Charge and Owner.
- **PaymentInstallment** — belongs to ChargeRepartition, has quarter (1–4), amount, email_sent_date, paid_date. Status is a computed `@property` (`Draft`/`Sent`/`Paid`).
- **Charge.status** is also a computed `@property` (`New`/`Ongoing`/`Closed`), derived from all installment statuses across all repartitions.

### Key Patterns
- **HTMX-first:** Routes return HTML fragments; dialogs are loaded into `<dialog id="dialog">` via hx-get.
- **DB existence guard:** `before_request` sets `g.db_exists`; base template gates the full UI on this flag.
- **No caching on index:** `@no_cache` decorator applied to the dashboard to prevent stale HTMX state.
- **DetachedInstanceError risk:** SQLAlchemy objects must not be accessed outside their session. Always use `joinedload` or access relationships within the request context.

## Consequences
- All models live in a single `models.py` file — fine now, may need splitting if models grow.
- `app.py` contains direct query logic in the `index` route — this is a known smell to address in the refactor.
- Blueprint for charges has no `url_prefix` explicitly set in `__init__.py` (verify before refactoring routing).
- `PaymentInstallment` uses a manual composite FK pattern instead of a simpler relationship — be careful when touching this model.
- Templates are split between `templates/` (root) and each blueprint's own `templates/` folder — Jinja loader resolves blueprint templates first, then falls back to root.
