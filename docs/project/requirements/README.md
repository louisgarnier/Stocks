# Project Requirements — Instructions (Read-Only Templates)

These files tell you **WHAT to build** and in what order. Follow them sequentially.
Project-specific output goes to `docs/project/config/` — never overwrite these templates.

## Quick Start
1. **Start here** → `REQUIREMENTS_WORKFLOW.md` (master checklist)
2. **Follow sequence** → `1` → `2` → `3` → `4` → `5` → `6` → `7`
3. **Write output** → each file generates content in `../config/`

## Numbered Workflow Files

| # | File | Purpose | Phase |
|---|------|---------|-------|
| 1 | `1-BRAINSTORM.md` | Validate idea before building | 🎯 **PLAN** |
| 2 | `2-PRD.md` | Requirements source of truth | 🎯 **PLAN** |
| 3 | `3-ARCHITECTURE.md` | All technical decisions | 🎯 **PLAN** |
| 4 | `4-LOGGING.md` | Logging setup template | 🎯 **PLAN** |
| 5 | `5-EPICS.md` | Work breakdown (Epics → Stories) | 🔨 **BUILD** |
| 6 | `6-BUILD.md` | Session-by-session build log | 🔨 **BUILD** |
| 7 | `7-CODEBASE.md` | Living codebase documentation | 🔨 **BUILD** |

## Output Mapping

| Instruction | Generates → | Location |
|-------------|-------------|----------|
| `1-BRAINSTORM.md` | brainstorm.md | `../config/` |
| `2-PRD.md` | prd.md | `../config/` |
| `3-ARCHITECTURE.md` | architecture.md | `../config/` |
| `4-LOGGING.md` | logging.md | `../config/` |
| `5-EPICS.md` | epics/ folder | `../config/epics/` |
| `6-BUILD.md` | build-log.md | `../config/` |
| `7-CODEBASE.md` | codebase.md | `../config/` |

## Supporting Files

| File | Purpose |
|------|---------|
| `README.md` | This overview (entry point) |
| `REQUIREMENTS_WORKFLOW.md` | **Master checklist** - start here |

## Project Development Flow

```
🎯 PLANNING PHASE
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  1-BRAINSTORM   │ →  │     2-PRD       │ →  │ 3-ARCHITECTURE  │ →  │   4-LOGGING     │
│ Validate idea   │    │ Requirements    │    │ Tech decisions  │    │ Setup template  │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘

🔨 BUILDING PHASE
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    5-EPICS      │ →  │    6-BUILD      │ ↔  │   7-CODEBASE    │
│ Break into      │    │ Session logs    │    │ Living docs     │
│ stories         │    │ & evidence      │    │ of modules      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              ↓ ↓ ↓
                    ┌─────────────────────────┐
                    │  CONTINUOUS WORKFLOW    │
                    │  ../../../workflow/     │
                    │  • ADR.md (decisions)   │
                    │  • ERRORS.md (bugs)     │
                    └─────────────────────────┘

🧪 TESTING PHASE
┌─────────────────┐
│ ../testing/     │
│ BLIND_SCENARIOS │
└─────────────────┘
```

## Detailed Workflow

See [REQUIREMENTS_WORKFLOW.md](./REQUIREMENTS_WORKFLOW.md) for the complete step-by-step guide.

## Key Principles

1. **Follow the Sequence** - Each numbered file builds on the previous one
2. **Validate Early** - Don't skip the brainstorm and PRD stages
3. **Lock Decisions** - Architecture and logging must be locked before building
4. **Document Everything** - Keep codebase docs current, log all decisions and errors
5. **Test Thoroughly** - Run blind scenarios only after development is complete

## Why This Structure Works

- **Guardrails** - Each file prevents common development pitfalls
- **Traceability** - Clear path from idea to implementation
- **Maintainability** - Decisions and errors are documented for future reference
- **Scalability** - Process works for small scripts to large applications

---

**## Related Documents**:
- [Master Workflow](./REQUIREMENTS_WORKFLOW.md) - Complete checklist
- [Config Output](../config/) - Project-specific generated content
- [Workflow Rules](../../../workflow/) - How the AI behaves (always active)
