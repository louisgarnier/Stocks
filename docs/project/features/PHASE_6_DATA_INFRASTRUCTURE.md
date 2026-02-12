# Phase 6: Data Infrastructure

**Establish price history and fundamental data fetching infrastructure to support position analysis, charting, and screening.**

---

## Requirements

### Functional Requirements
- [ ] Fetch and store historical price data (OHLCV) for all held positions
- [ ] Fetch and store fundamental metrics (margins, ratios, growth rates)
- [ ] Calculate and store technical indicators (SMA, EMA, RSI, Mansfield RSI)
- [ ] Implement data refresh mechanism (daily updates)
- [ ] Handle data validation and error recovery

### Non-Functional Requirements
- [ ] Performance: Fetch data for all positions in < 30 seconds
- [ ] Reliability: Retry logic for failed API calls
- [ ] Data Quality: Validate all fetched data before storage
- [ ] Scalability: Support 50+ positions without performance degradation

---

## Database Schema Changes

### New Tables

#### 1. `market_data` - Historical Price Data
```sql
CREATE TABLE IF NOT EXISTS market_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER NOT NULL,
    adjusted_close REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, date)
);

CREATE INDEX idx_market_data_symbol_date ON market_data(symbol, date);
CREATE INDEX idx_market_data_date ON market_data(date);
```

#### 2. `technical_indicators` - Calculated Technical Metrics
```sql
CREATE TABLE IF NOT EXISTS technical_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    sma_50 REAL,
    sma_150 REAL,
    sma_200 REAL,
    ema_50 REAL,
    ema_150 REAL,
    ema_200 REAL,
    rsi_14 REAL,
    mansfield_rsi REAL,
    volume_sma_20 REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, date)
);

CREATE INDEX idx_technical_symbol_date ON technical_indicators(symbol, date);
```

#### 3. `fundamental_metrics` - Fundamental Data
```sql
CREATE TABLE IF NOT EXISTS fundamental_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    gross_margin REAL,
    roic REAL,
    roe REAL,
    leveraged_fcf REAL,
    interest_coverage REAL,
    eps_growth_5y REAL,
    pe_ratio REAL,
    market_cap REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, date)
);

CREATE INDEX idx_fundamental_symbol_date ON fundamental_metrics(symbol, date);
```

#### 4. `data_fetch_log` - Track Data Updates
```sql
CREATE TABLE IF NOT EXISTS data_fetch_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    data_type TEXT NOT NULL, -- 'price', 'fundamental', 'technical'
    fetch_date TEXT NOT NULL,
    status TEXT NOT NULL, -- 'success', 'failed', 'partial'
    records_fetched INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fetch_log_symbol ON data_fetch_log(symbol, data_type);
```

---

## Configuration

### `backend/config/data_sources_config.py`
```python
class DataSourcesConfig:
    # Price Data Configuration
    PRICE_DATA_SOURCE = "yfinance"  # or "alpha_vantage", "polygon"
    PRICE_LOOKBACK_DAYS = 730  # 2 years of history
    PRICE_UPDATE_FREQUENCY = "daily"  # daily, hourly
    
    # Fundamental Data Configuration
    FUNDAMENTAL_DATA_SOURCE = "yfinance"  # or "financial_modeling_prep"
    FUNDAMENTAL_UPDATE_FREQUENCY = "weekly"
    
    # Technical Indicators Configuration
    TECHNICAL_INDICATORS = {
        'sma_periods': [50, 150, 200],
        'ema_periods': [50, 150, 200],
        'rsi_period': 14,
        'volume_sma_period': 20
    }
    
    # API Rate Limiting
    MAX_REQUESTS_PER_MINUTE = 60
    RETRY_ATTEMPTS = 3
    RETRY_DELAY_SECONDS = 5
    
    # Data Validation
    MAX_PRICE_CHANGE_PERCENT = 50  # Flag if daily change > 50%
    MIN_VOLUME_THRESHOLD = 1000
```

---

## Implementation Plan

### Step 6.1: Database Schema Setup
**Description**: Create all required database tables and indexes

**Tasks**:
- [ ] Create migration script `backend/database/migrations/006_data_infrastructure.py`
- [ ] Implement `market_data` table creation
- [ ] Implement `technical_indicators` table creation
- [ ] Implement `fundamental_metrics` table creation
- [ ] Implement `data_fetch_log` table creation
- [ ] Add indexes for performance optimization
- [ ] Create rollback mechanism

**Dependencies**: Phase 5 complete

**Deliverables**:
- Migration script
- Updated database schema

**Acceptance Criteria**:
- [ ] Migration runs successfully: `python backend/database/migrations/006_data_infrastructure.py`
- [ ] All tables created with correct schema
- [ ] Indexes created and verified
- [ ] No data loss from existing tables

**Tests**:
- [ ] Unit test: Verify table creation
- [ ] Unit test: Verify indexes exist
- [ ] Integration test: Insert and query sample data

**Estimated Time**: 2 hours

---

### Step 6.2: Price Data Fetcher (Port from tradingoff)
**Description**: Implement historical price data fetching (adapt `b_grab_histo_data_up.py`)

**Tasks**:
- [ ] Create `backend/scripts/fetch_price_data.py`
- [ ] Implement yfinance integration
- [ ] Add data validation logic (price change limits, volume thresholds)
- [ ] Implement incremental updates (fetch only missing dates)
- [ ] Add error handling and retry logic
- [ ] Log all fetch operations to `data_fetch_log`
- [ ] Create CSV backup of fetched data

**Dependencies**: Step 6.1

**Deliverables**:
- `backend/scripts/fetch_price_data.py`
- Price data populated in `market_data` table

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/fetch_price_data.py`
- [ ] Fetches data for all held positions
- [ ] Handles missing data gracefully
- [ ] Validates data before storage
- [ ] Logs success/failure for each symbol

**Tests**:
- [ ] Unit test: `test_fetch_single_symbol_price_data()`
- [ ] Unit test: `test_validate_price_data()`
- [ ] Unit test: `test_handle_api_failure()`
- [ ] Integration test: `test_fetch_all_positions_price_data()`
- [ ] Integration test: `test_incremental_update()`

**Test File**: `backend/tests/test_fetch_price_data.py`

**Estimated Time**: 4 hours

---

### Step 6.3: Technical Indicators Calculator (Port from tradingoff)
**Description**: Calculate technical indicators from price data (adapt `c_mma.py`)

**Tasks**:
- [ ] Create `backend/scripts/calculate_technical_indicators.py`
- [ ] Implement SMA calculation (50, 150, 200 periods)
- [ ] Implement EMA calculation (50, 150, 200 periods)
- [ ] Implement RSI calculation (14 period)
- [ ] Implement Mansfield RSI (relative to SPY)
- [ ] Implement volume SMA (20 period)
- [ ] Store results in `technical_indicators` table
- [ ] Add data validation

**Dependencies**: Step 6.2

**Deliverables**:
- `backend/scripts/calculate_technical_indicators.py`
- Technical indicators populated in database

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/calculate_technical_indicators.py`
- [ ] All indicators calculated correctly
- [ ] Mansfield RSI uses SPY as benchmark
- [ ] Handles insufficient data gracefully (need min 200 days for SMA200)

**Tests**:
- [ ] Unit test: `test_calculate_sma()`
- [ ] Unit test: `test_calculate_ema()`
- [ ] Unit test: `test_calculate_rsi()`
- [ ] Unit test: `test_calculate_mansfield_rsi()`
- [ ] Integration test: `test_calculate_all_indicators_for_symbol()`

**Test File**: `backend/tests/test_technical_indicators.py`

**Estimated Time**: 4 hours

---

### Step 6.4: Fundamental Data Fetcher
**Description**: Fetch fundamental metrics from external API

**Tasks**:
- [ ] Create `backend/scripts/fetch_fundamental_data.py`
- [ ] Research and select free API (yfinance, FMP, etc.)
- [ ] Implement API integration
- [ ] Fetch metrics: gross_margin, roic, roe, leveraged_fcf, interest_coverage, eps_growth_5y, pe_ratio
- [ ] Add data validation (ensure values are within reasonable ranges)
- [ ] Store in `fundamental_metrics` table
- [ ] Handle API rate limits

**Dependencies**: Step 6.1

**Deliverables**:
- `backend/scripts/fetch_fundamental_data.py`
- Fundamental metrics populated in database

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/fetch_fundamental_data.py`
- [ ] All required metrics fetched
- [ ] Handles missing data (some stocks may not have all metrics)
- [ ] Respects API rate limits

**Tests**:
- [ ] Unit test: `test_fetch_fundamental_metrics_single_symbol()`
- [ ] Unit test: `test_validate_fundamental_data()`
- [ ] Unit test: `test_handle_missing_metrics()`
- [ ] Integration test: `test_fetch_all_positions_fundamentals()`

**Test File**: `backend/tests/test_fetch_fundamental_data.py`

**Estimated Time**: 5 hours

---

### Step 6.5: Data Refresh Orchestrator
**Description**: Coordinate all data fetching and calculation scripts

**Tasks**:
- [ ] Create `backend/scripts/refresh_all_data.py`
- [ ] Orchestrate execution order: price → technical → fundamental
- [ ] Implement parallel fetching where possible (multiple symbols)
- [ ] Add progress reporting
- [ ] Generate summary report (symbols updated, errors, duration)
- [ ] Add command-line options (--symbols, --force-refresh, --data-type)

**Dependencies**: Steps 6.2, 6.3, 6.4

**Deliverables**:
- `backend/scripts/refresh_all_data.py`
- Automated data refresh pipeline

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/refresh_all_data.py`
- [ ] Updates all data types for all positions
- [ ] Completes in < 30 seconds for 10 positions
- [ ] Generates summary report
- [ ] Can refresh specific symbols: `python backend/scripts/refresh_all_data.py --symbols AAPL,TSLA`

**Tests**:
- [ ] Integration test: `test_refresh_all_data_pipeline()`
- [ ] Integration test: `test_refresh_specific_symbols()`
- [ ] Integration test: `test_handle_partial_failures()`

**Test File**: `backend/tests/test_refresh_all_data.py`

**Estimated Time**: 3 hours

---

### Step 6.6: API Endpoints for Data Access
**Description**: Create API endpoints to access fetched data

**Tasks**:
- [ ] Create `backend/api/routes/market_data.py`
- [ ] Add `GET /api/market-data/{symbol}` - Get price history
- [ ] Add `GET /api/technical-indicators/{symbol}` - Get technical indicators
- [ ] Add `GET /api/fundamental-metrics/{symbol}` - Get fundamental metrics
- [ ] Add `POST /api/data/refresh` - Trigger data refresh
- [ ] Add `GET /api/data/status` - Get last refresh status
- [ ] Add query parameters for date ranges

**Dependencies**: Step 6.5

**Deliverables**:
- API endpoints for data access
- API documentation

**Acceptance Criteria**:
- [ ] GET `/api/market-data/AAPL?start_date=2024-01-01&end_date=2024-12-31` returns price data
- [ ] GET `/api/technical-indicators/AAPL` returns latest indicators
- [ ] GET `/api/fundamental-metrics/AAPL` returns latest fundamentals
- [ ] POST `/api/data/refresh` triggers refresh and returns job status
- [ ] All endpoints return proper error messages

**Tests**:
- [ ] API test: `test_get_market_data_endpoint()`
- [ ] API test: `test_get_technical_indicators_endpoint()`
- [ ] API test: `test_get_fundamental_metrics_endpoint()`
- [ ] API test: `test_refresh_data_endpoint()`
- [ ] API test: `test_data_status_endpoint()`

**Test File**: `backend/tests/test_market_data_api.py`

**Estimated Time**: 3 hours

---

### Step 6.7: Frontend Data Service
**Description**: Create frontend service to fetch market data

**Tasks**:
- [ ] Create `frontend/src/api/marketDataService.ts`
- [ ] Implement `getMarketData(symbol, startDate, endDate)`
- [ ] Implement `getTechnicalIndicators(symbol)`
- [ ] Implement `getFundamentalMetrics(symbol)`
- [ ] Implement `refreshData(symbols?)`
- [ ] Implement `getDataStatus()`
- [ ] Add error handling and loading states

**Dependencies**: Step 6.6

**Deliverables**:
- Frontend market data service
- TypeScript types for data models

**Acceptance Criteria**:
- [ ] Service methods call correct API endpoints
- [ ] Proper error handling
- [ ] Loading states managed
- [ ] TypeScript types defined

**Tests**:
- [ ] Frontend test: `test_market_data_service_fetch()`
- [ ] Frontend test: `test_handle_api_errors()`

**Test File**: `frontend/src/api/__tests__/marketDataService.test.ts`

**Estimated Time**: 2 hours

---

## Performance Optimization

### Caching Strategy
- Cache price data for current day (invalidate at market close)
- Cache technical indicators (recalculate only on new price data)
- Cache fundamental metrics (update weekly)

### Database Optimization
- Use indexes on (symbol, date) for fast queries
- Implement data retention policy (keep 2 years of daily data)
- Partition large tables if needed

### API Rate Limiting
- Implement exponential backoff for retries
- Batch requests where possible
- Use connection pooling

---

## Data Validation Rules

### Price Data
- Daily price change < 50% (flag for review if exceeded)
- Volume > 1,000 shares
- High >= Low
- Close between Low and High

### Technical Indicators
- RSI between 0 and 100
- Moving averages > 0
- Mansfield RSI between -100 and 100

### Fundamental Metrics
- Margins between -100% and 100%
- ROIC, ROE between -100% and 200%
- Interest coverage > -10x

---

## Error Handling

### API Failures
- Retry up to 3 times with exponential backoff
- Log failures to `data_fetch_log`
- Continue with other symbols if one fails
- Send alert if > 50% of symbols fail

### Data Quality Issues
- Flag invalid data but don't block storage
- Create data quality report
- Allow manual review and correction

---

## Acceptance Criteria

- [ ] All database tables created and indexed
- [ ] Price data fetched for all held positions (2 years history)
- [ ] Technical indicators calculated and stored
- [ ] Fundamental metrics fetched and stored
- [ ] Data refresh completes in < 30 seconds for 10 positions
- [ ] API endpoints return correct data
- [ ] Frontend service successfully fetches data
- [ ] All tests passing (unit, integration, API, frontend)
- [ ] Data validation rules enforced
- [ ] Error handling tested and working

---

## Related Requirements

- [PHASE_7_POSITION_DETAILS.md](./PHASE_7_POSITION_DETAILS.md) - Uses price and fundamental data
- [PHASE_8_PRICE_CHARTS.md](./PHASE_8_PRICE_CHARTS.md) - Uses price and technical indicator data

---

## Notes

- **Data Source Selection**: Start with yfinance (free, reliable). Can add alternative sources later.
- **Incremental Updates**: Only fetch missing dates to minimize API calls.
- **SPY Benchmark**: Fetch SPY data for Mansfield RSI calculation.
- **Data Retention**: Keep 2 years of daily data, archive older data.
- **Performance**: Optimize for read-heavy workload (charts, analysis).

---

## Quick Links

- [Previous Phase: Automation](./PHASE_5_AUTOMATION.md)
- [Next Phase: Position Details](./PHASE_7_POSITION_DETAILS.md)
