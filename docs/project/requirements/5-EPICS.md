# 🗂️ Stage 5 — Epics & Stories
> **Output →** `docs/project/config/epics/` (overview.md, ACTIVE.md, epic-X/story-X.Y.md)
> **Instructions:** Break all work into Epics → Stories → Tasks before coding.
> The AI picks up ONE story at a time. It must not jump ahead.
> Keep stories small — a story should be completable in one coding session.
> Status indicators: `[ ] Pending` | `[→] In Progress` | `[x] Done` | `[~] Blocked`

## 📥 Inputs from Previous Stages
- **1-BRAINSTORM** → Core goals and user workflows inform epic priorities
- **2-PRD** → User stories map directly to epic stories, functional requirements drive tasks
- **3-ARCHITECTURE** → Component breakdown defines epic structure, tech stack shapes implementation tasks
- **4-LOGGING** → Logging infrastructure is ready, error handling patterns established

---

## Epic Overview
| ID | Epic | Status | Stories |
|---|---|---|---|
| EPIC-1 | [Project Setup & Scaffolding] | [ ] | 3 |
| EPIC-2 | [Core Feature 1] | [ ] | |
| EPIC-3 | [Core Feature 2] | [ ] | |
| EPIC-4 | [Testing & QA] | [ ] | |
| EPIC-5 | [Deployment & Docs] | [ ] | |

---

## EPIC-1: Project Setup & Scaffolding
> *Always start here. A solid scaffold prevents all kinds of drift.*

### Story 1.1 — Repository & Environment Setup
**Goal:** Project runs locally with a single setup command.
**Acceptance Criteria:**
- [ ] Repo initialized with this template structure
- [ ] `.env.example` created with all required variables
- [ ] `README.md` has local setup instructions
- [ ] Linter and formatter configured and passing
- [ ] Git pre-commit hooks active (optional but recommended)

**Tasks:**
- [ ] Initialize repo, set up `.gitignore`
- [ ] Create `requirements.txt` / `package.json` with approved deps
- [ ] Configure `ruff` + `black` (Python) or `eslint` + `prettier` (Node)
- [ ] Verify `CLAUDE.md` is present

**Test:** `make setup && make lint` runs without errors.

---

### Story 1.2 — Logging & Error Handling Foundation
**Goal:** Logging works before any feature is built.
**Acceptance Criteria:**
- [ ] Centralized logger configured (level from `.env`)
- [ ] All log output includes: timestamp, level, module name
- [ ] Unhandled exceptions are caught and logged, not silently swallowed

**Tasks:**
- [ ] Create `src/core/logger.py` (or `src/lib/logger.ts`)
- [ ] Create `src/core/exceptions.py` with base exception classes
- [ ] Write unit tests in `tests/dev/test_logger.py`

---

### Story 1.3 — [Add your project-specific setup story]
**Goal:**
**Acceptance Criteria:**
- [ ]

---

## EPIC-2: [Core Feature 1 — replace with your feature name]
> *Describe what this epic delivers at a high level.*

### Story 2.1 — [Name]
**Goal:** [One sentence]
**Maps to PRD:** US-01, FR-01
**Acceptance Criteria:**
- [ ]
- [ ]

**Tasks:**
- [ ]
- [ ]

**Dev Tests to write:** `tests/dev/test_[module].py`
- [ ] Test happy path
- [ ] Test edge case: [describe]
- [ ] Test failure case: [describe]

---

### Story 2.2 — [Name]
**Goal:**
**Maps to PRD:**
**Acceptance Criteria:**
- [ ]

**Tasks:**
- [ ]

**Dev Tests to write:**
- [ ]

---

## EPIC-3: [Core Feature 2]

### Story 3.1 — [Name]
**Goal:**
**Maps to PRD:**
**Acceptance Criteria:**
- [ ]

---

## EPIC-4: Testing & QA
> *This epic ties everything together. Run this before blind scenarios.*

### Story 4.1 — Full Dev Test Suite
**Goal:** All dev tests pass with >80% coverage.
**Acceptance Criteria:**
- [ ] `pytest` / `vitest` runs clean — zero failures
- [ ] Coverage report generated
- [ ] All FR requirements mapped to at least one test

**Tasks:**
- [ ] Run `pytest --cov` and check coverage
- [ ] Fill gaps in test coverage
- [ ] Fix any flaky tests

---

### Story 4.2 — Integration Smoke Test
**Goal:** The full workflow runs end-to-end without errors.
**Acceptance Criteria:**
- [ ] Can run the full pipeline/app with sample data
- [ ] All outputs are correct and in expected format
- [ ] No hardcoded paths or credentials

---

## EPIC-5: Deployment & Documentation

### Story 5.1 — README & Usage Docs
**Goal:** Someone new can set up and run the project in < 15 minutes.
**Acceptance Criteria:**
- [ ] `README.md` has: what it does, how to install, how to run, how to test
- [ ] `.env.example` is complete
- [ ] Any manual steps are documented

### Story 5.2 — Deployment
**Goal:** [Define your deployment target]
**Acceptance Criteria:**
- [ ]

---

## 🚦 Current Status
```
Working on: EPIC-[X] / Story [X.Y] — [Story name]
Blocked by:
Next up:
```

---

## 📌 Backlog (Unprioritized Ideas)
> *Dump ideas here instead of scope-creeping into current epics.*
- [ ] [Idea]
- [ ] [Idea]

---

## 🧪 Test Design Rules — Read Before Writing Any Test
> *These rules apply to every story. Violations cause silent false positives — tests pass when logic is broken.*

### Mocking rules
- **When the same DB/API mock chain is called more than once in a route, always use `side_effect=[result1, result2, ...]`** — a single `return_value` is reused for every call, meaning the second call returns stale data and the test becomes a false positive.
- **Never mock at a level that hides integration behaviour** — mock the external service (HTTP call, DB client), not internal business logic.

### Assertion rules
- **Never wrap an assertion in a conditional guard** — `if rows: assert rows[0] == x` silently passes when `rows` is empty. Always assert unconditionally: `assert len(rows) == 1` first, then check the value.
- **Always assert the exact value, not just presence** — `assert "synced" in response` passes even when `synced=0`. Assert `response["synced"] == 1`.
- **Every story's tests must cover:** happy path, at least one edge case, at least one failure/error case.

### Structure rules
- **Tests are written in the same session as the code** — never deferred to a later story.
- **Each story's final task is always: run the full test suite and confirm zero failures** — not just the new tests.
- **In-app blind scenarios** (see `testing/BLIND_SCENARIOS.md`) are written alongside the story and run manually on staging after dev tests pass.

---

## 📤 Outputs for 6-BUILD.md

**Once EPICS are defined and development begins, these outputs feed directly into build logging:**

- **Epic Structure** → BUILD session organization (work through epics in order)
- **Story Breakdown** → BUILD individual session planning (one story per session)
- **Acceptance Criteria** → BUILD session sign-off requirements (what must be true to mark story done)
- **Task Lists** → BUILD session task tracking (specific actions to complete)
- **Test Requirements** → BUILD session testing (dev tests to write per story)
- **Dependencies** → BUILD session sequencing (what must be done first)
- **Current Status** → BUILD session updates (track progress through epics)

---

*→ Proceed to `6-BUILD.md` once development begins with the structured outputs above*
