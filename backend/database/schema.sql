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

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_transactions_symbol ON transactions(symbol);
CREATE INDEX IF NOT EXISTS idx_transactions_trade_date ON transactions(trade_date);
CREATE INDEX IF NOT EXISTS idx_transactions_original_id ON transactions(original_transaction_id);
CREATE INDEX IF NOT EXISTS idx_import_logs_date ON import_logs(import_date);
