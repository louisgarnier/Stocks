# Phase 0: Project Setup ✅ COMPLETED

**Set up the foundational infrastructure: database, API, and basic frontend shell.**

## Requirements

### Functional Requirements
- [x] SQLite database with transactions and positions tables
- [x] FastAPI backend with health endpoint
- [x] Next.js frontend with basic layout
- [x] Frontend-backend connection verification

### Non-Functional Requirements
- [x] Performance: API responds in < 100ms for health check
- [x] Security: Environment variables for sensitive config
- [x] Usability: Clear "connected/disconnected" status in UI

## User Stories

### As a developer
- I want to have a working project structure
- So that I can build features on a solid foundation

### As a user
- I want to see if the system is connected
- So that I know the application is working

## Technical Specifications

### Backend

**API Endpoints**:
- `GET /health` - Returns `{"status": "ok", "database": "connected"}`

**Database Schema**:
```sql
-- transactions table
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT UNIQUE NOT NULL,
    source_file TEXT,
    asset_category TEXT DEFAULT 'Stocks',
    currency TEXT,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    quantity REAL NOT NULL,
    t_price REAL,
    c_price REAL,
    proceeds REAL,
    comm_fee REAL,
    basis REAL,
    original_transaction_id TEXT UNIQUE,
    stock_splits_applied TEXT,
    updated_quantity REAL,
    updated_t_price REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- positions table
CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT UNIQUE NOT NULL,
    total_updated_quantity REAL NOT NULL,
    transaction_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_transactions_symbol ON transactions(symbol);
CREATE INDEX idx_transactions_trade_date ON transactions(trade_date);
CREATE INDEX idx_transactions_original_id ON transactions(original_transaction_id);
```

**Dependencies**:
- fastapi
- uvicorn
- python-dotenv
- sqlite3 (built-in)

**Directory Structure**:
```
backend/
├── api/
│   ├── __init__.py
│   ├── main.py
│   └── routes/
│       └── __init__.py
├── database/
│   ├── __init__.py
│   ├── schema.sql
│   └── connection.py
└── requirements.txt
```

### Frontend

**Technology**: Next.js 16 with React and TypeScript

**Pages/Routes**:
- `app/page.tsx` - Dashboard with connection status

**Directory Structure**:
```
frontend/
├── app/
│   ├── page.tsx          # Main dashboard
│   ├── layout.tsx        # Root layout
│   ├── globals.css       # Global styles
│   └── api/proxy/        # API proxy route
├── next.config.ts
└── package.json
```

## Testing Requirements

### Backend Tests
- [ ] Health endpoint returns 200 with correct JSON
- [ ] Database file is created on startup
- [ ] Tables exist with correct schema

### Frontend Tests
- [ ] Dashboard page renders
- [ ] Connection status component shows correct state

## Acceptance Criteria

- [ ] `GET /health` returns `{"status": "ok"}`
- [ ] Frontend displays "Connected to API" when backend is running
- [ ] Frontend displays "Disconnected" when backend is not running
- [ ] Database file exists at `output/database/finance.db`
- [ ] Both tables created with correct columns

## Implementation Plan

### Step 1: Create Directory Structure
**Description**: Set up the project folder structure

**Tasks**:
- [ ] Create `backend/api/` directory
- [ ] Create `backend/database/` directory
- [ ] Create `input/daily_trades/` directory
- [ ] Create `input/specs/` directory
- [ ] Create `output/database/` directory
- [ ] Create `output/ibkr/` directory
- [ ] Create `archive/daily_trades/` directory
- [ ] Create `.env.example` file

**Dependencies**: None

**Deliverables**:
- Complete directory structure ready for code

**Acceptance Criteria**:
- [ ] All directories exist
- [ ] `.env.example` contains placeholder variables

**Estimated Time**: 30 minutes

---

### Step 2: Create SQLite Database Schema
**Description**: Create the database and tables

**Tasks**:
- [ ] Create `backend/database/schema.sql` with table definitions
- [ ] Create `backend/database/connection.py` for DB connection
- [ ] Create initialization script to run schema

**Dependencies**: Step 1

**Deliverables**:
- `schema.sql` file with complete table definitions
- `connection.py` with get_db() function
- Database file created at `output/database/finance.db`

**Acceptance Criteria**:
- [ ] Database file exists
- [ ] `transactions` table created with all columns
- [ ] `positions` table created with all columns
- [ ] Indexes created

**Estimated Time**: 1 hour

---

### Step 3: Create FastAPI Backend
**Description**: Set up FastAPI with health endpoint

**Tasks**:
- [ ] Create `backend/api/main.py` with FastAPI app
- [ ] Add `/health` endpoint
- [ ] Add CORS middleware for frontend
- [ ] Create `backend/requirements.txt`
- [ ] Test endpoint with curl

**Dependencies**: Step 2

**Deliverables**:
- Working FastAPI app
- Health endpoint returning JSON

**Acceptance Criteria**:
- [ ] `uvicorn backend.api.main:app --reload` starts server
- [ ] `curl http://localhost:8000/health` returns `{"status": "ok"}`
- [ ] CORS allows requests from `http://localhost:3000`

**Estimated Time**: 1 hour

---

### Step 4: Create Next.js Frontend ✅
**Description**: Initialize Next.js project with TailwindCSS

**Tasks**:
- [x] Initialize Next.js in `frontend/` directory
- [x] Install and configure TailwindCSS
- [x] Create basic layout with navigation placeholder
- [x] Create `app/page.tsx` dashboard page
- [x] Implement connection status display

**Dependencies**: Step 3

**Deliverables**:
- Working Next.js app
- Dashboard page with connection status

**Acceptance Criteria**:
- [x] `npm run dev` starts frontend on port 3000
- [x] Dashboard page loads with "IBKR Portfolio Tracker" title
- [x] Shows "Connected to API" when backend is running
- [x] Shows "No transactions yet" empty state

**Estimated Time**: 2 hours

---

## Frontend Checkpoint ✓

```
✅ Dashboard page loads at http://localhost:3000
✅ Shows "Connected to API" status (green indicator)
✅ Empty state: "No transactions yet"
✅ Clean, modern UI with TailwindCSS styling
```

## Related Requirements

- [ANALYZED_REQUIREMENTS.md - Phase 0](../requirements/ANALYZED_REQUIREMENTS.md#phase-0-project-setup)

## Notes

- Use SQLite for simplicity (no external database server needed)
- FastAPI runs on port 8000, Next.js on port 3000
- CORS must be configured for local development
- `.env` file should never be committed to git
- Frontend uses API proxy route (`/api/proxy/`) for terminal logging

---

## Quick Links

- [Requirements Workflow](../requirements/REQUIREMENTS_WORKFLOW.md)
- [Analyzed Requirements](../requirements/ANALYZED_REQUIREMENTS.md)
- [Next Phase: Flex API Integration](./PHASE_1_FLEX_API.md)
