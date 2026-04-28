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

-- Updated Transactions table - stores split/spinoff adjusted transaction values
CREATE TABLE IF NOT EXISTS updated_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    original_quantity REAL NOT NULL,
    original_price REAL NOT NULL,
    updated_quantity REAL NOT NULL,
    updated_price REAL NOT NULL,
    split_ratio REAL NOT NULL,
    ca_id INTEGER,
    ca_type TEXT NOT NULL,
    ca_date TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id) ON DELETE CASCADE,
    FOREIGN KEY (ca_id) REFERENCES corporate_actions(id) ON DELETE CASCADE
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_transactions_symbol ON transactions(symbol);
CREATE INDEX IF NOT EXISTS idx_transactions_trade_date ON transactions(trade_date);
CREATE INDEX IF NOT EXISTS idx_transactions_original_id ON transactions(original_transaction_id);
CREATE INDEX IF NOT EXISTS idx_import_logs_date ON import_logs(import_date);
CREATE INDEX IF NOT EXISTS idx_corporate_actions_sec_id ON corporate_actions(sec_id);
CREATE INDEX IF NOT EXISTS idx_corporate_actions_type ON corporate_actions(ca_type);
CREATE INDEX IF NOT EXISTS idx_corporate_actions_ex_date ON corporate_actions(ex_date);
CREATE INDEX IF NOT EXISTS idx_updated_transactions_transaction_id ON updated_transactions(transaction_id);
CREATE INDEX IF NOT EXISTS idx_updated_transactions_symbol ON updated_transactions(symbol);
CREATE INDEX IF NOT EXISTS idx_updated_transactions_ca_id ON updated_transactions(ca_id);

-- Vue consolidée : transactions ajustées pour les splits
-- Utilise updated_transactions en priorité, sinon les valeurs originales
CREATE VIEW IF NOT EXISTS transactions_adjusted AS
SELECT 
    t.transaction_id,
    t.symbol,
    t.trade_date,
    t.currency,
    t.asset_category,
    t.source_file,
    t.proceeds,
    t.comm_fee,
    t.basis,
    t.created_at,
    t.updated_at,
    -- Quantité et prix : utiliser updated si disponible, sinon original
    COALESCE(ut.updated_quantity, t.quantity) as quantity,
    COALESCE(ut.updated_price, t.t_price) as t_price,
    -- Valeurs originales (toujours disponibles)
    t.quantity as original_quantity,
    t.t_price as original_price,
    -- Informations sur l'ajustement
    CASE WHEN ut.transaction_id IS NOT NULL THEN 1 ELSE 0 END as is_adjusted,
    ut.split_ratio,
    ut.ca_id,
    ut.ca_type,
    ut.ca_date
FROM transactions t
LEFT JOIN updated_transactions ut ON t.transaction_id = ut.transaction_id
WHERE t.symbol NOT LIKE '%.%';  -- Exclure Forex

-- Positions imported from IBKR Flex Query (source of truth)
CREATE TABLE IF NOT EXISTS positions_ibkr (
    symbol TEXT PRIMARY KEY,
    quantity REAL NOT NULL,
    cost_basis_money REAL,
    cost_basis_price REAL,
    mark_price REAL,
    position_value REAL,
    unrealized_pnl REAL,
    currency TEXT,
    asset_category TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_positions_ibkr_symbol ON positions_ibkr(symbol);

-- Tracked universe — symbols we ingest market data for
CREATE TABLE IF NOT EXISTS tracked_universe (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    sector TEXT,
    currency TEXT,
    exchange TEXT,
    benchmark TEXT,
    sources TEXT NOT NULL DEFAULT '[]',  -- JSON array, e.g. ["sp500", "ibkr_position"]
    enabled INTEGER NOT NULL DEFAULT 1,
    added_at TIMESTAMP NOT NULL,
    last_synced_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tracked_universe_enabled ON tracked_universe(enabled);

-- Index list metadata — e.g., S&P 500 enable/disable + last refresh
CREATE TABLE IF NOT EXISTS tracked_indices (
    name TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 0,
    last_refreshed_at TIMESTAMP,
    symbol_count INTEGER DEFAULT 0
);

-- Market OHLCV data — one row per symbol per day
CREATE TABLE IF NOT EXISTS market_data (
    symbol TEXT NOT NULL,
    time TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    adj_close REAL,
    volume INTEGER,
    PRIMARY KEY (symbol, time)
);
CREATE INDEX IF NOT EXISTS idx_market_data_symbol ON market_data(symbol);
CREATE INDEX IF NOT EXISTS idx_market_data_time ON market_data(time);
