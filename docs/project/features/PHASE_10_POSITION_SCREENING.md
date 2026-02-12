# Phase 10: Position Screening & Investment Criteria

**Implement screening engine to identify securities for short-term and long-term investing based on fundamental and technical criteria, inspired by tradingoff breakout detector.**

---

## Requirements

### Functional Requirements
- [ ] Screen held positions against fundamental criteria
- [ ] Screen held positions against technical criteria (port breakout detector logic)
- [ ] Support watchlist screening (future positions)
- [ ] Rank positions by compliance score
- [ ] Filter by short-term vs long-term investment criteria
- [ ] Display screening results with actionable insights
- [ ] Support custom screening criteria configuration

### Non-Functional Requirements
- [ ] Performance: Screen 50+ positions in < 5 seconds
- [ ] Accuracy: Criteria evaluation must be precise
- [ ] Flexibility: Easy to add/modify screening criteria
- [ ] Usability: Clear visualization of pass/fail criteria

---

## Database Schema Changes

### New Tables

#### 1. `screening_criteria` - Configurable Screening Rules
```sql
CREATE TABLE IF NOT EXISTS screening_criteria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    criteria_name TEXT NOT NULL UNIQUE,
    criteria_type TEXT NOT NULL,  -- 'fundamental', 'technical'
    investment_horizon TEXT NOT NULL,  -- 'short_term', 'long_term', 'both'
    metric_name TEXT NOT NULL,
    operator TEXT NOT NULL,  -- '>', '<', '>=', '<=', '==', 'between'
    threshold_value REAL,
    threshold_min REAL,
    threshold_max REAL,
    weight REAL DEFAULT 1.0,  -- For scoring
    is_active BOOLEAN DEFAULT 1,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_screening_criteria_type ON screening_criteria(criteria_type);
CREATE INDEX idx_screening_criteria_horizon ON screening_criteria(investment_horizon);
```

**Example criteria:**
```sql
INSERT INTO screening_criteria (criteria_name, criteria_type, investment_horizon, metric_name, operator, threshold_value, weight, description) VALUES
('High Gross Margin', 'fundamental', 'both', 'gross_margin', '>', 60.0, 1.5, 'Gross margin > 60%'),
('Strong ROIC', 'fundamental', 'long_term', 'roic', '>', 12.0, 1.0, 'Return on invested capital > 12%'),
('Breakout Signal', 'technical', 'short_term', 'breakout_detected', '==', 1.0, 2.0, 'Breakout pattern detected');
```

#### 2. `screening_results` - Cached Screening Results
```sql
CREATE TABLE IF NOT EXISTS screening_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    screening_date TEXT NOT NULL,
    investment_horizon TEXT NOT NULL,
    
    -- Fundamental Scores
    fundamental_score REAL,
    fundamental_criteria_met INTEGER,
    fundamental_criteria_total INTEGER,
    
    -- Technical Scores
    technical_score REAL,
    technical_criteria_met INTEGER,
    technical_criteria_total INTEGER,
    
    -- Overall
    overall_score REAL,
    overall_rank INTEGER,
    recommendation TEXT,  -- 'strong_buy', 'buy', 'hold', 'sell'
    
    -- Detailed Results (JSON)
    criteria_details_json TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, screening_date, investment_horizon)
);

CREATE INDEX idx_screening_results_symbol ON screening_results(symbol);
CREATE INDEX idx_screening_results_date ON screening_results(screening_date);
CREATE INDEX idx_screening_results_score ON screening_results(overall_score);
```

#### 3. `breakout_signals` - Technical Breakout Detection (Port from tradingoff)
```sql
CREATE TABLE IF NOT EXISTS breakout_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    signal_date TEXT NOT NULL,
    
    -- Breakout Details
    breakout_type TEXT,  -- 'consolidation', 'resistance', 'pattern'
    pattern_name TEXT,  -- 'cup_and_handle', 'double_bottom', etc.
    confidence_score REAL,
    
    -- Price Levels
    breakout_price REAL,
    resistance_level REAL,
    support_level REAL,
    
    -- Volume Analysis
    volume_ratio REAL,
    volume_surge BOOLEAN,
    
    -- Moving Averages
    above_sma_50 BOOLEAN,
    above_sma_150 BOOLEAN,
    above_sma_200 BOOLEAN,
    
    -- Mansfield RSI
    mansfield_rsi REAL,
    relative_strength TEXT,  -- 'strong', 'moderate', 'weak'
    
    -- Consolidation Metrics (from g_consolidation.py)
    consolidation_days INTEGER,
    consolidation_range_pct REAL,
    consolidation_quality_score REAL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, signal_date)
);

CREATE INDEX idx_breakout_signals_symbol ON breakout_signals(symbol);
CREATE INDEX idx_breakout_signals_date ON breakout_signals(signal_date);
```

#### 4. `watchlist` - Securities to Monitor
```sql
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,
    added_date TEXT NOT NULL,
    added_reason TEXT,
    target_entry_price REAL,
    notes TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_watchlist_symbol ON watchlist(symbol);
CREATE INDEX idx_watchlist_active ON watchlist(is_active);
```

---

## Configuration

### `backend/config/screening_config.py`
```python
class ScreeningConfig:
    # Fundamental Criteria (from requirements)
    FUNDAMENTAL_CRITERIA = {
        'long_term': {
            'gross_margin': {'operator': '>', 'threshold': 60.0, 'weight': 1.5},
            'roic': {'operator': '>', 'threshold': 12.0, 'weight': 1.0},
            'roe': {'operator': '>', 'threshold': 15.0, 'weight': 1.0},
            'leveraged_fcf': {'operator': '>', 'threshold': 20.0, 'weight': 1.2},
            'interest_coverage': {'operator': '>', 'threshold': 3.0, 'weight': 0.8},
            'eps_growth_5y': {'operator': '>', 'threshold': 10.0, 'weight': 1.3}
        },
        'short_term': {
            'gross_margin': {'operator': '>', 'threshold': 60.0, 'weight': 1.0},
            'eps_growth_5y': {'operator': '>', 'threshold': 10.0, 'weight': 1.0}
        }
    }
    
    # Technical Criteria (from tradingoff breakout detector)
    TECHNICAL_CRITERIA = {
        'short_term': {
            'breakout_detected': {'operator': '==', 'threshold': True, 'weight': 2.0},
            'above_sma_50': {'operator': '==', 'threshold': True, 'weight': 1.5},
            'volume_surge': {'operator': '==', 'threshold': True, 'weight': 1.2},
            'mansfield_rsi': {'operator': '>', 'threshold': 0, 'weight': 1.0},
            'consolidation_quality': {'operator': '>', 'threshold': 0.7, 'weight': 1.3}
        },
        'long_term': {
            'above_sma_150': {'operator': '==', 'threshold': True, 'weight': 1.5},
            'above_sma_200': {'operator': '==', 'threshold': True, 'weight': 1.5},
            'mansfield_rsi': {'operator': '>', 'threshold': 0, 'weight': 1.2},
            'price_vs_52w_high': {'operator': '>', 'threshold': 0.9, 'weight': 1.0}
        }
    }
    
    # Breakout Detection (port from tradingoff config)
    BREAKOUT_CONFIG = {
        'lookback_days': 40,
        'zigzag_deviation': 6.0,
        'min_resistance_touches': 2,
        'min_support_touches': 2,
        'extreme_grouping_tolerance': 2.5,
        'breakout_confirmation_pct': 1.5,
        'volume_lookback_days': 20,
        'min_days_between_swings': 2,
        'max_daily_change': 30.0,
        'min_volume_threshold': 5000,
        'max_volatility_filter': 150.0
    }
    
    # Scoring
    SCORING_METHOD = 'weighted'  # 'weighted', 'simple'
    PASS_THRESHOLD = 0.7  # 70% of criteria must pass
    
    # Recommendations
    RECOMMENDATION_THRESHOLDS = {
        'strong_buy': 0.85,
        'buy': 0.70,
        'hold': 0.50,
        'sell': 0.0
    }
```

---

## Implementation Plan

### Step 10.1: Breakout Detector (Port from tradingoff)
**Description**: Port breakout detection logic from `d_breakout_detector_3.py` and `g_consolidation.py`

**Tasks**:
- [ ] Create `backend/scripts/detect_breakouts.py`
- [ ] Port ZigZag algorithm for support/resistance detection
- [ ] Port consolidation detection logic
- [ ] Implement volume surge detection
- [ ] Calculate consolidation quality score
- [ ] Store results in `breakout_signals` table
- [ ] Support multiple timeframes (15d, 30d, 60d)

**Dependencies**: Phase 6 (price data, technical indicators)

**Deliverables**:
- Breakout detection script
- Breakout signals in database

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/detect_breakouts.py`
- [ ] Detects consolidation patterns (same logic as tradingoff)
- [ ] Identifies breakout signals
- [ ] Calculates quality scores
- [ ] Stores results for all held positions

**Tests**:
- [ ] Unit test: `test_zigzag_algorithm()`
- [ ] Unit test: `test_consolidation_detection()`
- [ ] Unit test: `test_breakout_confirmation()`
- [ ] Unit test: `test_volume_surge_detection()`
- [ ] Integration test: `test_detect_breakouts_all_positions()`

**Test File**: `backend/tests/test_detect_breakouts.py`

**Estimated Time**: 6 hours

---

### Step 10.2: Fundamental Screener
**Description**: Evaluate positions against fundamental criteria

**Tasks**:
- [ ] Create `backend/utils/fundamental_screener.py`
- [ ] Implement criteria evaluation engine
- [ ] Calculate fundamental score (weighted)
- [ ] Support configurable criteria
- [ ] Handle missing data gracefully
- [ ] Return detailed pass/fail breakdown

**Dependencies**: Phase 6 (fundamental data)

**Deliverables**:
- Fundamental screening engine

**Acceptance Criteria**:
- [ ] Evaluates all fundamental criteria
- [ ] Calculates weighted score
- [ ] Returns criteria breakdown (which passed/failed)
- [ ] Handles missing metrics (partial scoring)

**Tests**:
- [ ] Unit test: `test_evaluate_single_criterion()`
- [ ] Unit test: `test_calculate_fundamental_score()`
- [ ] Unit test: `test_handle_missing_data()`
- [ ] Unit test: `test_weighted_scoring()`

**Test File**: `backend/tests/test_fundamental_screener.py`

**Estimated Time**: 3 hours

---

### Step 10.3: Technical Screener
**Description**: Evaluate positions against technical criteria

**Tasks**:
- [ ] Create `backend/utils/technical_screener.py`
- [ ] Implement technical criteria evaluation
- [ ] Check MA positions (above/below SMA 50/150/200)
- [ ] Evaluate Mansfield RSI
- [ ] Check breakout signals
- [ ] Calculate technical score (weighted)
- [ ] Support short-term vs long-term criteria

**Dependencies**: Phase 6 (technical indicators), Step 10.1 (breakout signals)

**Deliverables**:
- Technical screening engine

**Acceptance Criteria**:
- [ ] Evaluates all technical criteria
- [ ] Checks MA positions correctly
- [ ] Incorporates breakout signals
- [ ] Calculates weighted score
- [ ] Differentiates short-term vs long-term

**Tests**:
- [ ] Unit test: `test_evaluate_ma_position()`
- [ ] Unit test: `test_evaluate_mansfield_rsi()`
- [ ] Unit test: `test_evaluate_breakout_signal()`
- [ ] Unit test: `test_calculate_technical_score()`

**Test File**: `backend/tests/test_technical_screener.py`

**Estimated Time**: 3 hours

---

### Step 10.4: Screening Orchestrator
**Description**: Combine fundamental and technical screening

**Tasks**:
- [ ] Create `backend/scripts/screen_positions.py`
- [ ] Run fundamental screening
- [ ] Run technical screening
- [ ] Calculate overall score
- [ ] Rank positions by score
- [ ] Generate recommendations (strong_buy, buy, hold, sell)
- [ ] Store results in `screening_results` table
- [ ] Support filtering by investment horizon

**Dependencies**: Steps 10.2, 10.3

**Deliverables**:
- Position screening orchestrator

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/screen_positions.py`
- [ ] Screens all held positions
- [ ] Calculates overall scores
- [ ] Ranks positions
- [ ] Generates recommendations
- [ ] Stores results in database

**Tests**:
- [ ] Integration test: `test_screen_all_positions()`
- [ ] Integration test: `test_ranking_logic()`
- [ ] Integration test: `test_recommendation_generation()`

**Test File**: `backend/tests/test_screen_positions.py`

**Estimated Time**: 3 hours

---

### Step 10.5: Screening API Endpoints
**Description**: Create API endpoints for screening results

**Tasks**:
- [ ] Create `backend/api/routes/screening.py`
- [ ] Add `GET /api/screening/results` - Get screening results
- [ ] Add `GET /api/screening/results/{symbol}` - Get results for symbol
- [ ] Add `POST /api/screening/run` - Trigger screening
- [ ] Add `GET /api/screening/criteria` - Get screening criteria
- [ ] Add `PUT /api/screening/criteria/{id}` - Update criteria
- [ ] Add query parameters: `horizon`, `min_score`, `recommendation`

**Dependencies**: Step 10.4

**Deliverables**:
- Screening API endpoints

**Acceptance Criteria**:
- [ ] GET `/api/screening/results?horizon=long_term&min_score=0.7` returns filtered results
- [ ] GET `/api/screening/results/AAPL` returns detailed breakdown
- [ ] POST `/api/screening/run` triggers screening
- [ ] Can filter by investment horizon and score
- [ ] Returns ranked list

**Tests**:
- [ ] API test: `test_get_screening_results()`
- [ ] API test: `test_get_symbol_screening_details()`
- [ ] API test: `test_run_screening()`
- [ ] API test: `test_filter_by_horizon()`
- [ ] API test: `test_filter_by_score()`

**Test File**: `backend/tests/test_screening_api.py`

**Estimated Time**: 3 hours

---

### Step 10.6: Screening Dashboard Page
**Description**: Create screening results dashboard

**Tasks**:
- [ ] Create `frontend/src/pages/Screening.vue`
- [ ] Add route `/screening`
- [ ] Create tabs: Short-Term, Long-Term, All
- [ ] Display ranked positions table
- [ ] Show scores (fundamental, technical, overall)
- [ ] Add filters (min score, recommendation)
- [ ] Add navigation link from main menu

**Dependencies**: Step 10.5

**Deliverables**:
- Screening dashboard page

**Acceptance Criteria**:
- [ ] Page loads at `/screening`
- [ ] Tabs work (Short-Term, Long-Term, All)
- [ ] Displays ranked positions
- [ ] Shows all scores
- [ ] Filters work
- [ ] Can click symbol to view details

**Tests**:
- [ ] Frontend test: `test_screening_dashboard_renders()`
- [ ] Frontend test: `test_tab_navigation()`
- [ ] Frontend test: `test_filtering()`

**Test File**: `frontend/src/pages/__tests__/Screening.test.ts`

**Estimated Time**: 3 hours

---

### Step 10.7: Screening Results Table Component
**Description**: Display screening results in sortable table

**Tasks**:
- [ ] Create `frontend/src/components/ScreeningResultsTable.vue`
- [ ] Display columns: Symbol, Overall Score, Fundamental Score, Technical Score, Recommendation
- [ ] Add color coding (green=strong_buy, yellow=buy, gray=hold, red=sell)
- [ ] Make sortable by any column
- [ ] Add expand row to show criteria breakdown
- [ ] Show pass/fail indicators for each criterion

**Dependencies**: Step 10.6

**Deliverables**:
- Screening results table component

**Acceptance Criteria**:
- [ ] Table displays all screening results
- [ ] Color coding works
- [ ] Sortable by all columns
- [ ] Expandable rows show criteria details
- [ ] Pass/fail indicators clear

**Tests**:
- [ ] Frontend test: `test_screening_table_renders()`
- [ ] Frontend test: `test_sorting()`
- [ ] Frontend test: `test_expand_row()`
- [ ] Frontend test: `test_color_coding()`

**Test File**: `frontend/src/components/__tests__/ScreeningResultsTable.test.ts`

**Estimated Time**: 3 hours

---

### Step 10.8: Criteria Breakdown Component
**Description**: Display detailed criteria pass/fail breakdown

**Tasks**:
- [ ] Create `frontend/src/components/CriteriaBreakdown.vue`
- [ ] Display fundamental criteria with pass/fail
- [ ] Display technical criteria with pass/fail
- [ ] Show actual values vs thresholds
- [ ] Add visual indicators (✅/❌)
- [ ] Group by category (fundamental/technical)

**Dependencies**: Step 10.6

**Deliverables**:
- Criteria breakdown component

**Acceptance Criteria**:
- [ ] Displays all criteria
- [ ] Shows pass/fail clearly
- [ ] Shows actual values and thresholds
- [ ] Visual indicators work
- [ ] Grouped logically

**Tests**:
- [ ] Frontend test: `test_criteria_breakdown_renders()`
- [ ] Frontend test: `test_pass_fail_indicators()`

**Test File**: `frontend/src/components/__tests__/CriteriaBreakdown.test.ts`

**Estimated Time**: 2.5 hours

---

### Step 10.9: Watchlist Management
**Description**: Add/remove symbols to watchlist

**Tasks**:
- [ ] Create `frontend/src/pages/Watchlist.vue`
- [ ] Add route `/watchlist`
- [ ] Display watchlist table
- [ ] Add "Add Symbol" form
- [ ] Add remove symbol functionality
- [ ] Show screening results for watchlist symbols
- [ ] Add notes field per symbol

**Dependencies**: Step 10.5

**Deliverables**:
- Watchlist management page

**Acceptance Criteria**:
- [ ] Page loads at `/watchlist`
- [ ] Can add symbols to watchlist
- [ ] Can remove symbols
- [ ] Shows screening results for watchlist
- [ ] Can add/edit notes

**Tests**:
- [ ] Frontend test: `test_watchlist_page_renders()`
- [ ] Frontend test: `test_add_symbol()`
- [ ] Frontend test: `test_remove_symbol()`

**Test File**: `frontend/src/pages/__tests__/Watchlist.test.ts`

**Estimated Time**: 3 hours

---

### Step 10.10: Breakout Signals Display
**Description**: Display breakout signals on position detail page

**Tasks**:
- [ ] Create `frontend/src/components/BreakoutSignals.vue`
- [ ] Display recent breakout signals
- [ ] Show pattern type, confidence, quality score
- [ ] Add to position detail page (new tab or section)
- [ ] Show consolidation metrics
- [ ] Display support/resistance levels

**Dependencies**: Step 10.1

**Deliverables**:
- Breakout signals component

**Acceptance Criteria**:
- [ ] Displays breakout signals for position
- [ ] Shows pattern details
- [ ] Shows quality scores
- [ ] Integrated into position detail page

**Tests**:
- [ ] Frontend test: `test_breakout_signals_renders()`
- [ ] Frontend test: `test_signal_details_display()`

**Test File**: `frontend/src/components/__tests__/BreakoutSignals.test.ts`

**Estimated Time**: 2.5 hours

---

### Step 10.11: Screening Criteria Configuration UI
**Description**: Allow users to customize screening criteria

**Tasks**:
- [ ] Create `frontend/src/components/ScreeningCriteriaConfig.vue`
- [ ] Display all criteria in editable form
- [ ] Support adding new criteria
- [ ] Support editing thresholds and weights
- [ ] Support enabling/disabling criteria
- [ ] Add "Reset to Defaults" button
- [ ] Save changes via API

**Dependencies**: Step 10.5

**Deliverables**:
- Screening criteria configuration UI

**Acceptance Criteria**:
- [ ] Displays all criteria
- [ ] Can edit thresholds and weights
- [ ] Can enable/disable criteria
- [ ] Can add custom criteria
- [ ] Saves changes successfully
- [ ] Can reset to defaults

**Tests**:
- [ ] Frontend test: `test_criteria_config_renders()`
- [ ] Frontend test: `test_edit_criteria()`
- [ ] Frontend test: `test_toggle_criteria()`
- [ ] Frontend test: `test_save_changes()`

**Test File**: `frontend/src/components/__tests__/ScreeningCriteriaConfig.test.ts`

**Estimated Time**: 3 hours

---

### Step 10.12: Scheduled Screening
**Description**: Automate daily screening

**Tasks**:
- [ ] Create `backend/scripts/scheduled_screening.py`
- [ ] Run breakout detection daily
- [ ] Run position screening daily
- [ ] Generate screening report
- [ ] Add to automation pipeline
- [ ] Send notifications for new strong_buy signals

**Dependencies**: Steps 10.1, 10.4

**Deliverables**:
- Scheduled screening automation

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/scheduled_screening.py`
- [ ] Runs breakout detection
- [ ] Runs position screening
- [ ] Generates report
- [ ] Runs daily via scheduler

**Tests**:
- [ ] Integration test: `test_scheduled_screening()`

**Test File**: `backend/tests/test_scheduled_screening.py`

**Estimated Time**: 2 hours

---

## Performance Optimization

### Screening Execution
- Batch database queries (fetch all data at once)
- Cache screening results (recalculate only on new data)
- Parallel processing for multiple symbols
- Use database indexes on symbol and date

### Frontend Optimization
- Paginate screening results (show 20 at a time)
- Lazy load criteria breakdown
- Cache screening data (refresh every 5 minutes)

### Breakout Detection
- Optimize ZigZag algorithm (vectorized operations)
- Cache intermediate calculations
- Process only symbols with new price data

---

## Data Validation Rules

### Screening Criteria
- Thresholds must be valid numbers
- Weights must be > 0
- Operators must be valid ('>', '<', '>=', '<=', '==')
- Investment horizon must be valid ('short_term', 'long_term', 'both')

### Screening Results
- Scores between 0 and 1
- Rank must be positive integer
- Recommendation must be valid option

### Breakout Signals
- Confidence score between 0 and 1
- Quality score between 0 and 1
- Volume ratio > 0

---

## UI/UX Considerations

### Visual Design
- Use score gauges or progress bars
- Color code recommendations (green/yellow/gray/red)
- Clear pass/fail indicators (✅/❌)
- Highlight top-ranked positions

### Information Hierarchy
- Overall score most prominent
- Fundamental and technical scores secondary
- Detailed criteria breakdown expandable

### Accessibility
- Keyboard navigation for tables
- Screen reader labels for scores
- High contrast mode support

---

## Future Enhancements (Document but Don't Implement)

### Advanced Screening
- Multi-factor models (combine more criteria)
- Machine learning-based scoring
- Backtesting screening strategies

### Pattern Recognition
- More chart patterns (head & shoulders, triangles, etc.)
- Pattern success rate tracking
- Pattern-based alerts

### Watchlist Features
- Import watchlist from CSV
- Share watchlist with others
- Track watchlist performance

---

## Acceptance Criteria

- [ ] Breakout detection works (same logic as tradingoff)
- [ ] Fundamental screening evaluates all criteria
- [ ] Technical screening evaluates all criteria
- [ ] Overall scoring and ranking works
- [ ] Screening dashboard displays results
- [ ] Can filter by investment horizon and score
- [ ] Criteria breakdown shows pass/fail details
- [ ] Watchlist management works
- [ ] Screening criteria configurable
- [ ] Scheduled screening runs daily
- [ ] All tests passing (unit, integration, API, frontend)
- [ ] Screens 50+ positions in < 5 seconds

---

## Related Requirements

- [PHASE_6_DATA_INFRASTRUCTURE.md](./PHASE_6_DATA_INFRASTRUCTURE.md) - Provides price and fundamental data
- [PHASE_7_POSITION_DETAILS.md](./PHASE_7_POSITION_DETAILS.md) - Position data used in screening
- [PHASE_8_PRICE_CHARTS.md](./PHASE_8_PRICE_CHARTS.md) - Technical indicators used in screening
- [PHASE_9_MARKET_SENTIMENT.md](./PHASE_9_MARKET_SENTIMENT.md) - Macro context for screening

---

## Notes

- **Breakout Logic**: Must exactly match tradingoff implementation (ZigZag, consolidation detection)
- **Configuration**: Port `y_consolidation_config.py` settings
- **Scoring**: Weighted scoring gives more importance to critical criteria
- **Investment Horizons**: Different criteria for short-term (swing trading) vs long-term (position trading)
- **Performance**: Optimize for batch processing of all positions
- **Watchlist**: Future enhancement - initially focus on held positions

---

## Quick Links

- [Previous Phase: Market Sentiment](./PHASE_9_MARKET_SENTIMENT.md)
- [tradingoff Reference: d_breakout_detector_3.py](../../tradingoff/scripts/techanal/d_breakout_detector_3.py)
- [tradingoff Reference: g_consolidation.py](../../tradingoff/scripts/techanal/g_consolidation.py)
