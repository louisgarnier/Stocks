# Analyzed Requirements - IBKR Portfolio Tracker

## Build Philosophy

**Frontend-First Validation**: Each implementation step is validated through the Nuxt3 frontend before moving to the next step. This ensures:
- Visible progress at each stage
- Early detection of issues
- Clear acceptance criteria
- User can verify each component works

---

## Implementation Phases Overview

| Phase | Name | Backend | Frontend Checkpoint |
|-------|------|---------|---------------------|
| 0 | Project Setup | SQLite DB + FastAPI skeleton | Empty dashboard loads |
| 1 | Flex API Fetch | `a_flex_fetch.py` + transactions table | "Fetch" button + transactions displayed |
| 2 | Daily Processing | `b_daily_trades.py` | New transactions appear, duplicates skipped |
| 3 | Stock Splits | `c_trans_update.py` | Split-adjusted values shown |
| 4 | Positions | `d_positions.py` | Holdings dashboard complete |
| 5 | Automation | Scheduler + monitoring | Pipeline status panel |

---

## Phase 0: Project Setup

### Objective
Set up the foundational infrastructure: database, API, and basic frontend shell.

### Backend Tasks
- [ ] Create SQLite database with `transactions` and `positions` tables
- [ ] Set up FastAPI with basic health endpoint
- [ ] Create `.env` file structure for IBKR credentials
- [ ] Set up project directory structure

### Frontend Tasks
- [ ] Initialize Nuxt3 project with TailwindCSS
- [ ] Create basic layout with navigation
- [ ] Create empty dashboard page
- [ ] Connect to FastAPI backend (health check)

### Frontend Checkpoint ✓
```
✅ Dashboard page loads
✅ Shows "Connected to API" status
✅ Empty state: "No transactions yet"
```

### Acceptance Criteria
- [ ] `GET /health` returns `{"status": "ok"}`
- [ ] Frontend displays connection status
- [ ] Database file exists at `output/database/finance.db`

---

## Phase 1: Flex API Integration

### Objective
Fetch transactions directly from IBKR Flex Web Service API.

### Backend Tasks
- [ ] Create `a_flex_fetch.py` script
- [ ] Implement two-step API workflow (SendRequest → GetStatement)
- [ ] Save fetched data to `input/daily_trades/`
- [ ] Create `POST /api/flex/fetch` endpoint to trigger fetch
- [ ] Create `GET /api/flex/status` endpoint for fetch status
- [ ] Create `GET /api/transactions` endpoint with pagination

### Frontend Tasks
- [ ] Add "Fetch from IBKR" button on dashboard
- [ ] Show loading state during fetch (~20 seconds)
- [ ] Display fetch result (success/error, records fetched)
- [ ] Show last fetch timestamp
- [ ] Create transactions table with columns:
  - Symbol, Date, Quantity, Price, Proceeds, Fees
- [ ] Add pagination controls

### Frontend Checkpoint ✓
```
✅ "Fetch from IBKR" button visible
✅ Loading spinner during fetch
✅ Success message: "Fetched X records"
✅ Last sync time displayed
✅ Transactions appear in table after fetch + process
✅ Table shows correct data with pagination
```

### Acceptance Criteria
- [ ] Flex API returns data successfully
- [ ] CSV saved to `input/daily_trades/`
- [ ] Frontend shows fetch status in real-time
- [ ] Transactions displayed in table with pagination

### Configuration Required
```bash
# .env
IBKR_FLEX_TOKEN=your_token_here
IBKR_QUERY_ID=your_query_id_here
```

---

## Phase 2: Daily Trade Processing

### Objective
Process fetched flex files and insert new transactions into database with deduplication.

### Backend Tasks
- [ ] Adapt `b_daily_trades.py` to work with new structure
- [ ] Implement deduplication using `TransactionID`
- [ ] Create `POST /api/pipeline/process-trades` endpoint
- [ ] Archive processed files to `archive/daily_trades/`
- [ ] Log processing results

### Frontend Tasks
- [ ] Add "Process New Trades" button
- [ ] Show processing log/results
- [ ] Update transaction count after processing
- [ ] Highlight newly added transactions

### Frontend Checkpoint ✓
```
✅ "Process" button triggers processing
✅ Log shows: "X new transactions added, Y duplicates skipped"
✅ Transaction table updates with new entries
✅ New entries highlighted or marked
```

### Acceptance Criteria
- [ ] New transactions inserted correctly
- [ ] Duplicates are skipped (not inserted twice)
- [ ] Processed files moved to archive
- [ ] Frontend reflects new transaction count

---

## Phase 3: Stock Split Adjustments

### Objective
Apply stock split adjustments to historical transactions.

### Backend Tasks
- [ ] Adapt `c_trans_update.py` to work with new structure
- [ ] Load splits from `input/specs/stock_splits.csv`
- [ ] Update `updated_quantity` and `updated_t_price` columns
- [ ] Create `POST /api/pipeline/apply-splits` endpoint
- [ ] Create `GET /api/splits` endpoint to view configured splits

### Frontend Tasks
- [ ] Add "Apply Splits" button
- [ ] Show split configuration table (editable)
- [ ] Display both original and adjusted values in transaction table
- [ ] Visual indicator for split-adjusted transactions

### Frontend Checkpoint ✓
```
✅ Split configuration visible
✅ Transactions show original AND adjusted quantities
✅ Split-adjusted rows have visual indicator (icon/badge)
✅ Log shows: "X transactions adjusted for splits"
```

### Acceptance Criteria
- [ ] AAPL, TSLA, NVDA splits applied correctly (if applicable)
- [ ] `stock_splits_applied` column populated
- [ ] Frontend shows both original and adjusted values

---

## Phase 4: Position Calculation

### Objective
Calculate current holdings from all transactions and display on dashboard.

### Backend Tasks
- [ ] Adapt `d_positions.py` to work with new structure
- [ ] Calculate positions using `updated_quantity` (split-adjusted)
- [ ] Update `positions` table
- [ ] Create `GET /api/positions` endpoint
- [ ] Export positions to CSV backup

### Frontend Tasks
- [ ] Create holdings dashboard with:
  - Symbol, Quantity, Transaction Count
- [ ] Add summary cards (total positions, total shares)
- [ ] Sort by quantity or symbol
- [ ] Filter positions (search by symbol)

### Frontend Checkpoint ✓
```
✅ Holdings dashboard shows all positions
✅ Quantities match expected values (split-adjusted)
✅ Summary shows total positions count
✅ Can search/filter positions
```

### Acceptance Criteria
- [ ] Positions calculated correctly (sum of adjusted quantities)
- [ ] Zero/negative positions excluded
- [ ] Frontend matches database positions exactly

---

## Phase 5: Automation & Monitoring

### Objective
Automate the daily pipeline and provide monitoring dashboard.

### Backend Tasks
- [ ] Create pipeline orchestrator (runs A→B→C→D in sequence)
- [ ] Add scheduler (cron or APScheduler)
- [ ] Create `pipeline_runs` table for logging
- [ ] Create `GET /api/pipeline/history` endpoint
- [ ] Add error alerting (optional: email/webhook)

### Frontend Tasks
- [ ] Create pipeline status panel showing:
  - Last run time
  - Each step status (success/failed/pending)
  - Run duration
- [ ] Add "Run Full Pipeline" button
- [ ] Show pipeline history (last 10 runs)
- [ ] Error display with details

### Frontend Checkpoint ✓
```
✅ Pipeline panel shows all 4 steps
✅ Each step shows status (✓/✗/⏳)
✅ "Run Pipeline" executes all steps
✅ History shows past runs with results
```

### Acceptance Criteria
- [ ] Full pipeline runs successfully end-to-end
- [ ] Each step logged with timestamp and result
- [ ] Frontend reflects real-time pipeline status
- [ ] Scheduler runs daily at configured time (optional)

---

## Tech Stack Summary

| Layer | Technology |
|-------|------------|
| **Frontend** | Nuxt3, Vue 3, TailwindCSS, Pinia (state) |
| **Backend** | Python, FastAPI, SQLite |
| **API Integration** | IBKR Flex Web Service (HTTP) |
| **Scheduling** | APScheduler or system cron |

---

## Directory Structure

```
Stocks/
├── backend/
│   ├── api/
│   │   ├── main.py              # FastAPI app
│   │   ├── routes/
│   │   │   ├── transactions.py
│   │   │   ├── positions.py
│   │   │   ├── flex.py
│   │   │   └── pipeline.py
│   │   └── models/
│   ├── scripts/
│   │   ├── a_flex_fetch.py
│   │   ├── b_daily_trades.py
│   │   ├── c_trans_update.py
│   │   └── d_positions.py
│   └── database/
│       └── schema.sql
├── frontend/
│   ├── pages/
│   │   ├── index.vue            # Dashboard
│   │   ├── transactions.vue
│   │   ├── positions.vue
│   │   └── pipeline.vue
│   └── components/
├── input/
│   ├── daily_trades/            # Flex files land here
│   └── specs/
│       └── stock_splits.csv
├── output/
│   ├── database/
│   │   └── finance.db
│   └── ibkr/                    # CSV backups
├── archive/
│   └── daily_trades/            # Processed files
└── .env                         # IBKR credentials
```

---

## Related Documents

- [Raw Requirements](./RAW_REQUIREMENTS.md)
- [Features Directory](../features/README.md)

