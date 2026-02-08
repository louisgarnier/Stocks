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

-- Positions table - current holdings summary
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT UNIQUE NOT NULL,
    total_updated_quantity REAL NOT NULL,
    transaction_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Pipeline runs table - for automation tracking
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT NOT NULL,
    step_a_status TEXT,
    step_a_message TEXT,
    step_b_status TEXT,
    step_b_message TEXT,
    step_c_status TEXT,
    step_c_message TEXT,
    step_d_status TEXT,
    step_d_message TEXT,
    error_message TEXT
);

-- Sync status table - tracks last fetch time
CREATE TABLE IF NOT EXISTS sync_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    last_fetch_at TIMESTAMP,
    last_fetch_status TEXT,
    last_fetch_message TEXT,
    records_fetched INTEGER DEFAULT 0
);

-- Initialize sync_status with one row
INSERT OR IGNORE INTO sync_status (id, last_fetch_status) VALUES (1, 'never');

-- Stock splits table - stores splits fetched from Yahoo Finance
CREATE TABLE IF NOT EXISTS stock_splits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    split_date TEXT NOT NULL,
    split_ratio REAL NOT NULL,  -- e.g., 4.0 for 4-for-1 split
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    applied_at TIMESTAMP,
    UNIQUE(symbol, split_date)
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_transactions_symbol ON transactions(symbol);
CREATE INDEX IF NOT EXISTS idx_transactions_trade_date ON transactions(trade_date);
CREATE INDEX IF NOT EXISTS idx_transactions_original_id ON transactions(original_transaction_id);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_stock_splits_symbol ON stock_splits(symbol);
CREATE INDEX IF NOT EXISTS idx_stock_splits_date ON stock_splits(split_date);




