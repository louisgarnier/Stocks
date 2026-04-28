# 🧠 Stage 1 — Brainstorm & Idea Validation

> **Output →** `docs/project/config/brainstorm.md`
>
> **Two ways to complete this stage:**
> - **Manual:** Fill this template directly, copy output to `docs/project/config/brainstorm.md`
> - **Script (optional shortcut):** `python scripts/brainstorm.py` — asks the same questions interactively
>
> **Goal:** Decide if this idea is worth building — before writing a single line of code.
> **Status:** `[ ] Draft` → `[ ] Validated` → `[ ] GO — Proceed to PRD`

---

## 0. Freeform Input
> *Start here. No structure required. Raw thoughts, constraints, links, screenshots — anything.*

```
[dump everything you know about this idea here]
```

---

## 1. The One-Liner
> *What is this project in ONE sentence? No conjunctions — if you need "and", it's two projects.*

```
[PROJECT NAME] is a [type of thing] that [does what] for [who].
```

**Example:** *"TradeAlert is a Python daemon that detects breakout patterns in IBKR data and sends Telegram notifications."*

---

## 2. The Problem
> *What pain does this solve? Be specific — generic answers produce vague projects.*

- **Who has this problem?**
- **How are they solving it today?** (manual process / other tool / not at all)
- **Why is the current solution inadequate?**
- **How often does this problem occur?**

---

## 3. The Solution
> *Describe it from the USER's perspective, not the tech perspective. Keep it high-level — details go in the PRD.*

**Core workflow (user's journey):**
1. User does X
2. System does Y
3. User gets Z

**What makes this different from alternatives?**

---

## 4. Assumptions & Risks
> *List what you're assuming to be true. Each assumption is a risk if wrong.*

| Assumption | Risk if Wrong | Mitigation |
|---|---|---|
| [e.g. Data is available in CSV format] | [Pipeline fails at ingestion] | [Validate format at kickoff] |

---

## 5. Feasibility Check
> *Honest assessment before you invest weeks.*

| Dimension | Assessment | Notes |
|---|---|---|
| **Technical complexity** | Low / Medium / High | |
| **Time estimate (MVP)** | X days/weeks | |
| **Dependencies / blockers** | | |
| **Skills gap** | | |
| **Maintenance burden** | Low / Medium / High | |

---

## 6. Go / No-Go Decision
> *Commit or don't. Include what success looks like — that's your commit criteria.*

**What does success look like?**
- Minimum (MVP done): _______
- Full success: _______
- Failure looks like: _______

**Decision:**
```
[ ] GO   — The problem is real, the solution is scoped, I'm committing to this
[ ] NO-GO — Reasons: _______________
[ ] PARK  — Good idea, wrong time. Revisit: _______________
```

**Rationale:**

---

## 📤 Outputs for 2-PRD.md

> *If GO: these feed the PRD. The PRD is where goals, users, and requirements get detailed — not here.*

| Brainstorm | → PRD input |
|---|---|
| Name + one-liner (§1) | Project Summary |
| Problem + solution (§2-3) | Context & user story seeds |
| Assumptions & risks (§4) | Open Questions & Constraints |
| Feasibility (§5) | Non-functional requirements, constraints |
| Go/No-Go rationale (§6) | Goals framing |

---

*→ If GO: proceed to `2-PRD.md`*
