# Phase 1: Flex API Integration ✅ COMPLETED

**Fetch transactions from IBKR Flex Web Service API and display them in the frontend.**

## Requirements

### Functional Requirements
- [x] Fetch Flex Query reports from IBKR API
- [x] Parse XML and insert transactions into database
- [x] Display transactions in a table with pagination
- [x] Show fetch status and last sync time
- [x] Column sorting (click headers)
- [x] Symbol filtering (partial match)

### Non-Functional Requirements
- [x] Performance: Fetch completes within 30 seconds
- [x] Security: API token stored in environment variable
- [x] Reliability: Handle API errors gracefully
- [x] Deduplication: Skip existing transactions (by TransactionID)

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

**Technology**: Next.js 16 with React and TypeScript

**Features** (all in `app/page.tsx`):
- Sync button to trigger IBKR fetch
- Sync status with last fetch time
- Transactions table with pagination
- Sortable columns (click headers)
- Filter row for symbol search
- Page size selector (25/50/100/200)

**Pages/Routes**:
- `app/page.tsx` - Dashboard with all features

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

### Step 1: Create Flex Fetch Script ✅
**Description**: Implement the IBKR Flex Web Service API client

**Tasks**:
- [x] Create `backend/scripts/a_flex_fetch.py`
- [x] Implement SendRequest API call
- [x] Implement GetStatement API call (with 20s wait)
- [x] Save response to `input/daily_trades/` as XML
- [x] Parse XML and insert transactions into database
- [x] Add error handling and logging
- [x] Deduplication by TransactionID

**Dependencies**: Phase 0 complete

**Deliverables**:
- Working `a_flex_fetch.py` script
- XML file saved after successful fetch
- Transactions inserted into database

**Acceptance Criteria**:
- [x] Script runs: `python backend/scripts/a_flex_fetch.py`
- [x] XML file created in `input/daily_trades/`
- [x] Transactions inserted with deduplication
- [x] Errors logged clearly

**Estimated Time**: 2 hours

---

### Step 2: Create Flex API Endpoints ✅
**Description**: Add FastAPI endpoints for flex operations

**Tasks**:
- [x] Create `backend/api/routes/flex.py`
- [x] Add `POST /api/flex/fetch` endpoint (calls a_flex_fetch)
- [x] Add `GET /api/flex/status` endpoint
- [x] Store last fetch status in database (sync_status table)
- [x] Register routes in main.py

**Dependencies**: Step 1

**Deliverables**:
- Flex API endpoints working
- Status tracking implemented

**Acceptance Criteria**:
- [x] POST `/api/flex/fetch` triggers fetch and returns result
- [x] GET `/api/flex/status` returns last fetch info
- [x] Errors return proper HTTP status codes

**Estimated Time**: 1.5 hours

---

### Step 3: Create Transactions API Endpoint ✅
**Description**: Add endpoint to list transactions with pagination

**Tasks**:
- [x] Create `backend/api/routes/transactions.py`
- [x] Add `GET /api/transactions` with query params:
  - `page` (default: 1)
  - `limit` (default: 25, max: 200)
  - `symbol` (optional filter, partial match)
  - `sort_by` (column name)
  - `sort_order` (asc/desc)
- [x] Return total count for pagination
- [x] Add `GET /api/transactions/symbols` for filter dropdown
- [x] Register routes in main.py

**Dependencies**: Phase 0 (database)

**Deliverables**:
- Transactions endpoint with pagination, sorting, filtering

**Acceptance Criteria**:
- [x] GET `/api/transactions` returns paginated list
- [x] Response includes `total`, `page`, `limit`, `data`
- [x] Symbol filter works (partial match with LIKE)
- [x] Sorting works on all columns

**Estimated Time**: 1 hour

---

### Step 4: Create Frontend UI ✅
**Description**: Add fetch button, status display, and transactions table to dashboard

**Tasks**:
- [x] Implement sync button in `app/page.tsx`
- [x] Implement sync status display
- [x] Implement transactions table with columns: Date, Symbol, Quantity, Price, Proceeds, Fees
- [x] Implement pagination controls (25/50/100/200 per page)
- [x] Implement sortable column headers
- [x] Implement filter row for symbol search
- [x] API calls with loading states
- [x] Success/error messages

**Dependencies**: Steps 2, 3

**Deliverables**:
- Complete dashboard with all features in single page

**Acceptance Criteria**:
- [x] Button shows "Sync from IBKR"
- [x] Loading spinner during fetch
- [x] Success: Shows record count
- [x] Last sync time updates
- [x] Table displays all transaction columns
- [x] Pagination works with page size selector
- [x] Sorting works (click headers)
- [x] Filtering works (type in filter row)

**Estimated Time**: 4 hours

---

## Frontend Checkpoint ✓

```
✅ "Sync from IBKR" button visible on dashboard
✅ Loading spinner during fetch (~20 seconds)
✅ Success message shows record count
✅ Last sync time displayed
✅ Transactions appear in table after fetch
✅ Table shows correct data with pagination (25/50/100/200)
✅ Sortable columns (click headers)
✅ Filter row for symbol search
✅ 661 transactions imported successfully
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
