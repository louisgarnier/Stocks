# Phase 4: Position Calculation

**Calculate current holdings from all transactions and display on dashboard.**

## Requirements

### Functional Requirements
- [ ] Calculate positions from split-adjusted quantities
- [ ] Update positions table in database
- [ ] Display holdings dashboard
- [ ] Export positions to CSV backup

### Non-Functional Requirements
- [ ] Accuracy: Positions must match IBKR exactly
- [ ] Performance: Calculate all positions in < 5 seconds
- [ ] Usability: Easy to search and filter positions

## User Stories

### As a user
- I want to see my current stock holdings
- So that I know what I own

### As a user
- I want to search for a specific stock
- So that I can quickly find its position

## Technical Specifications

### Backend

**API Endpoints**:
- `POST /api/pipeline/calculate-positions` - Recalculate all positions
- `GET /api/positions` - List current positions

**New Files**:
```
backend/
└── scripts/
    └── d_positions.py    # Position calculator
```

**Position Logic**:
1. Sum `updated_quantity` (split-adjusted) for each symbol
2. Exclude positions with quantity < 0.1 or ≤ 0
3. Count transactions per symbol
4. Update positions table

### Frontend

**Components**:
- `PositionsTable.vue` - Holdings table
- `PositionCard.vue` - Summary cards
- `SearchFilter.vue` - Symbol search

**Pages/Routes**:
- `pages/positions.vue` - Holdings dashboard

## Acceptance Criteria

- [ ] Holdings dashboard shows all positions
- [ ] Quantities match expected values (split-adjusted)
- [ ] Summary shows total positions count
- [ ] Can search/filter positions by symbol
- [ ] Positions exported to CSV backup

## Implementation Plan

### Step 1: Create Positions Script
**Description**: Implement d_positions.py

**Tasks**:
- [ ] Create `backend/scripts/d_positions.py`
- [ ] Query all transactions from database
- [ ] Sum `updated_quantity` by symbol
- [ ] Filter out zero/negative positions
- [ ] Update positions table
- [ ] Export to CSV backup

**Dependencies**: Phase 3 complete

**Deliverables**:
- Working `d_positions.py` script
- Positions table populated

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/d_positions.py`
- [ ] Positions table updated
- [ ] CSV backup created in `output/ibkr/`

**Estimated Time**: 1.5 hours

---

### Step 2: Create Positions API Endpoint
**Description**: Add endpoint to get positions

**Tasks**:
- [ ] Add `POST /api/pipeline/calculate-positions` endpoint
- [ ] Add `GET /api/positions` endpoint with search
- [ ] Return position data with transaction counts

**Dependencies**: Step 1

**Deliverables**:
- Positions API endpoints

**Acceptance Criteria**:
- [ ] GET `/api/positions` returns all positions
- [ ] Search by symbol works
- [ ] Returns total count

**Estimated Time**: 1 hour

---

### Step 3: Create Holdings Dashboard
**Description**: Build positions page in frontend

**Tasks**:
- [ ] Create `pages/positions.vue`
- [ ] Create `PositionsTable.vue` component
- [ ] Create `PositionCard.vue` for summary stats
- [ ] Add search/filter functionality
- [ ] Add navigation link from dashboard

**Dependencies**: Step 2

**Deliverables**:
- Holdings dashboard page

**Acceptance Criteria**:
- [ ] Positions page shows all holdings
- [ ] Summary cards show totals
- [ ] Search filters table
- [ ] Sortable by symbol or quantity

**Estimated Time**: 2.5 hours

---

## Frontend Checkpoint ✓

```
✅ Holdings dashboard shows all positions
✅ Quantities match expected values (split-adjusted)
✅ Summary shows total positions count
✅ Can search/filter positions by symbol
✅ Sortable table (by symbol, quantity)
```

## Related Requirements

- [ANALYZED_REQUIREMENTS.md - Phase 4](../requirements/ANALYZED_REQUIREMENTS.md#phase-4-position-calculation)

## Notes

- Use `updated_quantity` (split-adjusted) for calculations
- Exclude fractional positions < 0.1 shares
- Exclude negative positions (short sales not supported)
- CSV backup uses European number format (comma decimal)

---

## Quick Links

- [Previous Phase: Stock Splits](./PHASE_3_STOCK_SPLITS.md)
- [Next Phase: Automation](./PHASE_5_AUTOMATION.md)
- [Analyzed Requirements](../requirements/ANALYZED_REQUIREMENTS.md)
