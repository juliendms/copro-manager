# Project Instructions

## Architecture Decisions (ADRs)
All significant decisions are recorded in [`docs/decisions/`](docs/decisions/).
Read [`ADR-001`](docs/decisions/001-initial-architecture.md) first — it describes the current architecture, data model, and known pitfalls.

**When to write a new ADR:**
- Changing the data model (new model, renamed field, relationship change)
- Adding or restructuring a Blueprint / route module
- Introducing a new library or replacing an existing one
- Changing how templates are organized or how HTMX fragments are served
- Any decision that future models would need to understand to avoid breaking existing behavior

**How:** Copy [`docs/decisions/000-template.md`](docs/decisions/000-template.md), number it sequentially, fill in Context / Decision / Consequences, and add it to the index below before implementing.

### ADR Index
| # | Title | Status |
|---|-------|--------|
| [001](docs/decisions/001-initial-architecture.md) | Initial Architecture Overview | accepted |
| [002](docs/decisions/002-limited-common-elements.md) | Introduce Limited Common Elements for Charge Repartition | accepted |
| [003](docs/decisions/003-testing-strategy.md) | Testing Strategy | accepted |

---

## UI
- This project uses BeerCSS library
- Prefer to use built-in CSS class from BeerCSS
- Follow Material Design 3 guidelines

## Guidelines
- Prefer to use HTMX tags rather than JS function
- Always double-check database context to prevent DetachedInstanceError