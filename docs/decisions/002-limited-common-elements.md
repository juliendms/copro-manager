# ADR-002: Introduce Limited Common Elements for Charge Repartition

**Status:** `accepted`
**Date:** 2026-03-09
**Affects:** `models.py`, `charges_management/`, `owner_management/`, `app.py`, entire DB schema (breaking — DB will be dropped and recreated)

---

## Context

### Current problem
Extraordinary charges are currently created with a manual, per-charge owner selection. This is architecturally wrong: in a condominium, *who pays* and *how much* is not defined per-charge — it is defined by the nature of the element the charge applies to.

There are two types of common elements in a condominium:

- **General common elements** (parties communes générales): shared by all co-owners. Each owner's share is their general *tantièmes* (`Owner.share`). All current *common* charges use this.
- **Limited common elements** (parties communes spéciales): shared by a defined subset of owners only (e.g. an elevator serving one staircase, a private parking lot, a specific wing). Each LCE has its own tantièmes table, independent of the general one.

A charge targets *an element*, not an arbitrary list of people. The current model inverts this: it asks the user to re-specify which owners are concerned for every single extraordinary charge, which is error-prone and legally inaccurate.

### What must not break
The common quarterly charge flow (all owners, general shares, quarterly installments) is working correctly and must not regress.

---

## Decision

### 1. Introduce `LimitedCommonElement` as a first-class entity

A new model representing a named limited common element at the condominium level. It is defined once and reused by any number of charges.

```
LimitedCommonElement
  id          Integer PK
  name        String(100)  e.g. "Elevator – Building A", "Private parking"
  description String(200)  optional
  shares      → LCEShare[]
```

```
LCEShare  (association table)
  element_id  FK → LimitedCommonElement  (PK part 1)
  owner_id    FK → Owner                 (PK part 2)
  share       Integer  (tantièmes for this element, independent of Owner.general_share)
```

LCEs are **optional**. The app works fully without any LCEs defined — extraordinary charges simply default to general scope.

### 2. Rename `Owner.share` → `Owner.general_share`

To clearly distinguish general tantièmes from LCE-specific tantièmes, and to prevent accidental misuse in LCE-scoped calculations.

### 3. Add `limited_common_element_id` to `Charge` (nullable FK)

This single field encodes the *scope* of the charge:

| `limited_common_element_id` | Scope | Owners affected | Shares used |
|---|---|---|---|
| `NULL` | General | All owners | `Owner.general_share` |
| `<id>` | Limited | LCE members only | `LCEShare.share` for that element |

**Share denominator:** always the dynamic sum of the shares of the owners involved (`sum(owner.general_share for all owners)` for general, `sum(lce_share.share for lce members)` for limited).

**Shares are snapshotted at charge creation time.** `ChargeRepartition` stores a `share_snapshot` column. Once a charge is created, modifying an owner's `general_share` or an LCE's `LCEShare.share` has no retroactive effect on existing charges or installment amounts.

**The `limited_common_element_id` is locked after creation**, same as `type` is currently locked once repartitions exist.

### 4. `type` and scope are independent — but only two use cases are exposed in the UI

The data model supports all combinations, but the UI is intentionally constrained:

| type | scope | Supported | Exposed in UI |
|---|---|---|---|
| common | general | yes | yes — existing flow, unchanged |
| common | limited | modeled but not used | **no** — hidden from charge creation form |
| extraordinary | general | yes | yes — default when no LCE selected |
| extraordinary | limited | yes | yes — LCE picker appears when LCEs exist |

`payment_schedule` remains derived from `type` (`common` → `quarterly`, `extraordinary` → `one_time`). Common charges always target general scope; `limited_common_element_id` is always `NULL` for common charges and this is enforced at the route level.

**Extraordinary charge UI — LCE picker visibility:**
- If no LCEs are configured: the scope field is hidden; charge silently targets general scope.
- If LCEs exist: a dropdown appears with "General common elements" as the first option, followed by each LCE by name.

### 5. Keep `ChargeRepartition` — auto-populate it on charge creation

`ChargeRepartition` remains the per-owner-per-charge record. It is no longer manually composed; it is populated automatically when a charge is created.

`PaymentInstallment` is **unchanged**.

---

## Final Schema

```
Owner
  id              Integer PK
  name            String(100)
  lot_number      String(10) unique
  general_share   Integer              ← renamed from `share`
  emails          → OwnerEmail[]
  repartitions    → ChargeRepartition[]

OwnerEmail  (unchanged)

LimitedCommonElement  (NEW)
  id          Integer PK
  name        String(100)
  description String(200) nullable
  shares      → LCEShare[]
  charges     → Charge[]

LCEShare  (NEW)
  element_id  Integer FK → LimitedCommonElement  (PK)
  owner_id    Integer FK → Owner                 (PK)
  share       Integer

Charge
  id                         Integer PK
  description                String(200)
  total_amount               Float
  type                       String(50)   'common' | 'extraordinary'
  payment_schedule           String(50)   'quarterly' | 'one_time'
  year                       Integer nullable       (set for common, null for extraordinary)
  purpose                    String(200) nullable   (set for extraordinary, null for common)
  voting_date                Date nullable
  date_created               DateTime
  limited_common_element_id  Integer FK → LimitedCommonElement nullable
                             ← always NULL for common charges
                             ← NULL (general) or LCE id for extraordinary

ChargeRepartition  (auto-populated)
  charge_id       Integer FK → Charge  (PK)
  owner_id        Integer FK → Owner   (PK)
  share_snapshot  Integer              ← NEW: share value frozen at charge creation time
  installments    → PaymentInstallment[]

PaymentInstallment  (unchanged)
  id                             Integer PK
  charge_repartition_charge_id   Integer
  charge_repartition_owner_id    Integer
  FK → ChargeRepartition (composite)
  quarter         Integer nullable
  amount          Float
  email_sent_date DateTime nullable
  paid_date       DateTime nullable
```

---

## Impact by layer

### `models.py`
- Rename `Owner.share` → `Owner.general_share`
- Add `LimitedCommonElement` + `LCEShare` models
- Add `Charge.limited_common_element_id` FK + relationship
- Add `ChargeRepartition.share_snapshot` column

### `charges_management/routes.py`
- `add_charge`: replace owner multi-select with auto-population from scope; enforce `limited_common_element_id = NULL` for common charges; store `share_snapshot` on each `ChargeRepartition`
- `edit_charge`: lock `limited_common_element_id` once repartitions exist (same guard as `type`)
- Share calculation: branch on `limited_common_element_id is None`

### `charges_management/templates/`
- `charge_dialog.html` / `_charge_type_selector.html`: replace owner checkboxes with conditional LCE dropdown (only shown for extraordinary type AND when LCEs exist)

### New: `lce_management/` blueprint (top-level nav item)
- CRUD for `LimitedCommonElement`
- UI to assign owners and their shares per element
- Nav entry in `templates/partials/nav.html`

### `app.py` — dashboard
- No structural change; `Charge.status` property and installment queries remain valid

---

## Consequences

- **DB is dropped and recreated** — accepted.
- Extraordinary charge data with ad-hoc owner selection is discarded.
- `Owner.share` rename touches: `add_charge`, `edit_charge`, dashboard query in `app.py`, and any template displaying shares — grep for `owner.share` and `rep.owner.share` before starting.
- `Charge.status` iterates `self.repartitions` via a `lazy='dynamic'` relationship — still valid, no change needed.
- When editing a charge's `total_amount` after creation, installment amounts are recalculated using `share_snapshot`, not live owner/LCE shares.
- The common charge + LCE combination is intentionally unimplemented in the UI. Do not add UI affordances for it without a new ADR.
