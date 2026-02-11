# Phase 3: Updated Transactions (Stock Splits & Spin-offs)

**Apply stock splits and spin-offs from Corporate Actions to create adjusted transaction values.**

## Overview

When Corporate Actions (splits, spin-offs) are fetched from yfinance, this feature automatically calculates adjusted quantities and prices for affected transactions and stores them in a dedicated `updated_transactions` table.

## Requirements

### Functional Requirements
- [ ] Create `updated_transactions` table with adjusted values
- [ ] Apply split/spin-off adjustments when "🔄 Fetch from yfinance" is triggered
- [ ] Display updated transactions in a new frontend tab
- [ ] Synchronize deletions between `transactions` and `updated_transactions`

### Non-Functional Requirements
- [ ] Accuracy: Split calculations must preserve total position value
- [ ] Idempotency: Re-running produces same result (no duplicates)
- [ ] Synchronization: Deleting a transaction removes its updated version

## User Stories

### As a user
- I want stock splits applied automatically when I fetch Corporate Actions
- So that my position quantities reflect post-split values

### As a user
- I want to see both original and adjusted transaction values
- So that I can verify the adjustments are correct

### As a user
- I want to filter and delete updated transactions like regular transactions
- So that I have full control over my data

## Technical Specifications

### Database Schema

**New Table: `updated_transactions`**
```sql
CREATE TABLE IF NOT EXISTS updated_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT NOT NULL,           -- FK to transactions.transaction_id
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    original_quantity REAL NOT NULL,
    original_price REAL NOT NULL,
    updated_quantity REAL NOT NULL,         -- After split adjustment
    updated_price REAL NOT NULL,            -- After split adjustment
    split_ratio REAL NOT NULL,              -- The ratio applied (e.g., 4.0 for 4:1)
    ca_id INTEGER,                          -- FK to corporate_actions.id
    ca_type TEXT NOT NULL,                  -- 'split' or 'spinoff'
    ca_date TEXT NOT NULL,                  -- Date of the corporate action
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id) ON DELETE CASCADE
);
```

### Split Calculation Logic

**Split 4:1 (ratio = 4.0)**
For transactions BEFORE the split date:
- `updated_quantity = original_quantity × ratio`
- `updated_price = original_price ÷ ratio`
- Total value preserved: 10 shares × $400 = 40 shares × $100 = $4,000

**Reverse Split 1:4 (ratio = 0.25)**
For transactions BEFORE the split date:
- `updated_quantity = original_quantity × ratio`
- `updated_price = original_price ÷ ratio`
- Total value preserved: 40 shares × $100 = 10 shares × $400 = $4,000

**Multiple Splits**
When a security has multiple splits, apply them chronologically:
1. Sort splits by date (oldest first)
2. For each split, adjust transactions between previous split date and current split date
3. Cumulative effect: a transaction before ALL splits gets ALL ratios applied

### Backend

**Modified Files**:
```
backend/
├── database/
│   └── schema.sql                    # Add updated_transactions table
├── scripts/
│   └── fetch_corporate_actions.py    # Add split application logic
├── api/routes/
│   ├── transactions.py               # Add cascade delete logic
│   └── updated_transactions.py       # NEW: CRUD for updated transactions
└── utils/
    └── split_calculator.py           # NEW: Split calculation utilities
```

**API Endpoints**:
- `GET /api/updated-transactions` - List updated transactions (with pagination, filters)
- `DELETE /api/updated-transactions` - Delete all updated transactions
- `DELETE /api/updated-transactions/{id}` - Delete specific updated transaction
- `POST /api/updated-transactions/delete-batch` - Delete selected updated transactions

### Frontend

**New Tab: "Updated Transactions"**
- Same UI pattern as Transactions tab
- Columns: Transaction ID, Symbol, Date, Original Qty, Original Price, Updated Qty, Updated Price, Split Ratio, CA Type
- Features: Filter by symbol, checkbox selection, delete selected, delete all
- Empty state: "No updated transactions. Fetch Corporate Actions to apply splits."

**Card in Corporate Actions tab**:
- Shows count of updated transactions
- Links to Updated Transactions tab

## Trigger Flow

```
User clicks "🔄 Fetch from yfinance"
    │
    ▼
fetch_corporate_actions() runs
    │
    ├── Fetches CAs from yfinance
    ├── Inserts into corporate_actions table
    ├── Updates CA status (green/grey)
    │
    ▼
For each CA where ca_type = 'split' or 'spinoff':
    │
    ├── Get all transactions for this symbol
    ├── Filter transactions with trade_date < ca_date
    ├── Calculate updated_quantity and updated_price
    ├── Insert/Update into updated_transactions table
    │
    ▼
Frontend refreshes Updated Transactions tab
```

## Synchronization Rules

1. **Transaction Deleted** → Cascade delete its `updated_transactions` entries
2. **CA Deleted** → Remove `updated_transactions` linked to that CA
3. **Re-fetch CAs** → Recalculate all `updated_transactions` (idempotent)

## Acceptance Criteria

- [ ] `updated_transactions` table created in schema
- [ ] Splits applied automatically on "Fetch from yfinance"
- [ ] Updated Transactions tab displays adjusted values
- [ ] Filter by symbol works
- [ ] Delete selected/all works
- [ ] Deleting a transaction removes its updated version
- [ ] Multiple splits applied correctly in chronological order
- [ ] Total position value preserved after split adjustment

## Implementation Plan

### Step 1: Database Schema
**Description**: Add `updated_transactions` table

**Tasks**:
- [ ] Add table definition to `schema.sql`
- [ ] Add foreign key with CASCADE delete
- [ ] Create index on `transaction_id` and `symbol`

**Acceptance Criteria**:
- [ ] Table created successfully
- [ ] CASCADE delete works when transaction deleted

**Estimated Time**: 30 minutes

---

### Step 2: Split Calculator Utility
**Description**: Create utility functions for split calculations

**Tasks**:
- [ ] Create `backend/utils/split_calculator.py`
- [ ] Implement `calculate_split_adjustment(qty, price, ratio)`
- [ ] Implement `apply_splits_to_transactions(symbol, splits, transactions)`
- [ ] Handle multiple splits chronologically

**Acceptance Criteria**:
- [ ] Split 4:1 correctly multiplies qty by 4, divides price by 4
- [ ] Reverse split 1:4 correctly multiplies qty by 0.25
- [ ] Multiple splits applied in correct order

**Estimated Time**: 1 hour

---

### Step 3: Modify fetch_corporate_actions
**Description**: Apply splits when CAs are fetched

**Tasks**:
- [ ] After inserting CAs, check for splits/spinoffs
- [ ] For each split, get affected transactions
- [ ] Calculate and insert updated_transactions
- [ ] Log count of updated transactions

**Acceptance Criteria**:
- [ ] Splits applied automatically on fetch
- [ ] Log shows "X transactions updated for splits"
- [ ] Idempotent: re-running doesn't create duplicates

**Estimated Time**: 2 hours

---

### Step 4: API Endpoints for Updated Transactions
**Description**: Create CRUD endpoints

**Tasks**:
- [ ] Create `backend/api/routes/updated_transactions.py`
- [ ] Implement GET with pagination and symbol filter
- [ ] Implement DELETE all
- [ ] Implement DELETE batch
- [ ] Register router in main.py

**Acceptance Criteria**:
- [ ] GET returns paginated results
- [ ] Filter by symbol works
- [ ] DELETE operations work

**Estimated Time**: 1.5 hours

---

### Step 5: Cascade Delete Logic
**Description**: Sync deletions between tables

**Tasks**:
- [ ] Verify CASCADE delete works via FK
- [ ] Add explicit delete in transaction delete endpoints (backup)
- [ ] Test deletion scenarios

**Acceptance Criteria**:
- [ ] Deleting transaction removes updated_transaction
- [ ] Deleting CA removes related updated_transactions

**Estimated Time**: 30 minutes

---

### Step 6: Frontend - Updated Transactions Tab
**Description**: Create new tab in dashboard

**Tasks**:
- [ ] Add "Updated Transactions" tab
- [ ] Create table with all columns
- [ ] Add symbol filter
- [ ] Add checkbox selection
- [ ] Add delete selected/all buttons
- [ ] Add empty state message
- [ ] Refresh after CA fetch

**Acceptance Criteria**:
- [ ] Tab displays updated transactions
- [ ] Filter works
- [ ] Delete works
- [ ] Empty state shown when no data

**Estimated Time**: 2 hours

---

## Notes

- Splits are fetched from yfinance as part of Corporate Actions
- The `ratio` field in yfinance data indicates the split ratio
- Spin-offs may have different ratio semantics (to be verified)
- Only transactions BEFORE the CA date are adjusted

---

## Quick Links

- [Previous Phase: Daily Processing](./PHASE_2_DAILY_PROCESSING.md)
- [Next Phase: Positions](./PHASE_4_POSITIONS.md)
