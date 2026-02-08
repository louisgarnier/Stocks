# Phase 3: Stock Split Adjustments

**Apply stock split adjustments to historical transactions.**

## Requirements

### Functional Requirements
- [ ] Load stock splits configuration from CSV
- [ ] Apply split adjustments to historical transactions
- [ ] Store both original and adjusted values
- [ ] Display split status in frontend

### Non-Functional Requirements
- [ ] Accuracy: Split calculations must be exact
- [ ] Idempotency: Running twice produces same result
- [ ] Traceability: Clear record of which splits applied

## User Stories

### As a user
- I want stock splits applied automatically to my historical trades
- So that my position quantities are accurate

### As a user
- I want to see which transactions had splits applied
- So that I can verify the adjustments are correct

## Technical Specifications

### Backend

**API Endpoints**:
- `POST /api/pipeline/apply-splits` - Apply split adjustments
- `GET /api/splits` - List configured stock splits

**New Files**:
```
backend/
└── scripts/
    └── c_trans_update.py    # Split adjuster

input/
└── specs/
    └── stock_splits.csv     # Split configuration
```

**Stock Splits CSV Format**:
```csv
Symbol;Date;Ratio
AAPL;28/08/2020;4-for-1
TSLA;25/08/2020;5-for-1
NVDA;20/07/2021;4-for-1
```

**Split Logic**:
- For transactions BEFORE split date: multiply quantity by ratio, divide price by ratio
- Mark as processed with split description
- Transactions after split date: mark as "no split"

### Frontend

**Components**:
- `SplitConfigTable.vue` - Shows configured splits
- `SplitBadge.vue` - Visual indicator for split-adjusted rows

**Updates**:
- Transaction table shows original AND adjusted columns
- Split-adjusted rows have badge/icon

## Acceptance Criteria

- [ ] Split configuration visible in UI
- [ ] "Apply Splits" button triggers processing
- [ ] Transactions show original AND adjusted quantities
- [ ] Split-adjusted rows have visual indicator
- [ ] Log shows: "X transactions adjusted for splits"

## Implementation Plan

### Step 1: Create Stock Splits Config
**Description**: Set up splits configuration file

**Tasks**:
- [ ] Create `input/specs/stock_splits.csv`
- [ ] Add known splits (AAPL, TSLA, NVDA, etc.)
- [ ] Document format in README

**Dependencies**: Phase 2 complete

**Deliverables**:
- Stock splits CSV file

**Acceptance Criteria**:
- [ ] CSV file exists with correct format
- [ ] At least 3 stock splits configured

**Estimated Time**: 30 minutes

---

### Step 2: Create Split Adjustment Script
**Description**: Implement c_trans_update.py

**Tasks**:
- [ ] Create `backend/scripts/c_trans_update.py`
- [ ] Load splits from CSV
- [ ] Find transactions needing adjustment (NULL stock_splits_applied)
- [ ] Calculate adjusted quantity and price
- [ ] Update database with adjusted values
- [ ] Mark all as processed ("no split" or split description)

**Dependencies**: Step 1

**Deliverables**:
- Working `c_trans_update.py` script

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/c_trans_update.py`
- [ ] `updated_quantity` and `updated_t_price` populated
- [ ] `stock_splits_applied` column filled for all transactions

**Estimated Time**: 2 hours

---

### Step 3: Create Splits API Endpoints
**Description**: Add endpoints for split operations

**Tasks**:
- [ ] Add `POST /api/pipeline/apply-splits` endpoint
- [ ] Add `GET /api/splits` endpoint
- [ ] Return split configuration and status

**Dependencies**: Step 2

**Deliverables**:
- Splits API endpoints

**Acceptance Criteria**:
- [ ] POST `/api/pipeline/apply-splits` applies splits
- [ ] GET `/api/splits` returns configured splits
- [ ] Returns count of adjusted transactions

**Estimated Time**: 1 hour

---

### Step 4: Update Frontend for Splits
**Description**: Show split info in UI

**Tasks**:
- [ ] Create `SplitConfigTable.vue` component
- [ ] Create `SplitBadge.vue` component
- [ ] Add "Apply Splits" button to dashboard
- [ ] Update transaction table with adjusted columns
- [ ] Add split indicator to adjusted rows

**Dependencies**: Step 3

**Deliverables**:
- Split configuration display
- Updated transaction table

**Acceptance Criteria**:
- [ ] Split config table shows all configured splits
- [ ] Transaction table shows Qty and Adjusted Qty columns
- [ ] Split-adjusted rows have visual badge
- [ ] Apply Splits button works

**Estimated Time**: 2 hours

---

## Frontend Checkpoint ✓

```
✅ Split configuration visible (table of splits)
✅ "Apply Splits" button triggers processing
✅ Transactions show original AND adjusted quantities
✅ Split-adjusted rows have visual indicator (badge/icon)
✅ Log shows: "X transactions adjusted for splits"
```

## Related Requirements

- [ANALYZED_REQUIREMENTS.md - Phase 3](../requirements/ANALYZED_REQUIREMENTS.md#phase-3-stock-split-adjustments)

## Notes

- Splits are cumulative (if multiple splits, apply all)
- Only process transactions with NULL `stock_splits_applied`
- "no split" means checked but no adjustment needed
- Split ratios: "4-for-1" means qty × 4, price ÷ 4

---

## Quick Links

- [Previous Phase: Daily Processing](./PHASE_2_DAILY_PROCESSING.md)
- [Next Phase: Positions](./PHASE_4_POSITIONS.md)
- [Analyzed Requirements](../requirements/ANALYZED_REQUIREMENTS.md)
