# Phase 1: Flex API Integration

**Fetch transactions from IBKR Flex Web Service API and display them in the frontend.**

## Requirements

### Functional Requirements
- [ ] Fetch Flex Query reports from IBKR API
- [ ] Save fetched data to input directory
- [ ] Display transactions in a table with pagination
- [ ] Show fetch status and last sync time

### Non-Functional Requirements
- [ ] Performance: Fetch completes within 30 seconds
- [ ] Security: API token stored in environment variable
- [ ] Reliability: Handle API errors gracefully

## User Stories

### As a user
- I want to click a button to fetch my IBKR transactions
- So that I can see my trading history without manual exports

### As a user
- I want to see when the last sync occurred
- So that I know if my data is up to date

## Technical Specifications

### Backend

**API Endpoints**:
- `POST /api/flex/fetch` - Trigger Flex Query fetch from IBKR
- `GET /api/flex/status` - Get last fetch status and timestamp
- `GET /api/transactions` - List transactions with pagination

**New Files**:
```
backend/
├── scripts/
│   └── a_flex_fetch.py      # Flex API fetcher
└── api/
    └── routes/
        ├── flex.py          # Flex endpoints
        └── transactions.py  # Transaction endpoints
```

**Dependencies**:
- requests (for HTTP calls)

### Frontend

**Components**:
- `FetchButton.vue` - Button to trigger IBKR fetch
- `SyncStatus.vue` - Shows last sync time
- `TransactionsTable.vue` - Paginated transaction table

**Pages/Routes**:
- `pages/index.vue` - Dashboard with fetch button
- `pages/transactions.vue` - Full transaction list

## Testing Requirements

### Backend Tests
- [ ] Flex fetch script handles API errors
- [ ] Transactions endpoint returns paginated data
- [ ] Status endpoint returns correct timestamp

### Frontend Tests
- [ ] Fetch button shows loading state
- [ ] Table displays transaction data correctly
- [ ] Pagination controls work

## Acceptance Criteria

- [ ] "Fetch from IBKR" button visible on dashboard
- [ ] Loading spinner during fetch (~20 seconds)
- [ ] Success message shows record count
- [ ] Last sync time displayed
- [ ] Transactions appear in table after fetch + process
- [ ] Table pagination works

## Implementation Plan

### Step 1: Create Flex Fetch Script
**Description**: Implement the IBKR Flex Web Service API client

**Tasks**:
- [ ] Create `backend/scripts/a_flex_fetch.py`
- [ ] Implement SendRequest API call
- [ ] Implement GetStatement API call (with 20s wait)
- [ ] Save response to `input/daily_trades/` as CSV
- [ ] Add error handling and logging

**Dependencies**: Phase 0 complete

**Deliverables**:
- Working `a_flex_fetch.py` script
- CSV file saved after successful fetch

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/a_flex_fetch.py`
- [ ] CSV file created in `input/daily_trades/`
- [ ] Errors logged clearly

**Estimated Time**: 2 hours

---

### Step 2: Create Flex API Endpoints
**Description**: Add FastAPI endpoints for flex operations

**Tasks**:
- [ ] Create `backend/api/routes/flex.py`
- [ ] Add `POST /api/flex/fetch` endpoint (calls a_flex_fetch)
- [ ] Add `GET /api/flex/status` endpoint
- [ ] Store last fetch status in database or file
- [ ] Register routes in main.py

**Dependencies**: Step 1

**Deliverables**:
- Flex API endpoints working
- Status tracking implemented

**Acceptance Criteria**:
- [ ] POST `/api/flex/fetch` triggers fetch and returns result
- [ ] GET `/api/flex/status` returns last fetch info
- [ ] Errors return proper HTTP status codes

**Estimated Time**: 1.5 hours

---

### Step 3: Create Transactions API Endpoint
**Description**: Add endpoint to list transactions with pagination

**Tasks**:
- [ ] Create `backend/api/routes/transactions.py`
- [ ] Add `GET /api/transactions` with query params:
  - `page` (default: 1)
  - `limit` (default: 50)
  - `symbol` (optional filter)
- [ ] Return total count for pagination
- [ ] Register routes in main.py

**Dependencies**: Phase 0 (database)

**Deliverables**:
- Transactions endpoint with pagination

**Acceptance Criteria**:
- [ ] GET `/api/transactions` returns paginated list
- [ ] Response includes `total`, `page`, `limit`, `data`
- [ ] Symbol filter works

**Estimated Time**: 1 hour

---

### Step 4: Create Frontend Fetch UI
**Description**: Add fetch button and status display to dashboard

**Tasks**:
- [ ] Create `FetchButton.vue` component
- [ ] Create `SyncStatus.vue` component
- [ ] Add to dashboard page
- [ ] Implement API calls with loading states
- [ ] Show success/error messages

**Dependencies**: Steps 2, 3

**Deliverables**:
- Fetch button with loading state
- Sync status display

**Acceptance Criteria**:
- [ ] Button shows "Fetch from IBKR"
- [ ] Loading spinner during fetch
- [ ] Success: "Fetched X records"
- [ ] Error: Shows error message
- [ ] Last sync time updates

**Estimated Time**: 2 hours

---

### Step 5: Create Transactions Table
**Description**: Display transactions in a paginated table

**Tasks**:
- [ ] Create `TransactionsTable.vue` component
- [ ] Add columns: Symbol, Date, Quantity, Price, Proceeds, Fees
- [ ] Implement pagination controls
- [ ] Add to transactions page
- [ ] Link from dashboard

**Dependencies**: Step 3

**Deliverables**:
- Transactions table with pagination
- Transactions page

**Acceptance Criteria**:
- [ ] Table displays all transaction columns
- [ ] Pagination shows correct page info
- [ ] Can navigate between pages
- [ ] Data matches database

**Estimated Time**: 2 hours

---

## Frontend Checkpoint ✓

```
✅ "Fetch from IBKR" button visible on dashboard
✅ Loading spinner during fetch (~20 seconds)
✅ Success message: "Fetched X records"
✅ Last sync time displayed
✅ Transactions appear in table after fetch + process
✅ Table shows correct data with pagination
```

## Configuration Required

```bash
# .env
IBKR_FLEX_TOKEN=your_token_here
IBKR_QUERY_ID=your_query_id_here
```

## Related Requirements

- [ANALYZED_REQUIREMENTS.md - Phase 1](../requirements/ANALYZED_REQUIREMENTS.md#phase-1-flex-api-integration)
- [RAW_REQUIREMENTS.md - Flex Web Service](../requirements/RAW_REQUIREMENTS.md#flex-web-service-api-configuration)

## Notes

- Flex API requires ~20 second wait between SendRequest and GetStatement
- Token expires (configurable 6 hours to 1 year in IBKR Client Portal)
- User-Agent header required for API calls
- Data is T+1 (previous day's trades)

---

## Quick Links

- [Previous Phase: Project Setup](./PHASE_0_PROJECT_SETUP.md)
- [Next Phase: Daily Processing](./PHASE_2_DAILY_PROCESSING.md)
- [Analyzed Requirements](../requirements/ANALYZED_REQUIREMENTS.md)
