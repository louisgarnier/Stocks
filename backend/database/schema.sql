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
    last_synced_at TIMESTAMP,
    yfinance_symbol TEXT  -- override when the bare symbol isn't a valid yfinance ticker
                          -- (e.g. IBKR reports 'SGLD' but yfinance needs 'SGLD.AS').
                          -- NULL means use the symbol column as-is.
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

-- Technical indicators per (symbol, time) — pandas-computed from market_data
CREATE TABLE IF NOT EXISTS indicators (
    symbol TEXT NOT NULL,
    time TEXT NOT NULL,
    ma_50 REAL,
    ma_100 REAL,
    ma_150 REAL,
    ma_200 REAL,
    bb_upper_20 REAL,
    bb_lower_20 REAL,
    bb_width REAL,
    rsi_14 REAL,
    mrsi REAL,
    atr_14 REAL,
    volume_ma_20 REAL,
    PRIMARY KEY (symbol, time)
);
CREATE INDEX IF NOT EXISTS idx_indicators_time ON indicators(time);

-- Sell signals computed per held symbol per signal_type.
-- One row per (symbol, signal_type); UPSERT on each evaluation.
-- Sold-out symbols are deleted on next sync.
CREATE TABLE IF NOT EXISTS holding_signals (
    symbol TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    fired INTEGER NOT NULL,
    value REAL,
    threshold REAL,
    last_evaluated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (symbol, signal_type)
);
CREATE INDEX IF NOT EXISTS idx_holding_signals_symbol ON holding_signals(symbol);

-- Global on/off + threshold config per signal_type.
CREATE TABLE IF NOT EXISTS signal_settings (
    signal_type TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 1,
    threshold REAL
);

-- Seed defaults; INSERT OR IGNORE keeps it idempotent across boots.
INSERT OR IGNORE INTO signal_settings (signal_type, enabled, threshold) VALUES
    ('ma50_break',        1, NULL),
    ('ma100_break',       1, NULL),
    ('ma150_break',       1, NULL),
    ('ma200_break',       1, NULL),
    ('death_cross',       1, NULL),
    ('volume_dryup',      1, NULL),
    ('distribution_day',  1, NULL),
    ('rsi_weakness',      1, NULL),
    ('mrsi_flip',         1, NULL),
    ('trailing_drawdown', 1, 0.10),
    ('stop_loss',         1, 0.08);

-- One row per sync action attempt. Captures every POST to /api/sync/* plus
-- manual ticker adds. Replaces import_logs as the "what's working / what's
-- bugging" view; import_logs is left in place as legacy IBKR-only history.
CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_ms INTEGER,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT,
    details_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_sync_runs_started ON sync_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sync_runs_action ON sync_runs(action);

-- ============================================================
-- SCREENER (Epic E) — Phase 1
-- ============================================================

-- Fundamentals snapshot (1 row/symbol, overwritten). QUALITY SCORECARD.
CREATE TABLE IF NOT EXISTS fundamentals (
    symbol TEXT PRIMARY KEY,
    long_name TEXT, sector TEXT, industry TEXT, country TEXT,
    currency TEXT, exchange TEXT, quote_type TEXT,
    -- quality gate raw values
    gross_margin REAL, roe REAL, roic REAL, roic_method TEXT,
    levered_fcf_margin REAL, interest_cover REAL, eps_5y_growth REAL, free_cashflow REAL,
    gates_passed INTEGER, gates_total INTEGER,
    -- raw statement inputs (for recompute)
    ebit REAL, tax_provision REAL, total_revenue REAL, total_debt REAL,
    total_equity REAL, cash REAL, interest_expense REAL, eps_annual_json TEXT,
    -- context
    market_cap REAL, trailing_pe REAL, forward_pe REAL, trailing_eps REAL, forward_eps REAL,
    dividend_yield REAL, recommendation_mean REAL, recommendation_key TEXT,
    number_of_analyst_opinions INTEGER, target_mean_price REAL,
    target_high_price REAL, target_low_price REAL,
    -- earnings beat/miss
    earnings_history_json TEXT, beat_rate_4q REAL,
    -- meta
    fetched_at TIMESTAMP, fetch_error TEXT, fields_missing_json TEXT
);

-- Screening signals (latest-only, f_watch). Holds only what indicators lacks.
CREATE TABLE IF NOT EXISTS screen_signals (
    symbol TEXT PRIMARY KEY,
    date TEXT,
    momentum_5d REAL, momentum_20d REAL, momentum_60d REAL, multi_factor_momentum REAL,
    vs_benchmark REAL,
    price_vs_ma50 TEXT, above_ma50 INTEGER, above_ma100 INTEGER, above_ma150 INTEGER, above_ma200 INTEGER,
    ma_cross_status TEXT, trend_aligned INTEGER, is_8d_consec INTEGER,
    volume INTEGER, avg_volume_20 REAL, volume_spike INTEGER,
    high_52w REAL, low_52w REAL, dist_from_52w_high REAL, dist_from_52w_low REAL, near_52w_high INTEGER,
    last_evaluated_at TIMESTAMP
);

-- Current consolidation/base per symbol (latest-only, g_consolidation).
CREATE TABLE IF NOT EXISTS consolidation_patterns (
    symbol TEXT PRIMARY KEY,
    date TEXT, timeframe TEXT, detection_method TEXT,
    support_level REAL, resistance_level REAL, range_pct REAL, duration_days INTEGER,
    quality_score REAL, tightness_score REAL, touch_score REAL, duration_score REAL,
    volume_score REAL, freshness_score REAL,
    total_touches INTEGER, zigzag_swings INTEGER, boundary_touches INTEGER, pct_closes_in_channel REAL,
    volume_trend TEXT, volume_decline_pct REAL, price_position_pct REAL, position_desc TEXT,
    current_price REAL, last_evaluated_at TIMESTAMP
);

-- Breakout events (windowed, d_breakout). PK(symbol, date).
CREATE TABLE IF NOT EXISTS breakout_signals (
    symbol TEXT NOT NULL, date TEXT NOT NULL,
    breakout_status TEXT, breakout_direction TEXT, breakout_day INTEGER,
    breakout_strength REAL, breakout_volume_ratio REAL,
    consolidation_bottom REAL, consolidation_top REAL, consolidation_range_pct REAL,
    consolidation_duration_days INTEGER, rejection_reason TEXT, detail_json TEXT,
    last_evaluated_at TIMESTAMP,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_breakout_signals_date ON breakout_signals(date);

-- Support/resistance zones (latest-only). PK(symbol, zone_type, level).
CREATE TABLE IF NOT EXISTS support_resistance (
    symbol TEXT NOT NULL, zone_type TEXT NOT NULL, level REAL NOT NULL,
    zone_bottom REAL, zone_top REAL, center_price REAL, touches INTEGER, strength REAL,
    date TEXT, last_evaluated_at TIMESTAMP,
    PRIMARY KEY (symbol, zone_type, level)
);

-- Composite score/verdict (windowed). PK(symbol, date). PROVISIONAL until Phase 2.
CREATE TABLE IF NOT EXISTS screen_scores (
    symbol TEXT NOT NULL, date TEXT NOT NULL,
    score_tech REAL, score_fund REAL, score_total REAL, verdict TEXT,
    tech_flags TEXT, fund_flags TEXT, multi_factor_momentum REAL,
    passed INTEGER, fail_reasons TEXT, is_provisional INTEGER DEFAULT 1,
    last_evaluated_at TIMESTAMP,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_screen_scores_date ON screen_scores(date);

-- Screener config (key/value JSON). All editable from the UI later.
CREATE TABLE IF NOT EXISTS screener_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    category TEXT
);
INSERT OR IGNORE INTO screener_settings (key, value_json, category) VALUES
 ('quality_gates', '{"gross_margin":0.60,"roe":0.15,"roic":0.10,"levered_fcf_margin":0.20,"interest_cover":3.0,"eps_5y_growth":0.10,"free_cashflow":0}', 'fundamentals'),
 ('consolidation_params', '{"zigzag_deviation":6.0,"lookback_days":40,"min_days_between_swings":2,"breakout_confirmation_pct":1.5,"volume_lookback_days":20,"min_resistance_touches":2,"min_support_touches":2,"extreme_grouping_tolerance":2.5,"timeframes":[15,30,60],"max_consolidation_range_pct":5.0,"min_consolidation_duration":20,"max_daily_change":30.0,"min_volume_threshold":5000,"max_volatility_filter":150.0,"channel_test_tolerance":0.02,"min_touches_per_level":2,"min_range_size_pct":2.0,"min_bounces_in_channel":3}', 'signals'),
 ('scoring_weights', '{"above_ma50":10,"above_ma200":10,"ma50_rising_8d":10,"ma50_above_ma200":8,"macd_bullish":8,"rsi_neutral":5,"volume_spike":7,"breakout":12,"consolidation_quality":10,"momentum_20d_positive":8,"momentum_60d_positive":10,"near_52w_high":5}', 'scoring'),
 ('thresholds', '{"min_score_total":55,"min_score_tech":50,"min_quality_gates":4,"min_rr_ratio":1.5,"max_rsi":80,"min_market_cap":500000000}', 'scoring'),
 ('retention', '{"breakout_fresh_days":3,"breakout_retention_days":30,"screen_scores_retention_days":60}', 'retention'),
 ('account', '{"account_size":13596,"currency":"EUR","risk_pct_per_trade":1.0,"default_stop_method":"atr_2x"}', 'account');

-- Flattened one-row-per-symbol overview for the Screener grid / export.
-- Unified per-symbol research dataset (Epic R). Single source of truth for the
-- Research grid, CSV export, and the detail popup. Joins latest indicators
-- (Epic D), screener signals, consolidation, breakout, fundamentals, and score.
CREATE VIEW IF NOT EXISTS research_overview AS
SELECT
    u.symbol, u.name, u.sector,
    -- latest close price + raw volume (Epic C market_data)
    (SELECT md.close FROM market_data md WHERE md.symbol = u.symbol ORDER BY md.time DESC LIMIT 1) AS price,
    (SELECT md.volume FROM market_data md WHERE md.symbol = u.symbol ORDER BY md.time DESC LIMIT 1) AS volume,
    -- latest raw volume relative to its 20-day average ("trading heavier than normal?")
    (SELECT md.volume FROM market_data md WHERE md.symbol = u.symbol ORDER BY md.time DESC LIMIT 1) * 1.0
        / NULLIF(i.volume_ma_20, 0) AS volume_ratio,
    -- latest indicators (Epic D)
    i.time AS indicator_date,
    i.ma_50, i.ma_100, i.ma_150, i.ma_200,
    i.bb_upper_20, i.bb_lower_20, i.bb_width,
    i.rsi_14, i.mrsi, i.atr_14, i.volume_ma_20,
    -- screener signals (Epic S)
    ss.date AS signal_date, ss.momentum_5d, ss.momentum_20d, ss.momentum_60d,
    ss.multi_factor_momentum, ss.above_ma50, ss.above_ma200, ss.ma_cross_status,
    ss.trend_aligned, ss.is_8d_consec, ss.volume_spike,
    ss.dist_from_52w_high, ss.near_52w_high,
    cp.quality_score AS consolidation_quality, cp.support_level, cp.resistance_level,
    cp.range_pct AS consolidation_range_pct, cp.timeframe AS consolidation_timeframe,
    b.breakout_status, b.breakout_direction, b.breakout_strength, b.breakout_volume_ratio, b.date AS breakout_date,
    -- bounds from the breakout detector's OWN consolidation pass (independent of
    -- consolidation_patterns above — two detectors, see workflow/ADR.md)
    b.consolidation_bottom AS breakout_support, b.consolidation_top AS breakout_resistance,
    b.consolidation_range_pct AS breakout_range_pct, b.consolidation_duration_days AS breakout_duration_days,
    f.gross_margin, f.roe, f.roic, f.levered_fcf_margin, f.interest_cover, f.eps_5y_growth,
    f.gates_passed, f.gates_total, f.market_cap, f.trailing_pe,
    sc.score_tech, sc.score_fund, sc.score_total, sc.verdict
FROM tracked_universe u
LEFT JOIN indicators i ON i.symbol = u.symbol
    AND i.time = (SELECT MAX(time) FROM indicators i2 WHERE i2.symbol = u.symbol)
LEFT JOIN screen_signals ss ON ss.symbol = u.symbol
LEFT JOIN consolidation_patterns cp ON cp.symbol = u.symbol
LEFT JOIN breakout_signals b ON b.symbol = u.symbol
    AND b.date = (SELECT MAX(date) FROM breakout_signals b2 WHERE b2.symbol = u.symbol)
LEFT JOIN fundamentals f ON f.symbol = u.symbol
LEFT JOIN screen_scores sc ON sc.symbol = u.symbol
    AND sc.date = (SELECT MAX(date) FROM screen_scores s2 WHERE s2.symbol = u.symbol)
WHERE u.enabled = 1;

-- Backward-compat alias: existing /api/screener/overview reads this.
CREATE VIEW IF NOT EXISTS screener_overview AS SELECT * FROM research_overview;

-- Latest IBKR cash balances per currency (Flex CashReport snapshot).
-- Replaced wholesale on each IBKR sync; an empty CashReport keeps the
-- last snapshot rather than wiping it.
CREATE TABLE IF NOT EXISTS cash_balances (
    currency TEXT PRIMARY KEY,
    amount REAL NOT NULL,
    report_date TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily portfolio valuation (Epic V dashboard). Rebuilt by
-- portfolio_history_compute.compute_history; safe to delete and recompute.
CREATE TABLE IF NOT EXISTS portfolio_value_history (
    date TEXT PRIMARY KEY,
    value_eur REAL NOT NULL,
    value_usd_leg REAL,
    value_eur_leg REAL,
    fx_rate REAL,
    computed_at TEXT
);
