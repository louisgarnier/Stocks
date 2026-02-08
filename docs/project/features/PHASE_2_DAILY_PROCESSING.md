# Phase 2: Daily Trade Processing

**Process fetched flex files and insert new transactions into database with deduplication.**

## Requirements

### Functional Requirements
- [ ] Process CSV files from `input/daily_trades/`
- [ ] Deduplicate using IBKR TransactionID
- [ ] Insert new transactions into database
- [ ] Archive processed files
- [ ] Show processing results in frontend

### Non-Functional Requirements
- [ ] Performance: Process 1000+ transactions in < 10 seconds
- [ ] Reliability: No duplicate transactions ever inserted
- [ ] Auditability: Log all processing actions

## User Stories

### As a user
- I want to process fetched trades with one click
- So that new transactions are added to my database

### As a user
- I want to see how many new vs duplicate transactions were found
- So that I know the sync is working correctly

## Technical Specifications

### Backend

**API Endpoints**:
- `POST /api/pipeline/process-trades` - Process pending flex files

**New Files**:
```
backend/
└── scripts/
    └── b_daily_trades.py    # Trade processor
```

**Processing Logic**:
1. Find all CSV files in `input/daily_trades/`
2. For each file:
   - Parse CSV rows
   - Filter for STK (stocks) asset class only
   - Check `TransactionID` against database
   - Insert new transactions
   - Skip duplicates
3. Archive processed files to `archive/daily_trades/`
4. Return summary (new, duplicates, errors)

### Frontend

**Components**:
- `ProcessButton.vue` - Button to trigger processing
- `ProcessingLog.vue` - Shows processing results

**Updates**:
- Dashboard shows "Process New Trades" button
- Transaction table refreshes after processing

## Acceptance Criteria

- [ ] "Process" button triggers processing
- [ ] Log shows: "X new transactions added, Y duplicates skipped"
- [ ] Transaction table updates with new entries
- [ ] New entries highlighted or marked
- [ ] Processed files moved to archive
- [ ] No duplicates in database

## Implementation Plan

### Step 1: Create Daily Trades Script
**Description**: Adapt b_daily_trades.py for new structure

**Tasks**:
- [ ] Create `backend/scripts/b_daily_trades.py`
- [ ] Implement CSV parsing
- [ ] Filter for STK asset class
- [ ] Implement deduplication check
- [ ] Insert new transactions
- [ ] Archive processed files
- [ ] Return processing summary

**Dependencies**: Phase 1 complete

**Deliverables**:
- Working `b_daily_trades.py` script
- Transactions inserted into database

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/b_daily_trades.py`
- [ ] New transactions inserted
- [ ] Duplicates skipped with log message
- [ ] Files archived

**Estimated Time**: 2 hours

---

### Step 2: Create Pipeline API Endpoint
**Description**: Add endpoint to trigger trade processing

**Tasks**:
- [ ] Create `backend/api/routes/pipeline.py`
- [ ] Add `POST /api/pipeline/process-trades` endpoint
- [ ] Call b_daily_trades script
- [ ] Return processing summary
- [ ] Register routes in main.py

**Dependencies**: Step 1

**Deliverables**:
- Pipeline endpoint working

**Acceptance Criteria**:
- [ ] POST `/api/pipeline/process-trades` processes files
- [ ] Returns `{new: X, duplicates: Y, errors: Z}`
- [ ] Errors return proper HTTP status

**Estimated Time**: 1 hour

---

### Step 3: Create Frontend Processing UI
**Description**: Add process button and results display

**Tasks**:
- [ ] Create `ProcessButton.vue` component
- [ ] Create `ProcessingLog.vue` component
- [ ] Add to dashboard
- [ ] Refresh transaction table after processing
- [ ] Highlight new transactions (optional)

**Dependencies**: Step 2

**Deliverables**:
- Process button with results display

**Acceptance Criteria**:
- [ ] Button shows "Process New Trades"
- [ ] Loading state during processing
- [ ] Shows "X new, Y duplicates" after processing
- [ ] Transaction table refreshes

**Estimated Time**: 1.5 hours

---

## Frontend Checkpoint ✓

```
✅ "Process New Trades" button visible
✅ Loading state during processing
✅ Log shows: "X new transactions added, Y duplicates skipped"
✅ Transaction table updates with new entries
✅ Processed files moved to archive
```

## Related Requirements

- [ANALYZED_REQUIREMENTS.md - Phase 2](../requirements/ANALYZED_REQUIREMENTS.md#phase-2-daily-trade-processing)

## Notes

- Deduplication key: `original_transaction_id` (IBKR_TXN_xxxxx format)
- Only STK (stocks) asset class processed
- Archive preserves original filename
- Processing is idempotent (safe to run multiple times)

---

## Quick Links

- [Previous Phase: Flex API](./PHASE_1_FLEX_API.md)
- [Next Phase: Stock Splits](./PHASE_3_STOCK_SPLITS.md)
- [Analyzed Requirements](../requirements/ANALYZED_REQUIREMENTS.md)
