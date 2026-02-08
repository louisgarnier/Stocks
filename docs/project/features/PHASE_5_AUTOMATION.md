# Phase 5: Automation & Monitoring

**Automate the daily pipeline and provide monitoring dashboard.**

## Requirements

### Functional Requirements
- [ ] Pipeline orchestrator runs all steps in sequence
- [ ] Scheduler for automated daily runs
- [ ] Pipeline run history logging
- [ ] Status monitoring in frontend

### Non-Functional Requirements
- [ ] Reliability: Pipeline handles failures gracefully
- [ ] Observability: Clear logs for each step
- [ ] Alerting: Notify on failures (optional)

## User Stories

### As a user
- I want to run the full pipeline with one click
- So that I don't have to run each step manually

### As a user
- I want to see the status of each pipeline step
- So that I can identify if something failed

### As a user
- I want the pipeline to run automatically each day
- So that my data stays up to date

## Technical Specifications

### Backend

**API Endpoints**:
- `POST /api/pipeline/run` - Run full pipeline (A→B→C→D)
- `GET /api/pipeline/history` - Get pipeline run history
- `GET /api/pipeline/status` - Get current pipeline status

**New Files**:
```
backend/
├── scripts/
│   └── pipeline_runner.py   # Orchestrator
└── api/
    └── routes/
        └── pipeline.py      # Pipeline endpoints (extend)
```

**Database Schema Addition**:
```sql
CREATE TABLE pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT NOT NULL,  -- 'running', 'success', 'failed'
    step_a_status TEXT,
    step_a_message TEXT,
    step_b_status TEXT,
    step_b_message TEXT,
    step_c_status TEXT,
    step_c_message TEXT,
    step_d_status TEXT,
    step_d_message TEXT,
    error_message TEXT
);
```

**Pipeline Steps**:
1. **Step A**: Flex Fetch (a_flex_fetch.py)
2. **Step B**: Process Trades (b_daily_trades.py)
3. **Step C**: Apply Splits (c_trans_update.py)
4. **Step D**: Calculate Positions (d_positions.py)

### Frontend

**Components**:
- `PipelineStatus.vue` - Shows current/last run status
- `PipelineHistory.vue` - List of past runs
- `StepIndicator.vue` - Status for each step (✓/✗/⏳)

**Pages/Routes**:
- `pages/pipeline.vue` - Pipeline monitoring page

## Acceptance Criteria

- [ ] "Run Full Pipeline" button executes all steps
- [ ] Pipeline panel shows all 4 steps
- [ ] Each step shows status (✓/✗/⏳)
- [ ] History shows past runs with results
- [ ] Scheduler runs daily at configured time (optional)

## Implementation Plan

### Step 1: Create Pipeline Runner
**Description**: Orchestrator script that runs all steps

**Tasks**:
- [ ] Create `backend/scripts/pipeline_runner.py`
- [ ] Import and call each step script
- [ ] Capture success/failure for each step
- [ ] Stop on first failure (optional: continue)
- [ ] Return complete status

**Dependencies**: Phases 1-4 complete

**Deliverables**:
- Working pipeline orchestrator

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/pipeline_runner.py`
- [ ] All 4 steps execute in sequence
- [ ] Returns status for each step

**Estimated Time**: 1.5 hours

---

### Step 2: Create Pipeline Runs Table
**Description**: Add database table for run history

**Tasks**:
- [ ] Add `pipeline_runs` table to schema
- [ ] Create migration or update schema.sql
- [ ] Add helper functions for logging runs

**Dependencies**: Step 1

**Deliverables**:
- Pipeline runs table

**Acceptance Criteria**:
- [ ] Table created with correct columns
- [ ] Can insert and query run records

**Estimated Time**: 30 minutes

---

### Step 3: Create Pipeline API Endpoints
**Description**: Add endpoints for pipeline operations

**Tasks**:
- [ ] Add `POST /api/pipeline/run` endpoint
- [ ] Add `GET /api/pipeline/history` endpoint
- [ ] Add `GET /api/pipeline/status` endpoint
- [ ] Log runs to database

**Dependencies**: Steps 1, 2

**Deliverables**:
- Pipeline API endpoints

**Acceptance Criteria**:
- [ ] POST `/api/pipeline/run` executes full pipeline
- [ ] GET `/api/pipeline/history` returns last 10 runs
- [ ] GET `/api/pipeline/status` returns current status

**Estimated Time**: 1.5 hours

---

### Step 4: Create Pipeline Monitoring UI
**Description**: Build pipeline status page

**Tasks**:
- [ ] Create `pages/pipeline.vue`
- [ ] Create `PipelineStatus.vue` component
- [ ] Create `StepIndicator.vue` component
- [ ] Create `PipelineHistory.vue` component
- [ ] Add "Run Full Pipeline" button
- [ ] Add navigation link

**Dependencies**: Step 3

**Deliverables**:
- Pipeline monitoring page

**Acceptance Criteria**:
- [ ] Pipeline page shows 4 steps with status
- [ ] Run button triggers pipeline
- [ ] History shows past runs
- [ ] Real-time status updates (polling)

**Estimated Time**: 2.5 hours

---

### Step 5: Add Scheduler (Optional)
**Description**: Automated daily pipeline runs

**Tasks**:
- [ ] Add APScheduler to backend
- [ ] Configure daily run time (e.g., 6:00 AM)
- [ ] Add scheduler status to API
- [ ] Show next scheduled run in UI

**Dependencies**: Step 4

**Deliverables**:
- Automated scheduling

**Acceptance Criteria**:
- [ ] Pipeline runs automatically at configured time
- [ ] UI shows next scheduled run
- [ ] Can enable/disable scheduler

**Estimated Time**: 1.5 hours

---

## Frontend Checkpoint ✓

```
✅ Pipeline page shows all 4 steps
✅ Each step shows status (✓/✗/⏳)
✅ "Run Full Pipeline" button executes all steps
✅ History shows past runs with results
✅ Real-time status updates during run
```

## Related Requirements

- [ANALYZED_REQUIREMENTS.md - Phase 5](../requirements/ANALYZED_REQUIREMENTS.md#phase-5-automation--monitoring)

## Notes

- Pipeline runs are logged for audit trail
- Consider adding email/webhook alerts for failures
- Scheduler uses APScheduler (or system cron as alternative)
- Pipeline should be idempotent (safe to run multiple times)

---

## Quick Links

- [Previous Phase: Positions](./PHASE_4_POSITIONS.md)
- [Analyzed Requirements](../requirements/ANALYZED_REQUIREMENTS.md)
- [Project Setup](./PHASE_0_PROJECT_SETUP.md) (start over)
