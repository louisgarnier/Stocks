-- Database Schema - IBKR Portfolio Tracker
-- ⚠️ Before making changes, read: ../../docs/workflow/BEST_PRACTICES.md

-- Transactions table - stores all IBKR trades
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT UNIQUE NOT NULL,
    source_file TEXT,
    asset_category TEXT DEFAULT 'Stocks',
    currency TEXT,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    trade_time TEXT,
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

-- Import logs table - tracks each file import
CREATE TABLE IF NOT EXISTS import_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    parsed INTEGER DEFAULT 0,
    inserted INTEGER DEFAULT 0,
    skipped INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    status TEXT DEFAULT 'success'
);

-- Corporate Actions table - stores dividends, splits, etc.
CREATE TABLE IF NOT EXISTS corporate_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sec_id TEXT NOT NULL,
    ca_type TEXT NOT NULL,
    ex_date TEXT,
    record_date TEXT,
    pay_date TEXT,
    declared_date TEXT,
    amount REAL,
    currency TEXT,
    split_ratio REAL,
    split_from REAL,
    split_to REAL,
    split_direction TEXT,
    dividend_type TEXT,
    frequency TEXT,
    adjusted INTEGER DEFAULT 1,
    source TEXT DEFAULT 'yfinance',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sec_id, ca_type, ex_date)
);

-- Corporate Actions Status table - tracks fetch status per symbol
CREATE TABLE IF NOT EXISTS corporate_actions_status (
    sec_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK(status IN ('grey', 'green', 'orange')),
    last_fetched_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_transactions_symbol ON transactions(symbol);
CREATE INDEX IF NOT EXISTS idx_transactions_trade_date ON transactions(trade_date);
CREATE INDEX IF NOT EXISTS idx_transactions_original_id ON transactions(original_transaction_id);
CREATE INDEX IF NOT EXISTS idx_import_logs_date ON import_logs(import_date);
CREATE INDEX IF NOT EXISTS idx_corporate_actions_sec_id ON corporate_actions(sec_id);
CREATE INDEX IF NOT EXISTS idx_corporate_actions_type ON corporate_actions(ca_type);
CREATE INDEX IF NOT EXISTS idx_corporate_actions_ex_date ON corporate_actions(ex_date);
