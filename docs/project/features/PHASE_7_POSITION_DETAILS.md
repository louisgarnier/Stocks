# Phase 7: Position Detail Tabs

**Create dedicated tabs for each held position with transaction history, FIFO P&L tracking, and tax lot simulation.**

---

## Requirements

### Functional Requirements
- [ ] Create individual position detail pages (route: `/positions/{symbol}`)
- [ ] Display all transactions for the position (chronological order)
- [ ] Calculate and display FIFO-based P&L per transaction
- [ ] Show realized vs unrealized gains
- [ ] Implement tax lot simulation tool ("what if I sell X shares?")
- [ ] Display current position summary (shares held, average cost, total P&L)
- [ ] Show fundamental metrics compliance (gross margin, ROIC, ROE, etc.)

### Non-Functional Requirements
- [ ] Performance: Load position details in < 1 second
- [ ] Accuracy: P&L calculations must match `check_acb.py` logic exactly
- [ ] Usability: Clear visualization of tax lots and P&L impact
- [ ] Responsiveness: Works on desktop and tablet

---

## Database Schema Changes

### New Tables

#### 1. `position_summary` - Cached Position Calculations
```sql
CREATE TABLE IF NOT EXISTS position_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,
    total_shares REAL NOT NULL,
    average_cost REAL NOT NULL,
    total_cost REAL NOT NULL,
    current_price REAL,
    market_value REAL,
    unrealized_gain REAL,
    unrealized_gain_pct REAL,
    total_realized_gain REAL,
    transaction_count INTEGER,
    first_purchase_date TEXT,
    last_transaction_date TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_position_summary_symbol ON position_summary(symbol);
```

#### 2. `tax_lots` - FIFO Tax Lot Tracking
```sql
CREATE TABLE IF NOT EXISTS tax_lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    purchase_date TEXT NOT NULL,
    shares_remaining REAL NOT NULL,
    cost_per_share REAL NOT NULL,
    total_cost REAL NOT NULL,
    transaction_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

CREATE INDEX idx_tax_lots_symbol ON tax_lots(symbol);
CREATE INDEX idx_tax_lots_purchase_date ON tax_lots(purchase_date);
```

---

## Configuration

### `backend/config/position_config.py`
```python
class PositionConfig:
    # FIFO Calculation Settings
    FIFO_ROUNDING_DECIMALS = 4
    MINIMUM_LOT_SIZE = 0.0001  # Ignore lots smaller than this
    
    # Tax Lot Display
    SHOW_CLOSED_LOTS = False  # Only show open lots by default
    LOT_GROUPING_THRESHOLD = 0.01  # Group lots within 1% of each other
    
    # P&L Calculation
    INCLUDE_COMMISSIONS_IN_COST_BASIS = True
    REALIZED_GAIN_PRECISION = 2  # Decimal places
    
    # Fundamental Thresholds (for compliance checking)
    FUNDAMENTAL_THRESHOLDS = {
        'gross_margin': 60.0,  # > 60%
        'roic': 12.0,          # > 12%
        'roe': 15.0,           # > 15%
        'leveraged_fcf': 20.0, # > 20%
        'interest_coverage': 3.0,  # > 3x
        'eps_growth_5y': 10.0  # > 10%
    }
```

---

## Implementation Plan

### Step 7.1: Position Summary Calculator
**Description**: Calculate position summaries with FIFO logic (extend `check_acb.py`)

**Tasks**:
- [ ] Create `backend/scripts/calculate_position_summary.py`
- [ ] Port FIFO logic from `check_acb.py`
- [ ] Calculate total shares, average cost, realized gains
- [ ] Generate tax lots (open positions only)
- [ ] Store results in `position_summary` and `tax_lots` tables
- [ ] Handle edge cases (stock splits, partial sales)

**Dependencies**: Phase 6 complete

**Deliverables**:
- `backend/scripts/calculate_position_summary.py`
- Position summaries populated in database

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/calculate_position_summary.py`
- [ ] FIFO calculations match `check_acb.py` output exactly
- [ ] Tax lots correctly track remaining shares
- [ ] Handles split-adjusted quantities

**Tests**:
- [ ] Unit test: `test_fifo_calculation_simple_case()`
- [ ] Unit test: `test_fifo_with_multiple_buys_and_sells()`
- [ ] Unit test: `test_fifo_with_stock_splits()`
- [ ] Unit test: `test_tax_lot_generation()`
- [ ] Integration test: `test_calculate_all_position_summaries()`

**Test File**: `backend/tests/test_position_summary.py`

**Estimated Time**: 4 hours

---

### Step 7.2: Tax Lot Simulation Engine
**Description**: Implement "what if I sell X shares?" simulation

**Tasks**:
- [ ] Create `backend/utils/tax_lot_simulator.py`
- [ ] Implement `simulate_sale(symbol, shares_to_sell)` function
- [ ] Calculate impact on realized gains
- [ ] Calculate new average cost of remaining shares
- [ ] Return detailed breakdown (which lots sold, P&L per lot)
- [ ] Support partial lot sales

**Dependencies**: Step 7.1

**Deliverables**:
- `backend/utils/tax_lot_simulator.py`
- Simulation API

**Acceptance Criteria**:
- [ ] Simulation returns correct P&L for sale
- [ ] Correctly identifies which lots are sold (FIFO order)
- [ ] Calculates new average cost accurately
- [ ] Handles selling more shares than held (error)

**Tests**:
- [ ] Unit test: `test_simulate_full_lot_sale()`
- [ ] Unit test: `test_simulate_partial_lot_sale()`
- [ ] Unit test: `test_simulate_multi_lot_sale()`
- [ ] Unit test: `test_simulate_oversell_error()`
- [ ] Unit test: `test_remaining_cost_basis_after_sale()`

**Test File**: `backend/tests/test_tax_lot_simulator.py`

**Estimated Time**: 3 hours

---

### Step 7.3: Position Detail API Endpoints
**Description**: Create API endpoints for position details

**Tasks**:
- [ ] Create `backend/api/routes/position_details.py`
- [ ] Add `GET /api/positions/{symbol}/summary` - Position summary
- [ ] Add `GET /api/positions/{symbol}/transactions` - Transaction history
- [ ] Add `GET /api/positions/{symbol}/tax-lots` - Current tax lots
- [ ] Add `POST /api/positions/{symbol}/simulate-sale` - Tax lot simulation
- [ ] Add `GET /api/positions/{symbol}/fundamentals` - Fundamental metrics with compliance

**Dependencies**: Steps 7.1, 7.2

**Deliverables**:
- Position detail API endpoints

**Acceptance Criteria**:
- [ ] GET `/api/positions/AAPL/summary` returns position summary
- [ ] GET `/api/positions/AAPL/transactions` returns all transactions
- [ ] GET `/api/positions/AAPL/tax-lots` returns open tax lots
- [ ] POST `/api/positions/AAPL/simulate-sale` with `{"shares": 10}` returns simulation
- [ ] GET `/api/positions/AAPL/fundamentals` returns metrics with pass/fail flags

**Tests**:
- [ ] API test: `test_get_position_summary()`
- [ ] API test: `test_get_position_transactions()`
- [ ] API test: `test_get_tax_lots()`
- [ ] API test: `test_simulate_sale_endpoint()`
- [ ] API test: `test_get_fundamentals_with_compliance()`

**Test File**: `backend/tests/test_position_details_api.py`

**Estimated Time**: 3 hours

---

### Step 7.4: Position Detail Page (Frontend)
**Description**: Create position detail page with tabs

**Tasks**:
- [ ] Create `frontend/src/pages/PositionDetail.vue`
- [ ] Implement route `/positions/:symbol`
- [ ] Create tab navigation (Overview, Transactions, Tax Lots, Fundamentals)
- [ ] Display position summary card (shares, cost, P&L)
- [ ] Show current price and market value
- [ ] Add link back to positions list

**Dependencies**: Step 7.3

**Deliverables**:
- Position detail page with tab navigation

**Acceptance Criteria**:
- [ ] Page loads at `/positions/AAPL`
- [ ] Displays position summary correctly
- [ ] Tab navigation works
- [ ] Shows loading states
- [ ] Handles errors (symbol not found)

**Tests**:
- [ ] Frontend test: `test_position_detail_page_renders()`
- [ ] Frontend test: `test_tab_navigation()`
- [ ] Frontend test: `test_loading_states()`
- [ ] Frontend test: `test_error_handling()`

**Test File**: `frontend/src/pages/__tests__/PositionDetail.test.ts`

**Estimated Time**: 3 hours

---

### Step 7.5: Transactions Tab Component
**Description**: Display transaction history with P&L breakdown

**Tasks**:
- [ ] Create `frontend/src/components/TransactionsTab.vue`
- [ ] Display transactions table (date, type, quantity, price, commission, P&L)
- [ ] Show running totals (shares held, average cost)
- [ ] Highlight buys vs sells (color coding)
- [ ] Add sorting (by date, P&L)
- [ ] Show realized gain per transaction

**Dependencies**: Step 7.4

**Deliverables**:
- Transactions tab component

**Acceptance Criteria**:
- [ ] Displays all transactions chronologically
- [ ] Shows P&L for each sell transaction
- [ ] Running totals update correctly
- [ ] Color coding: green for buys, red for sells
- [ ] Sortable columns work

**Tests**:
- [ ] Frontend test: `test_transactions_table_renders()`
- [ ] Frontend test: `test_transaction_sorting()`
- [ ] Frontend test: `test_pnl_display()`

**Test File**: `frontend/src/components/__tests__/TransactionsTab.test.ts`

**Estimated Time**: 3 hours

---

### Step 7.6: Tax Lots Tab Component
**Description**: Display current tax lots and simulation tool

**Tasks**:
- [ ] Create `frontend/src/components/TaxLotsTab.vue`
- [ ] Display tax lots table (purchase date, shares, cost basis, current value, unrealized gain)
- [ ] Add simulation input (shares to sell)
- [ ] Display simulation results (lots sold, P&L, new average cost)
- [ ] Show visual indicator of which lots would be sold
- [ ] Add "Reset" button for simulation

**Dependencies**: Step 7.4

**Deliverables**:
- Tax lots tab with simulation tool

**Acceptance Criteria**:
- [ ] Displays all open tax lots
- [ ] Simulation input accepts number of shares
- [ ] Simulation results update in real-time
- [ ] Shows which lots would be sold (FIFO order)
- [ ] Displays new average cost after simulated sale
- [ ] Reset button clears simulation

**Tests**:
- [ ] Frontend test: `test_tax_lots_table_renders()`
- [ ] Frontend test: `test_simulation_input()`
- [ ] Frontend test: `test_simulation_results_display()`
- [ ] Frontend test: `test_reset_simulation()`

**Test File**: `frontend/src/components/__tests__/TaxLotsTab.test.ts`

**Estimated Time**: 4 hours

---

### Step 7.7: Fundamentals Tab Component
**Description**: Display fundamental metrics with compliance indicators

**Tasks**:
- [ ] Create `frontend/src/components/FundamentalsTab.vue`
- [ ] Display fundamental metrics table
- [ ] Show threshold for each metric
- [ ] Add pass/fail indicator (✅/❌)
- [ ] Color code: green if passing, red if failing
- [ ] Show last updated date
- [ ] Add "Refresh Data" button

**Dependencies**: Step 7.4

**Deliverables**:
- Fundamentals tab component

**Acceptance Criteria**:
- [ ] Displays all fundamental metrics
- [ ] Shows thresholds clearly
- [ ] Pass/fail indicators correct
- [ ] Color coding works
- [ ] Refresh button triggers data update

**Tests**:
- [ ] Frontend test: `test_fundamentals_table_renders()`
- [ ] Frontend test: `test_compliance_indicators()`
- [ ] Frontend test: `test_refresh_data_button()`

**Test File**: `frontend/src/components/__tests__/FundamentalsTab.test.ts`

**Estimated Time**: 2.5 hours

---

### Step 7.8: Position Navigation Enhancement
**Description**: Add navigation from positions list to detail pages

**Tasks**:
- [ ] Update `frontend/src/pages/Positions.vue`
- [ ] Make symbol column clickable (link to detail page)
- [ ] Add "View Details" button/icon per row
- [ ] Add breadcrumb navigation on detail page
- [ ] Update positions list to show alert indicators (if any)

**Dependencies**: Step 7.4

**Deliverables**:
- Enhanced navigation between positions list and details

**Acceptance Criteria**:
- [ ] Clicking symbol navigates to detail page
- [ ] Breadcrumb shows: Home > Positions > {SYMBOL}
- [ ] Back button returns to positions list
- [ ] Navigation preserves scroll position

**Tests**:
- [ ] Frontend test: `test_navigation_to_detail_page()`
- [ ] Frontend test: `test_breadcrumb_navigation()`

**Test File**: `frontend/src/pages/__tests__/Positions.test.ts`

**Estimated Time**: 2 hours

---

## Performance Optimization

### Caching Strategy
- Cache position summaries (recalculate only on new transactions)
- Cache tax lots (update only when transactions change)
- Cache simulation results (same inputs = same output)

### Database Optimization
- Index on `tax_lots(symbol, purchase_date)` for fast FIFO queries
- Denormalize position summary for fast reads
- Use database triggers to auto-update summaries on transaction insert

### Frontend Optimization
- Lazy load tabs (only fetch data when tab is clicked)
- Virtualize transaction table for positions with 100+ transactions
- Debounce simulation input (wait 500ms after typing)

---

## Data Validation Rules

### Position Summary
- Total shares >= 0
- Average cost > 0
- Total realized gain can be negative

### Tax Lots
- Shares remaining > 0 (close lots with 0 shares)
- Cost per share > 0
- Purchase date <= today

### Simulation
- Shares to sell > 0
- Shares to sell <= total shares held
- Result must match manual FIFO calculation

---

## UI/UX Considerations

### Visual Design
- Use cards for summary metrics
- Color code P&L (green for gains, red for losses)
- Use tables for transactions and tax lots
- Add tooltips for complex metrics

### Responsive Design
- Stack tabs vertically on mobile
- Horizontal scroll for wide tables
- Collapsible sections for smaller screens

### Accessibility
- Keyboard navigation for tabs
- Screen reader labels for metrics
- High contrast mode support

---

## Acceptance Criteria

- [ ] Position detail page accessible at `/positions/{symbol}`
- [ ] All tabs render correctly (Overview, Transactions, Tax Lots, Fundamentals)
- [ ] Transaction history displays with accurate P&L
- [ ] Tax lots show current open positions
- [ ] Simulation tool calculates correct P&L and new average cost
- [ ] Fundamental metrics display with pass/fail indicators
- [ ] Navigation from positions list works
- [ ] All calculations match `check_acb.py` output
- [ ] All tests passing (unit, integration, API, frontend)
- [ ] Performance: Page loads in < 1 second

---

## Related Requirements

- [PHASE_6_DATA_INFRASTRUCTURE.md](./PHASE_6_DATA_INFRASTRUCTURE.md) - Provides fundamental data
- [PHASE_8_PRICE_CHARTS.md](./PHASE_8_PRICE_CHARTS.md) - Will add charts to position detail page

---

## Notes

- **FIFO Logic**: Must exactly match `check_acb.py` - use same rounding, same commission handling
- **Tax Lots**: Only track open lots (shares remaining > 0)
- **Simulation**: Non-destructive - doesn't modify actual data
- **Fundamental Compliance**: Visual indicator only - doesn't prevent actions
- **Performance**: Optimize for positions with 100+ transactions

---

## Quick Links

- [Previous Phase: Data Infrastructure](./PHASE_6_DATA_INFRASTRUCTURE.md)
- [Next Phase: Price Charts](./PHASE_8_PRICE_CHARTS.md)
