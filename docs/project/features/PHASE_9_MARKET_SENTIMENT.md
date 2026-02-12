# Phase 9: Market Sentiment Analytics

**Create macro-level market analytics dashboard to highlight broader market conditions that impact portfolio decisions.**

---

## Requirements

### Functional Requirements
- [ ] Fetch and display macro economic indicators
- [ ] Calculate and display market sentiment metrics
- [ ] Implement visual alert system (green/yellow/red zones)
- [ ] Track historical trends for key indicators
- [ ] Provide market overview dashboard
- [ ] Support manual threshold configuration

### Non-Functional Requirements
- [ ] Performance: Dashboard loads in < 3 seconds
- [ ] Data Freshness: Update macro data daily
- [ ] Reliability: Handle API failures gracefully
- [ ] Usability: Clear visual indicators for risk zones

---

## Database Schema Changes

### New Tables

#### 1. `market_sentiment_data` - Macro Indicators
```sql
CREATE TABLE IF NOT EXISTS market_sentiment_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    
    -- Valuation Metrics
    cape_ratio REAL,
    buffett_indicator REAL,  -- Market Cap / GDP
    sp500_m2_ratio REAL,
    
    -- Volatility & Fear
    vix_index REAL,
    
    -- Interest Rates & Currency
    us_10y_yield REAL,
    us_30y_yield REAL,
    usd_jpy_rate REAL,
    eur_usd_rate REAL,
    
    -- Sector Rotation
    consumer_discretionary_staples_ratio REAL,
    
    -- Margin Requirements (Futures)
    margin_equity_index REAL,
    margin_energy REAL,
    margin_metals REAL,
    margin_agriculture REAL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sentiment_date ON market_sentiment_data(date);
```

#### 2. `sentiment_thresholds` - Alert Thresholds Configuration
```sql
CREATE TABLE IF NOT EXISTS sentiment_thresholds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator_name TEXT NOT NULL UNIQUE,
    green_min REAL,
    green_max REAL,
    yellow_min REAL,
    yellow_max REAL,
    red_min REAL,
    red_max REAL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Example threshold data:**
```sql
INSERT INTO sentiment_thresholds (indicator_name, green_min, green_max, yellow_min, yellow_max, red_min, red_max, description) VALUES
('vix_index', 0, 15, 15, 25, 25, 100, 'VIX volatility index'),
('cape_ratio', 0, 20, 20, 30, 30, 50, 'Shiller PE ratio'),
('usd_jpy_rate', 0, 150, 150, 160, 160, 200, 'USD/JPY exchange rate');
```

#### 3. `sentiment_data_sources` - Track Data Source Status
```sql
CREATE TABLE IF NOT EXISTS sentiment_data_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator_name TEXT NOT NULL,
    data_source TEXT NOT NULL,  -- 'fred', 'yahoo', 'scraping', 'manual'
    source_url TEXT,
    last_fetch_date TEXT,
    last_fetch_status TEXT,  -- 'success', 'failed'
    error_message TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_data_sources_indicator ON sentiment_data_sources(indicator_name);
```

---

## Configuration

### `backend/config/sentiment_config.py`
```python
class SentimentConfig:
    # Data Sources Configuration
    DATA_SOURCES = {
        'cape_ratio': {
            'source': 'multpl',  # multpl.com/shiller-pe
            'url': 'https://www.multpl.com/shiller-pe/table/by-month',
            'method': 'scraping',
            'update_frequency': 'monthly'
        },
        'vix_index': {
            'source': 'yahoo',
            'symbol': '^VIX',
            'method': 'api',
            'update_frequency': 'daily'
        },
        'buffett_indicator': {
            'source': 'fred',  # Federal Reserve Economic Data
            'series_id': 'DDDM01USA156NWDB',  # Market Cap to GDP
            'method': 'api',
            'update_frequency': 'quarterly'
        },
        'us_10y_yield': {
            'source': 'yahoo',
            'symbol': '^TNX',
            'method': 'api',
            'update_frequency': 'daily'
        },
        'us_30y_yield': {
            'source': 'yahoo',
            'symbol': '^TYX',
            'method': 'api',
            'update_frequency': 'daily'
        },
        'usd_jpy_rate': {
            'source': 'yahoo',
            'symbol': 'JPY=X',
            'method': 'api',
            'update_frequency': 'daily'
        },
        'eur_usd_rate': {
            'source': 'yahoo',
            'symbol': 'EURUSD=X',
            'method': 'api',
            'update_frequency': 'daily'
        },
        'sp500_m2_ratio': {
            'source': 'calculated',  # SPY price / M2 money supply
            'components': ['SPY', 'M2SL'],  # M2SL from FRED
            'method': 'calculated',
            'update_frequency': 'weekly'
        },
        'consumer_discretionary_staples_ratio': {
            'source': 'calculated',  # XLY / XLP
            'components': ['XLY', 'XLP'],  # ETFs
            'method': 'calculated',
            'update_frequency': 'daily'
        },
        'margin_requirements': {
            'source': 'cme',  # CME Group or manual
            'url': 'https://www.cmegroup.com/clearing/risk-management/margin-requirements.html',
            'method': 'manual',  # To be confirmed
            'update_frequency': 'weekly'
        }
    }
    
    # Default Thresholds (Green/Yellow/Red zones)
    DEFAULT_THRESHOLDS = {
        'vix_index': {
            'green': (0, 15),
            'yellow': (15, 25),
            'red': (25, 100),
            'description': 'Low VIX = complacency, High VIX = fear'
        },
        'cape_ratio': {
            'green': (0, 20),
            'yellow': (20, 30),
            'red': (30, 50),
            'description': 'Historical average ~16-17'
        },
        'buffett_indicator': {
            'green': (0, 100),
            'yellow': (100, 140),
            'red': (140, 300),
            'description': 'Market Cap / GDP ratio'
        },
        'usd_jpy_rate': {
            'green': (0, 150),
            'yellow': (150, 160),
            'red': (160, 200),
            'description': 'Yen carry trade risk above 160'
        },
        'eur_usd_rate': {
            'green': (0, 1.15),
            'yellow': (1.15, 1.20),
            'red': (1.20, 2.0),
            'description': 'Strong EUR can signal risk-off'
        },
        'us_10y_yield': {
            'green': (0, 4.0),
            'yellow': (4.0, 5.0),
            'red': (5.0, 10.0),
            'description': 'Rising yields pressure equities'
        }
    }
    
    # Update Settings
    UPDATE_FREQUENCY = 'daily'
    RETRY_ATTEMPTS = 3
    CACHE_TTL_HOURS = 24
```

---

## Implementation Plan

### Step 9.1: Sentiment Data Fetchers - Yahoo Finance Indicators
**Description**: Fetch daily indicators from Yahoo Finance (VIX, yields, currencies)

**Tasks**:
- [ ] Create `backend/scripts/fetch_sentiment_yahoo.py`
- [ ] Implement VIX fetcher (^VIX)
- [ ] Implement US 10Y yield fetcher (^TNX)
- [ ] Implement US 30Y yield fetcher (^TYX)
- [ ] Implement USD/JPY fetcher (JPY=X)
- [ ] Implement EUR/USD fetcher (EURUSD=X)
- [ ] Store in `market_sentiment_data` table
- [ ] Log fetch status to `sentiment_data_sources`

**Dependencies**: Phase 6 (data infrastructure)

**Deliverables**:
- Yahoo Finance sentiment data fetcher

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/fetch_sentiment_yahoo.py`
- [ ] Fetches all Yahoo-based indicators
- [ ] Stores latest values in database
- [ ] Handles API failures gracefully
- [ ] Logs fetch status

**Tests**:
- [ ] Unit test: `test_fetch_vix_index()`
- [ ] Unit test: `test_fetch_treasury_yields()`
- [ ] Unit test: `test_fetch_currency_rates()`
- [ ] Integration test: `test_fetch_all_yahoo_indicators()`

**Test File**: `backend/tests/test_fetch_sentiment_yahoo.py`

**Estimated Time**: 3 hours

---

### Step 9.2: Sentiment Data Fetchers - FRED API Indicators
**Description**: Fetch indicators from Federal Reserve Economic Data (FRED)

**Tasks**:
- [ ] Create `backend/scripts/fetch_sentiment_fred.py`
- [ ] Set up FRED API key (free registration)
- [ ] Implement Buffett Indicator fetcher (Market Cap / GDP)
- [ ] Implement M2 money supply fetcher (for S&P/M2 ratio)
- [ ] Store in `market_sentiment_data` table
- [ ] Handle quarterly vs daily data frequencies

**Dependencies**: Phase 6

**Deliverables**:
- FRED API sentiment data fetcher

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/fetch_sentiment_fred.py`
- [ ] Fetches Buffett Indicator
- [ ] Fetches M2 money supply
- [ ] Handles API rate limits
- [ ] Stores data with correct dates

**Tests**:
- [ ] Unit test: `test_fetch_buffett_indicator()`
- [ ] Unit test: `test_fetch_m2_money_supply()`
- [ ] Integration test: `test_fred_api_integration()`

**Test File**: `backend/tests/test_fetch_sentiment_fred.py`

**Estimated Time**: 3 hours

---

### Step 9.3: Sentiment Data Fetchers - Web Scraping (CAPE Ratio)
**Description**: Scrape CAPE ratio from multpl.com

**Tasks**:
- [ ] Create `backend/scripts/fetch_sentiment_scraping.py`
- [ ] Implement CAPE ratio scraper (multpl.com)
- [ ] Add HTML parsing with BeautifulSoup
- [ ] Add error handling for page structure changes
- [ ] Store in `market_sentiment_data` table
- [ ] Add user-agent headers to avoid blocking

**Dependencies**: Phase 6

**Deliverables**:
- Web scraping sentiment data fetcher

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/fetch_sentiment_scraping.py`
- [ ] Scrapes current CAPE ratio
- [ ] Handles website changes gracefully
- [ ] Respects robots.txt
- [ ] Stores data correctly

**Tests**:
- [ ] Unit test: `test_parse_cape_ratio_html()`
- [ ] Unit test: `test_handle_scraping_errors()`
- [ ] Integration test: `test_scrape_cape_ratio()`

**Test File**: `backend/tests/test_fetch_sentiment_scraping.py`

**Estimated Time**: 3 hours

---

### Step 9.4: Calculated Indicators
**Description**: Calculate derived indicators (S&P/M2, Consumer Discretionary/Staples)

**Tasks**:
- [ ] Create `backend/scripts/calculate_sentiment_indicators.py`
- [ ] Implement S&P 500 / M2 ratio calculation
- [ ] Implement Consumer Discretionary / Staples ratio (XLY / XLP)
- [ ] Fetch component data (SPY, XLY, XLP prices)
- [ ] Store calculated values in `market_sentiment_data`

**Dependencies**: Steps 9.1, 9.2

**Deliverables**:
- Calculated sentiment indicators

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/calculate_sentiment_indicators.py`
- [ ] Calculates S&P/M2 ratio correctly
- [ ] Calculates XLY/XLP ratio correctly
- [ ] Handles missing component data

**Tests**:
- [ ] Unit test: `test_calculate_sp500_m2_ratio()`
- [ ] Unit test: `test_calculate_discretionary_staples_ratio()`
- [ ] Integration test: `test_calculate_all_indicators()`

**Test File**: `backend/tests/test_calculate_sentiment_indicators.py`

**Estimated Time**: 2.5 hours

---

### Step 9.5: Sentiment Data Orchestrator
**Description**: Coordinate all sentiment data fetching

**Tasks**:
- [ ] Create `backend/scripts/refresh_sentiment_data.py`
- [ ] Orchestrate execution: Yahoo → FRED → Scraping → Calculated
- [ ] Implement error recovery (continue if one source fails)
- [ ] Generate summary report
- [ ] Add command-line options (--source, --force-refresh)

**Dependencies**: Steps 9.1, 9.2, 9.3, 9.4

**Deliverables**:
- Sentiment data refresh orchestrator

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/refresh_sentiment_data.py`
- [ ] Fetches all sentiment indicators
- [ ] Completes in < 30 seconds
- [ ] Generates summary report
- [ ] Can refresh specific sources: `--source yahoo`

**Tests**:
- [ ] Integration test: `test_refresh_all_sentiment_data()`
- [ ] Integration test: `test_partial_failure_handling()`

**Test File**: `backend/tests/test_refresh_sentiment_data.py`

**Estimated Time**: 2 hours

---

### Step 9.6: Threshold Evaluator
**Description**: Evaluate current indicators against thresholds (green/yellow/red)

**Tasks**:
- [ ] Create `backend/utils/sentiment_evaluator.py`
- [ ] Implement threshold checking logic
- [ ] Return zone (green/yellow/red) for each indicator
- [ ] Calculate overall market sentiment score
- [ ] Support custom threshold overrides

**Dependencies**: Step 9.5

**Deliverables**:
- Sentiment threshold evaluator

**Acceptance Criteria**:
- [ ] Evaluates each indicator against thresholds
- [ ] Returns correct zone (green/yellow/red)
- [ ] Calculates overall sentiment score (0-100)
- [ ] Handles missing data gracefully

**Tests**:
- [ ] Unit test: `test_evaluate_single_indicator()`
- [ ] Unit test: `test_calculate_overall_sentiment()`
- [ ] Unit test: `test_custom_thresholds()`

**Test File**: `backend/tests/test_sentiment_evaluator.py`

**Estimated Time**: 2 hours

---

### Step 9.7: Sentiment API Endpoints
**Description**: Create API endpoints for market sentiment data

**Tasks**:
- [ ] Create `backend/api/routes/sentiment.py`
- [ ] Add `GET /api/sentiment/current` - Latest sentiment data with zones
- [ ] Add `GET /api/sentiment/history` - Historical sentiment data
- [ ] Add `GET /api/sentiment/thresholds` - Get threshold configuration
- [ ] Add `PUT /api/sentiment/thresholds` - Update thresholds
- [ ] Add `POST /api/sentiment/refresh` - Trigger data refresh

**Dependencies**: Steps 9.5, 9.6

**Deliverables**:
- Sentiment API endpoints

**Acceptance Criteria**:
- [ ] GET `/api/sentiment/current` returns latest data with zones
- [ ] GET `/api/sentiment/history?days=30` returns 30 days of data
- [ ] GET `/api/sentiment/thresholds` returns all thresholds
- [ ] PUT `/api/sentiment/thresholds` updates thresholds
- [ ] POST `/api/sentiment/refresh` triggers refresh

**Tests**:
- [ ] API test: `test_get_current_sentiment()`
- [ ] API test: `test_get_sentiment_history()`
- [ ] API test: `test_get_thresholds()`
- [ ] API test: `test_update_thresholds()`
- [ ] API test: `test_refresh_sentiment_data()`

**Test File**: `backend/tests/test_sentiment_api.py`

**Estimated Time**: 3 hours

---

### Step 9.8: Market Sentiment Dashboard Page
**Description**: Create market sentiment dashboard frontend

**Tasks**:
- [ ] Create `frontend/src/pages/MarketSentiment.vue`
- [ ] Add route `/market-sentiment`
- [ ] Create dashboard layout with indicator cards
- [ ] Display current values with zone indicators (green/yellow/red)
- [ ] Add navigation link from main menu
- [ ] Show last updated timestamp

**Dependencies**: Step 9.7

**Deliverables**:
- Market sentiment dashboard page

**Acceptance Criteria**:
- [ ] Page loads at `/market-sentiment`
- [ ] Displays all sentiment indicators
- [ ] Color coding works (green/yellow/red)
- [ ] Shows current values
- [ ] Shows last updated time

**Tests**:
- [ ] Frontend test: `test_sentiment_dashboard_renders()`
- [ ] Frontend test: `test_indicator_color_coding()`

**Test File**: `frontend/src/pages/__tests__/MarketSentiment.test.ts`

**Estimated Time**: 3 hours

---

### Step 9.9: Sentiment Indicator Cards
**Description**: Create reusable indicator card components

**Tasks**:
- [ ] Create `frontend/src/components/SentimentIndicatorCard.vue`
- [ ] Display indicator name, value, zone
- [ ] Add color-coded background or border
- [ ] Show threshold ranges
- [ ] Add tooltip with description
- [ ] Display trend arrow (up/down from previous)

**Dependencies**: Step 9.8

**Deliverables**:
- Sentiment indicator card component

**Acceptance Criteria**:
- [ ] Card displays indicator name and value
- [ ] Background/border color matches zone
- [ ] Tooltip shows description and thresholds
- [ ] Trend arrow shows direction of change
- [ ] Responsive design

**Tests**:
- [ ] Frontend test: `test_indicator_card_renders()`
- [ ] Frontend test: `test_zone_color_coding()`
- [ ] Frontend test: `test_trend_arrow_display()`

**Test File**: `frontend/src/components/__tests__/SentimentIndicatorCard.test.ts`

**Estimated Time**: 2.5 hours

---

### Step 9.10: Sentiment Historical Chart
**Description**: Display historical trends for sentiment indicators

**Tasks**:
- [ ] Create `frontend/src/components/SentimentHistoryChart.vue`
- [ ] Use Plotly for line charts
- [ ] Display 30/90/180 day trends
- [ ] Add threshold lines (green/yellow/red zones)
- [ ] Support multi-indicator overlay
- [ ] Add timeframe selector

**Dependencies**: Step 9.8

**Deliverables**:
- Sentiment history chart component

**Acceptance Criteria**:
- [ ] Displays historical data as line chart
- [ ] Shows threshold zones as background colors
- [ ] Can select timeframe (30/90/180 days)
- [ ] Can overlay multiple indicators
- [ ] Interactive hover shows values

**Tests**:
- [ ] Frontend test: `test_history_chart_renders()`
- [ ] Frontend test: `test_timeframe_selection()`
- [ ] Frontend test: `test_threshold_zones_display()`

**Test File**: `frontend/src/components/__tests__/SentimentHistoryChart.test.ts`

**Estimated Time**: 3 hours

---

### Step 9.11: Overall Market Risk Score
**Description**: Calculate and display aggregate market risk score

**Tasks**:
- [ ] Create `frontend/src/components/MarketRiskScore.vue`
- [ ] Display overall risk score (0-100)
- [ ] Show risk level (Low/Medium/High)
- [ ] Add visual gauge or progress bar
- [ ] List top risk factors (indicators in red zone)
- [ ] Add interpretation text

**Dependencies**: Step 9.8

**Deliverables**:
- Market risk score component

**Acceptance Criteria**:
- [ ] Displays overall risk score
- [ ] Shows risk level clearly
- [ ] Visual gauge works
- [ ] Lists top risk factors
- [ ] Provides actionable interpretation

**Tests**:
- [ ] Frontend test: `test_risk_score_display()`
- [ ] Frontend test: `test_risk_level_calculation()`
- [ ] Frontend test: `test_top_risk_factors()`

**Test File**: `frontend/src/components/__tests__/MarketRiskScore.test.ts`

**Estimated Time**: 2.5 hours

---

### Step 9.12: Threshold Configuration UI
**Description**: Allow users to customize thresholds

**Tasks**:
- [ ] Create `frontend/src/components/ThresholdConfigModal.vue`
- [ ] Display current thresholds in editable form
- [ ] Add input validation (green < yellow < red)
- [ ] Add "Reset to Defaults" button
- [ ] Save changes via API
- [ ] Show confirmation on save

**Dependencies**: Step 9.7

**Deliverables**:
- Threshold configuration UI

**Acceptance Criteria**:
- [ ] Modal displays all thresholds
- [ ] Can edit threshold values
- [ ] Validates input (logical ranges)
- [ ] Saves changes successfully
- [ ] Can reset to defaults

**Tests**:
- [ ] Frontend test: `test_threshold_config_modal_renders()`
- [ ] Frontend test: `test_threshold_validation()`
- [ ] Frontend test: `test_save_thresholds()`
- [ ] Frontend test: `test_reset_to_defaults()`

**Test File**: `frontend/src/components/__tests__/ThresholdConfigModal.test.ts`

**Estimated Time**: 3 hours

---

## Performance Optimization

### Data Fetching
- Cache sentiment data for 24 hours
- Batch API calls where possible
- Use async/await for parallel fetching
- Implement exponential backoff for retries

### Database Optimization
- Index on date column for fast historical queries
- Store only daily snapshots (not intraday)
- Archive data older than 2 years

### Frontend Optimization
- Cache dashboard data (refresh every 5 minutes)
- Lazy load historical charts
- Debounce threshold updates

---

## Data Validation Rules

### Sentiment Data
- VIX: 0-100 range
- CAPE ratio: 0-50 range (flag if > 50)
- Yields: 0-15% range
- Currency rates: > 0
- Ratios: > 0

### Thresholds
- Green max <= Yellow min
- Yellow max <= Red min
- All values > 0

---

## UI/UX Considerations

### Visual Design
- Use traffic light colors (green/yellow/red)
- Large, clear indicator cards
- Prominent overall risk score
- Clean, uncluttered layout

### Information Hierarchy
- Overall risk score at top
- Critical indicators (red zone) highlighted
- Historical trends below current values

### Accessibility
- Color-blind friendly (use icons + colors)
- Screen reader labels
- Keyboard navigation

---

## Future Enhancements (Document but Don't Implement)

### Additional Indicators
- Put/Call ratio
- Advance/Decline line
- High Yield spreads
- Sector rotation metrics

### Advanced Features
- Email alerts when indicators enter red zone
- Correlation analysis between indicators
- Predictive modeling (ML-based)

### Data Sources
- Bloomberg API (if available)
- Real-time data feeds
- Alternative data sources

---

## Acceptance Criteria

- [ ] Market sentiment dashboard accessible at `/market-sentiment`
- [ ] All macro indicators display correctly
- [ ] Color coding (green/yellow/red) works
- [ ] Overall market risk score calculated
- [ ] Historical charts display trends
- [ ] Thresholds configurable via UI
- [ ] Data refreshes daily
- [ ] Dashboard loads in < 3 seconds
- [ ] All tests passing (unit, integration, API, frontend)
- [ ] Handles missing data gracefully

---

## Related Requirements

- [PHASE_6_DATA_INFRASTRUCTURE.md](./PHASE_6_DATA_INFRASTRUCTURE.md) - Data fetching infrastructure
- [PHASE_10_POSITION_SCREENING.md](./PHASE_10_POSITION_SCREENING.md) - Uses sentiment data for screening

---

## Notes

- **Data Sources**: Mix of free APIs, web scraping, and calculated metrics
- **FRED API**: Free but requires registration for API key
- **Margin Requirements**: May need manual updates initially (CME data)
- **Update Frequency**: Daily is sufficient for macro indicators
- **Thresholds**: Initial values are suggestions - user can customize
- **Performance**: Optimize for quick dashboard load, not real-time updates

---

## Quick Links

- [Previous Phase: Price Charts](./PHASE_8_PRICE_CHARTS.md)
- [Next Phase: Position Screening](./PHASE_10_POSITION_SCREENING.md)
