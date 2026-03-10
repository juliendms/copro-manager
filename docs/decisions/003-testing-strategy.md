# ADR-003: Testing Strategy

**Status:** `accepted`
**Date:** 2026-03-09
**Affects:** `tests/`, `requirements.txt`

## Context

There is currently no automated test suite. The refactor in ADR-002 makes significant changes to the charge creation and repartition logic. The common quarterly charge workflow is the most critical path in the app: it is already working and must not regress.

Testing the full HTMX + BeerCSS UI layer (browser-level) would be disproportionate for a local single-user app. The risk is concentrated in the **business logic**: share calculation, repartition auto-population, installment generation, and the `status` computed properties.

## Decision

### Scope: business logic only, not UI

Use **pytest** with Flask's built-in test client. Do not test template rendering or HTMX headers in depth — focus on data correctness.

### What to test

**Priority 1 — common charge workflow (must not regress):**
- Creating a common charge generates `ChargeRepartition` for every owner
- Installment amounts are correctly proportional to `general_share`
- 4 quarterly installments are created per owner
- `Charge.status` returns `New` → `Ongoing` → `Closed` as installments are paid
- `PaymentInstallment.status` returns `Draft` → `Sent` → `Paid` correctly

**Priority 2 — extraordinary charge workflow (new behavior from ADR-002):**
- Extraordinary charge with `limited_common_element_id = NULL` → repartitions cover all owners using `general_share`
- Extraordinary charge with a LCE → repartitions cover only LCE members using `LCEShare.share`
- `share_snapshot` on `ChargeRepartition` is frozen at creation; modifying owner's `general_share` afterwards does not change existing installment amounts

**Priority 3 — edge cases:**
- Creating a charge with no owners (no LCE members, or no owners at all) does not crash and creates no repartitions
- Common charge always has `limited_common_element_id = NULL` regardless of input

### What NOT to test

- Template rendering
- HTMX response headers
- Gmail / OAuth integration (external service, already isolated in `charges_management/utils.py`)
- Flash message content

### Structure

```
tests/
  conftest.py          # app fixture, db fixture, seed helpers
  test_common_charge.py
  test_extraordinary_charge.py
  test_models.py       # status computed properties
```

### Fixtures approach

Use an in-memory SQLite database (`SQLALCHEMY_DATABASE_URI = 'sqlite://'`) created fresh per test function. Seed helpers create owners and LCEs directly via SQLAlchemy, bypassing routes where possible.

## Consequences

- Add `pytest` and `pytest-flask` to `requirements.txt` (dev dependency)
- Tests live in the existing `tests/` directory (already present in the repo)
- Tests should be run before committing any change to `charges_management/routes.py` or `models.py`
- Gmail integration is not tested — it is covered by the existing manual flow only
