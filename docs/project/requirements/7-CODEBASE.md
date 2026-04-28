# 📚 Stage 7 — Codebase Documentation
> **Output →** `docs/project/config/codebase.md`
> **This file is the AI's map of the existing codebase.**
> Updated after EVERY story that adds or modifies code.
> The AI MUST read this before touching any existing module.
>
> Structure per component:
> - **Current State** (always accurate, always at top) → what the AI uses before coding
> - **Change Log** (append-only, below current state) → audit trail for regressions

## 📥 Inputs from 6-BUILD.md
- **New Modules Created** → Add to Codebase Map with epic/story reference
- **Module Documentation** → Create/update individual module sections
- **Data Flow Changes** → Update Data Flows section
- **Dependencies Added** → Update Dependency Map section
- **Technical Debt** → Document in Known Technical Debt section
- **Architectural Changes** → Add to component change logs
- **Session Decisions** → Reference when documenting design rationale
- **Implementation Details** → Capture in Current State sections

> ⚠️ RULES FOR THE AI:
> - Read this file at the start of every session
> - After completing a story, update the affected component entries HERE
> - Never modify the Change Log — only append to it
> - If current state contradicts `3-ARCHITECTURE.md`, flag it before proceeding

---

## 🗺️ Codebase Map
> High-level index — updated as modules are added. One line per file.

```
src/
├── core/
│   ├── logger.py          → Centralized logger (EPIC-1 / Story 1.2)
│   ├── exceptions.py      → Base exception classes (EPIC-1 / Story 1.2)
│   └── config.py          → Env var loading & validation (EPIC-1 / Story 1.1)
├── [module]/
│   └── [file].py          → [one-line description] (EPIC-X / Story X.Y)
└── main.py                → Entry point (EPIC-1 / Story 1.1)

tests/dev/
├── test_core.py           → Tests for core/ (EPIC-1 / Story 1.2)
└── test_[module].py       → [description] (EPIC-X / Story X.Y)
```

---
---

## CORE MODULES

---

### 📄 `src/core/logger.py`
> **Status:** `[ ] Pending` | `[ ] Built` | `[ ] Modified`
> **Built in:** EPIC-1 / Story 1.2
> **Last modified:** EPIC-X / Story X.Y

#### Current State

**Purpose:**
Centralized logger used by all modules. Ensures consistent log format across the application.

**Exports:**
```python
get_logger(name: str) -> logging.Logger
```

**Usage:**
```python
from src.core.logger import get_logger
log = get_logger(__name__)
log.info("Something happened")
```

**Log format:**
```
2024-03-11 14:22:01 INFO  [module.name] Message here
```

**Configuration:**
- Log level read from `LOG_LEVEL` env var (default: `INFO`)
- Outputs to: stdout + `logs/app.log`

**Data flow:**
- Input: `name` (string, typically `__name__`)
- Output: configured `logging.Logger` instance
- Side effects: creates `logs/` directory if not present

**Design rationale:**
Single logger factory prevents inconsistent formats across modules. Using `__name__` as the logger name gives precise source location in every log line.

**Known limitations:**
- No log rotation configured yet — `logs/app.log` grows unbounded
- No structured/JSON logging — add if log aggregation tool is needed later

---

#### Change Log
| Date | Story | Change | Reason |
|---|---|---|---|
| [DATE] | EPIC-1 / Story 1.2 | Created | Initial logger setup |

---

### 📄 `src/core/exceptions.py`
> **Status:** `[ ] Pending` | `[ ] Built` | `[ ] Modified`
> **Built in:** EPIC-1 / Story 1.2

#### Current State

**Purpose:**
Base exception hierarchy for the project. All custom exceptions inherit from `AppError` so callers can catch broadly or narrowly.

**Exports:**
```python
class AppError(Exception)           # Base — catch-all for project errors
class ConfigError(AppError)         # Missing/invalid env vars
class IngestionError(AppError)      # Data loading failures
class ValidationError(AppError)     # Schema/data quality failures
class ProcessingError(AppError)     # Pipeline processing failures
```

**Usage:**
```python
from src.core.exceptions import ValidationError
raise ValidationError("Missing required column: 'date'")
```

**Design rationale:**
Hierarchy allows callers to `except AppError` for broad handling or `except ValidationError` for specific cases. Avoids bare `Exception` catches that swallow unexpected errors.

**Known limitations:**
- Add more specific subclasses as new modules are built

---

#### Change Log
| Date | Story | Change | Reason |
|---|---|---|---|
| [DATE] | EPIC-1 / Story 1.2 | Created | Initial exception hierarchy |

---

### 📄 `src/core/config.py`
> **Status:** `[ ] Pending` | `[ ] Built` | `[ ] Modified`
> **Built in:** EPIC-1 / Story 1.1

#### Current State

**Purpose:**
Loads and validates all environment variables at startup. Fails fast if required vars are missing — prevents cryptic errors deep in the pipeline.

**Exports:**
```python
class Config:
    APP_ENV: str
    LOG_LEVEL: str
    DATABASE_URL: str | None
    # ... add vars as they are defined in .env.example

def load_config() -> Config
```

**Usage:**
```python
from src.core.config import load_config
config = load_config()
```

**Data flow:**
- Input: environment variables (from `.env` via `python-dotenv`)
- Output: validated `Config` instance
- Raises: `ConfigError` if required variable is missing

**Design rationale:**
Centralizing config in one place means no `os.getenv()` scattered across modules. Type hints on `Config` make missing vars a startup error, not a runtime surprise.

**Known limitations:**
- No secrets manager integration yet — all config from `.env` file

---

#### Change Log
| Date | Story | Change | Reason |
|---|---|---|---|
| [DATE] | EPIC-1 / Story 1.1 | Created | Initial config loader |

---

### 📄 `src/main.py`
> **Status:** `[ ] Pending` | `[ ] Built` | `[ ] Modified`
> **Built in:** EPIC-1 / Story 1.1

#### Current State

**Purpose:**
Application entry point. Initializes config and logger, then routes to the appropriate workflow.

**Data flow:**
```
main()
  └── load_config()
  └── get_logger()
  └── [invoke core workflow]
```

**Design rationale:**
Thin entry point — no business logic here. Makes testing easier (import modules directly, don't go through main).

---

#### Change Log
| Date | Story | Change | Reason |
|---|---|---|---|
| [DATE] | EPIC-1 / Story 1.1 | Created | Entry point scaffold |

---
---

## FEATURE MODULES
> Add one section per module as epics are built.
> Copy the template below for each new file.

---

### 📄 `src/[module]/[file].py`
> **Status:** `[ ] Pending` | `[ ] Built` | `[ ] Modified`
> **Built in:** EPIC-X / Story X.Y
> **Last modified:** EPIC-X / Story X.Y

#### Current State

**Purpose:**
[What does this module do? One paragraph max.]

**Exports:**
```python
# List all public functions/classes with signatures
def function_name(param: type, param2: type) -> return_type
class ClassName:
    method_name(self, param: type) -> return_type
```

**Usage example:**
```python
from src.[module].[file] import [name]
# Show realistic usage in 3-5 lines
```

**Data flow:**
- Input: [what comes in, from where]
- Output: [what goes out, to where]
- Side effects: [files written, DB rows inserted, logs emitted, etc.]
- Raises: [which exceptions under which conditions]

**Key logic / algorithm:**
[Describe the non-obvious logic. If it's a 3-step process, describe the 3 steps. The AI should understand what's happening without reading the code.]

**Design rationale:**
[Why was it built this way? What alternatives were rejected and why? What constraints shaped the design?]

**Architectural impact:**
[How does this module affect the rest of the system? What depends on it? What does it depend on?]

**Known limitations / future considerations:**
- [ ] [e.g. Not thread-safe — fine for now, revisit if parallelism is added]
- [ ] [e.g. Hardcoded batch size of 1000 — parameterize in v2]

---

#### Change Log
| Date | Story | Change | Reason |
|---|---|---|---|
| [DATE] | EPIC-X / Story X.Y | Created | [Initial reason] |
| [DATE] | EPIC-X / Story X.Y | [What changed] | [Why] |

---
---

## DATA FLOWS
> End-to-end flow diagrams. Updated when a new epic changes the flow.
> Last updated: EPIC-X / Story X.Y

### Main Workflow
```
[Input]
  │
  ▼
[Module A]  →  output: [type]
  │
  ▼
[Module B]  →  output: [type]
  │
  ├──(error)──▶ [Error Handler] → log + raise AppError
  │
  ▼
[Module C]  →  output: [type]
  │
  ▼
[Output / Storage]
```

**Log checkpoints** (what should appear in logs at each stage):
1. `INFO [module_a] ...` — [what it confirms]
2. `INFO [module_b] ...` — [what it confirms]
3. `INFO [module_c] ...` — [what it confirms]

---

## 🔗 Dependency Map
> Which modules depend on which. Updated when imports change.
> Helps the AI understand blast radius before modifying a module.

| Module | Depends On | Used By |
|---|---|---|
| `core/config.py` | — | `main.py`, all modules |
| `core/logger.py` | `core/config.py` | all modules |
| `core/exceptions.py` | — | all modules |
| `[module]/[file].py` | `core/logger`, `core/exceptions` | `main.py` |

---

## ⚠️ Known Technical Debt
> Honest register of shortcuts taken. Prevents the AI from building on shaky foundations.

| # | Location | Description | Impact | Ticket / Story to Fix |
|---|---|---|---|---|
| TD-01 | `src/[file]` | [What the shortcut is] | [What breaks if ignored] | Story X.Y |

---

## 📐 Naming Conventions
> Enforced across all modules. AI must follow these.

| Element | Convention | Example |
|---|---|---|
| Python files | `snake_case` | `data_loader.py` |
| Python classes | `PascalCase` | `DataLoader` |
| Python functions | `snake_case` | `load_csv_file()` |
| Constants | `UPPER_SNAKE` | `MAX_BATCH_SIZE = 1000` |
| TS/React files | `PascalCase` for components | `DataTable.tsx` |
| TS functions | `camelCase` | `loadCsvFile()` |
| Test files (Python) | `test_[module].py` | `test_data_loader.py` |
| Test files (TS) | `[module].test.ts` | `dataLoader.test.ts` |
| Log messages | `[module] verb: detail` | `[ingestion] loaded: 1432 rows` |

---

## 📤 Outputs for Workflow Documents

**This living codebase documentation provides reference material for:**

### → ../../../workflow/ADR.md (Architecture Decision Records)
- **Design Rationale** → Context for why architectural choices were made
- **Component Interactions** → Understanding of system dependencies for decision impact analysis
- **Technical Debt** → Known limitations that inform future architectural decisions
- **Change Log Patterns** → Historical context for decision review triggers

### → ../../../workflow/ERRORS.md (Known Errors Registry)
- **Module Locations** → Precise file paths for error categorization and fixes
- **Component Dependencies** → Understanding blast radius of errors and fixes
- **Current State** → Accurate module behavior for root cause analysis
- **Change History** → Context for when errors were introduced or fixed

### → AI Development Sessions
- **Current State** → Accurate module understanding before making changes
- **Dependencies** → Impact analysis before modifications
- **Naming Conventions** → Consistent code style enforcement
- **Technical Debt** → Awareness of existing shortcuts and limitations
