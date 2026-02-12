# Phase 8: Price Charts & Technical Indicators

**Add interactive price charts with technical indicators and configurable alert system for position monitoring.**

---

## Requirements

### Functional Requirements
- [ ] Display interactive price charts for each position
- [ ] Overlay technical indicators (SMA 50/150/200, EMA, RSI, Mansfield RSI, Volume)
- [ ] Show support/resistance levels (future: from options data)
- [ ] Implement configurable alerts (MA crossovers, gain-taking thresholds)
- [ ] Display alerts on position detail page and positions list
- [ ] Track alert history (when triggered, actions taken)
- [ ] Support both global and per-position alert rules

### Non-Functional Requirements
- [ ] Performance: Charts render in < 2 seconds
- [ ] Interactivity: Zoom, pan, hover for data points
- [ ] Responsiveness: Charts adapt to screen size
- [ ] Real-time: Update charts when new price data arrives

---

## Database Schema Changes

### New Tables

#### 1. `alert_rules` - Alert Configuration
```sql
CREATE TABLE IF NOT EXISTS alert_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT,  -- NULL for global rules
    rule_type TEXT NOT NULL,  -- 'ma_crossover', 'gain_threshold', 'price_target'
    rule_name TEXT NOT NULL,
    condition_json TEXT NOT NULL,  -- JSON config for the rule
    action TEXT NOT NULL,  -- 'sell_50_percent', 'sell_100_percent', 'notify'
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_alert_rules_symbol ON alert_rules(symbol);
CREATE INDEX idx_alert_rules_active ON alert_rules(is_active);
```

**Example `condition_json` for MA crossover:**
```json
{
  "indicator": "price",
  "crosses": "below",
  "target": "sma_50",
  "confirmation_days": 1
}
```

**Example `condition_json` for gain threshold:**
```json
{
  "gain_type": "unrealized_pct",
  "threshold": 20.0,
  "direction": "above"
}
```

#### 2. `alert_history` - Alert Trigger Log
```sql
CREATE TABLE IF NOT EXISTS alert_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_rule_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    triggered_date TEXT NOT NULL,
    trigger_price REAL NOT NULL,
    condition_met TEXT NOT NULL,  -- Description of what triggered
    action_recommended TEXT NOT NULL,
    action_taken TEXT,  -- NULL if no action, or description
    user_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (alert_rule_id) REFERENCES alert_rules(id)
);

CREATE INDEX idx_alert_history_symbol ON alert_history(symbol);
CREATE INDEX idx_alert_history_date ON alert_history(triggered_date);
```

#### 3. `support_resistance_levels` - Price Levels (Future Enhancement)
```sql
CREATE TABLE IF NOT EXISTS support_resistance_levels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    level_type TEXT NOT NULL,  -- 'support', 'resistance'
    price_level REAL NOT NULL,
    strength REAL,  -- 0-1 confidence score
    source TEXT,  -- 'options_max_pain', 'historical_pivot', 'manual'
    valid_from TEXT,
    valid_until TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, level_type, price_level)
);

CREATE INDEX idx_support_resistance_symbol ON support_resistance_levels(symbol);
```

---

## Configuration

### `backend/config/alerts_config.py`
```python
class AlertsConfig:
    # Global Alert Rules (apply to all positions unless overridden)
    GLOBAL_RULES = [
        {
            'rule_type': 'ma_crossover',
            'rule_name': 'Price crosses below SMA 50',
            'condition': {
                'indicator': 'price',
                'crosses': 'below',
                'target': 'sma_50',
                'confirmation_days': 1
            },
            'action': 'sell_50_percent'
        },
        {
            'rule_type': 'ma_crossover',
            'rule_name': 'Price crosses below SMA 150',
            'condition': {
                'indicator': 'price',
                'crosses': 'below',
                'target': 'sma_150',
                'confirmation_days': 1
            },
            'action': 'sell_50_percent'
        }
    ]
    
    # Alert Evaluation Frequency
    EVALUATION_FREQUENCY = 'daily'  # 'daily', 'hourly', 'real-time'
    
    # Alert Notification Settings
    NOTIFICATION_CHANNELS = ['in_app']  # 'in_app', 'email', 'sms'
    
    # Alert Display
    SHOW_TRIGGERED_ALERTS_DAYS = 30  # Show alerts from last 30 days
    MAX_ALERTS_PER_POSITION = 10  # Limit display
```

### `backend/config/chart_config.py`
```python
class ChartConfig:
    # Chart Library
    CHART_LIBRARY = 'plotly'  # 'plotly', 'matplotlib', 'chartjs'
    
    # Default Chart Settings
    DEFAULT_TIMEFRAME = '1Y'  # '1M', '3M', '6M', '1Y', '2Y', 'ALL'
    DEFAULT_CHART_TYPE = 'candlestick'  # 'candlestick', 'line', 'ohlc'
    
    # Technical Indicators Display
    DEFAULT_INDICATORS = ['sma_50', 'sma_150', 'sma_200', 'volume']
    INDICATOR_COLORS = {
        'sma_50': '#FF6B6B',
        'sma_150': '#4ECDC4',
        'sma_200': '#45B7D1',
        'ema_50': '#FFA07A',
        'volume': '#95A5A6'
    }
    
    # Chart Performance
    MAX_DATAPOINTS = 500  # Downsample if more
    ENABLE_CACHING = True
    CACHE_TTL_SECONDS = 3600  # 1 hour
```

---

## Implementation Plan

### Step 8.1: Alert Rules Engine
**Description**: Implement alert evaluation logic

**Tasks**:
- [ ] Create `backend/utils/alert_evaluator.py`
- [ ] Implement MA crossover detection
- [ ] Implement gain threshold detection
- [ ] Implement price target detection
- [ ] Add rule evaluation scheduler
- [ ] Store triggered alerts in `alert_history`
- [ ] Support both global and per-position rules

**Dependencies**: Phase 6 (technical indicators), Phase 7 (position summary)

**Deliverables**:
- Alert evaluation engine
- Scheduled alert checker

**Acceptance Criteria**:
- [ ] Detects when price crosses below SMA 50/150/200
- [ ] Detects when unrealized gain exceeds threshold
- [ ] Logs all triggered alerts to database
- [ ] Respects confirmation days (doesn't trigger on single-day spike)
- [ ] Global rules apply to all positions
- [ ] Per-position rules override global rules

**Tests**:
- [ ] Unit test: `test_detect_ma_crossover_below()`
- [ ] Unit test: `test_detect_ma_crossover_above()`
- [ ] Unit test: `test_detect_gain_threshold()`
- [ ] Unit test: `test_confirmation_days_logic()`
- [ ] Unit test: `test_global_vs_position_rules()`
- [ ] Integration test: `test_evaluate_all_positions()`

**Test File**: `backend/tests/test_alert_evaluator.py`

**Estimated Time**: 4 hours

---

### Step 8.2: Alert Management API
**Description**: Create API endpoints for alert configuration and history

**Tasks**:
- [ ] Create `backend/api/routes/alerts.py`
- [ ] Add `GET /api/alerts/rules` - List all alert rules
- [ ] Add `GET /api/alerts/rules/{symbol}` - Get rules for symbol
- [ ] Add `POST /api/alerts/rules` - Create new alert rule
- [ ] Add `PUT /api/alerts/rules/{id}` - Update alert rule
- [ ] Add `DELETE /api/alerts/rules/{id}` - Delete alert rule
- [ ] Add `GET /api/alerts/history/{symbol}` - Get alert history
- [ ] Add `POST /api/alerts/evaluate` - Manually trigger evaluation

**Dependencies**: Step 8.1

**Deliverables**:
- Alert management API endpoints

**Acceptance Criteria**:
- [ ] Can create, read, update, delete alert rules
- [ ] Can retrieve alert history for a symbol
- [ ] Can manually trigger alert evaluation
- [ ] Validates rule configuration before saving

**Tests**:
- [ ] API test: `test_create_alert_rule()`
- [ ] API test: `test_update_alert_rule()`
- [ ] API test: `test_delete_alert_rule()`
- [ ] API test: `test_get_alert_history()`
- [ ] API test: `test_manual_evaluation()`

**Test File**: `backend/tests/test_alerts_api.py`

**Estimated Time**: 3 hours

---

### Step 8.3: Chart Data Preparation
**Description**: Prepare and optimize data for charting

**Tasks**:
- [ ] Create `backend/utils/chart_data_builder.py`
- [ ] Implement data aggregation (combine price + indicators)
- [ ] Add downsampling for large datasets (> 500 points)
- [ ] Calculate support/resistance levels (from historical pivots)
- [ ] Format data for Plotly consumption
- [ ] Implement caching for chart data

**Dependencies**: Phase 6 (price data, technical indicators)

**Deliverables**:
- Chart data builder utility
- Optimized chart data format

**Acceptance Criteria**:
- [ ] Combines price data with technical indicators
- [ ] Downsamples data if > 500 points
- [ ] Returns data in Plotly-compatible format
- [ ] Caches results for 1 hour
- [ ] Handles missing data gracefully

**Tests**:
- [ ] Unit test: `test_build_chart_data()`
- [ ] Unit test: `test_downsample_large_dataset()`
- [ ] Unit test: `test_combine_price_and_indicators()`
- [ ] Unit test: `test_cache_chart_data()`

**Test File**: `backend/tests/test_chart_data_builder.py`

**Estimated Time**: 3 hours

---

### Step 8.4: Chart API Endpoints
**Description**: Create API endpoints for chart data

**Tasks**:
- [ ] Create `backend/api/routes/charts.py`
- [ ] Add `GET /api/charts/{symbol}` - Get chart data
- [ ] Add query parameters: `timeframe`, `indicators`, `chart_type`
- [ ] Add `GET /api/charts/{symbol}/support-resistance` - Get price levels
- [ ] Implement response caching
- [ ] Add error handling for missing data

**Dependencies**: Step 8.3

**Deliverables**:
- Chart data API endpoints

**Acceptance Criteria**:
- [ ] GET `/api/charts/AAPL?timeframe=1Y&indicators=sma_50,sma_200` returns chart data
- [ ] Supports timeframes: 1M, 3M, 6M, 1Y, 2Y, ALL
- [ ] Supports indicators: sma_50, sma_150, sma_200, ema_50, rsi, mansfield_rsi, volume
- [ ] Returns support/resistance levels
- [ ] Caches responses appropriately

**Tests**:
- [ ] API test: `test_get_chart_data()`
- [ ] API test: `test_chart_timeframe_filtering()`
- [ ] API test: `test_chart_indicator_selection()`
- [ ] API test: `test_support_resistance_levels()`

**Test File**: `backend/tests/test_charts_api.py`

**Estimated Time**: 2.5 hours

---

### Step 8.5: Price Chart Component (Frontend)
**Description**: Create interactive price chart component using Plotly

**Tasks**:
- [ ] Create `frontend/src/components/PriceChart.vue`
- [ ] Integrate Plotly.js library
- [ ] Implement candlestick chart
- [ ] Add technical indicator overlays
- [ ] Add volume subplot
- [ ] Implement zoom and pan
- [ ] Add hover tooltips with OHLCV data
- [ ] Add timeframe selector (1M, 3M, 6M, 1Y, 2Y, ALL)
- [ ] Add indicator toggle buttons

**Dependencies**: Step 8.4

**Deliverables**:
- Interactive price chart component

**Acceptance Criteria**:
- [ ] Displays candlestick chart with price data
- [ ] Overlays selected technical indicators
- [ ] Volume displayed in subplot
- [ ] Zoom and pan work smoothly
- [ ] Hover shows OHLCV values
- [ ] Timeframe selector updates chart
- [ ] Can toggle indicators on/off

**Tests**:
- [ ] Frontend test: `test_price_chart_renders()`
- [ ] Frontend test: `test_indicator_overlay()`
- [ ] Frontend test: `test_timeframe_selection()`
- [ ] Frontend test: `test_indicator_toggle()`

**Test File**: `frontend/src/components/__tests__/PriceChart.test.ts`

**Estimated Time**: 5 hours

---

### Step 8.6: Alert Display Components
**Description**: Display alerts on position pages and positions list

**Tasks**:
- [ ] Create `frontend/src/components/AlertBadge.vue` - Alert indicator badge
- [ ] Create `frontend/src/components/AlertPanel.vue` - Alert details panel
- [ ] Update `PositionDetail.vue` to show active alerts
- [ ] Update `Positions.vue` to add "Alert" column
- [ ] Add alert icon/badge when alerts are triggered
- [ ] Show alert details on hover or click
- [ ] Color code by severity (yellow=warning, red=sell signal)

**Dependencies**: Step 8.2

**Deliverables**:
- Alert display components
- Updated position pages with alerts

**Acceptance Criteria**:
- [ ] Alert badge shows on positions list if alerts exist
- [ ] Alert panel displays alert details (rule, trigger date, recommended action)
- [ ] Color coding works (yellow/red)
- [ ] Clicking alert shows full history
- [ ] Shows last 30 days of alerts

**Tests**:
- [ ] Frontend test: `test_alert_badge_renders()`
- [ ] Frontend test: `test_alert_panel_displays_details()`
- [ ] Frontend test: `test_alert_color_coding()`

**Test File**: `frontend/src/components/__tests__/AlertComponents.test.ts`

**Estimated Time**: 3 hours

---

### Step 8.7: Alert Configuration UI
**Description**: Create UI for managing alert rules

**Tasks**:
- [ ] Create `frontend/src/components/AlertRulesManager.vue`
- [ ] Display list of active alert rules
- [ ] Add "Create Alert Rule" form
- [ ] Support rule types: MA crossover, gain threshold
- [ ] Add toggle to enable/disable rules
- [ ] Add delete rule functionality
- [ ] Show global vs position-specific rules
- [ ] Add validation for rule configuration

**Dependencies**: Step 8.2

**Deliverables**:
- Alert rules management UI

**Acceptance Criteria**:
- [ ] Displays all alert rules (global and position-specific)
- [ ] Can create new alert rule with form
- [ ] Can toggle rule active/inactive
- [ ] Can delete rules
- [ ] Form validates inputs (e.g., threshold > 0)
- [ ] Shows which rules are global vs position-specific

**Tests**:
- [ ] Frontend test: `test_alert_rules_list_renders()`
- [ ] Frontend test: `test_create_alert_rule_form()`
- [ ] Frontend test: `test_toggle_rule_active()`
- [ ] Frontend test: `test_delete_rule()`

**Test File**: `frontend/src/components/__tests__/AlertRulesManager.test.ts`

**Estimated Time**: 4 hours

---

### Step 8.8: Integrate Charts into Position Detail Page
**Description**: Add chart tab to position detail page

**Tasks**:
- [ ] Update `frontend/src/pages/PositionDetail.vue`
- [ ] Add "Chart" tab
- [ ] Embed `PriceChart` component
- [ ] Add indicator selection controls
- [ ] Add timeframe controls
- [ ] Show support/resistance levels on chart (if available)
- [ ] Add "Alerts" section below chart

**Dependencies**: Steps 8.5, 8.6

**Deliverables**:
- Chart tab on position detail page

**Acceptance Criteria**:
- [ ] Chart tab displays price chart
- [ ] Can select indicators to display
- [ ] Can change timeframe
- [ ] Support/resistance levels shown (future enhancement)
- [ ] Active alerts displayed below chart

**Tests**:
- [ ] Frontend test: `test_chart_tab_renders()`
- [ ] Frontend test: `test_indicator_controls()`
- [ ] Frontend test: `test_timeframe_controls()`

**Test File**: `frontend/src/pages/__tests__/PositionDetail.test.ts`

**Estimated Time**: 2 hours

---

### Step 8.9: Scheduled Alert Evaluation
**Description**: Set up automated alert checking

**Tasks**:
- [ ] Create `backend/scripts/evaluate_alerts.py`
- [ ] Implement daily alert evaluation (runs after market close)
- [ ] Check all active alert rules against current data
- [ ] Log triggered alerts to `alert_history`
- [ ] Send notifications (in-app for now)
- [ ] Add to automation pipeline

**Dependencies**: Step 8.1

**Deliverables**:
- Scheduled alert evaluation script
- Automated alert monitoring

**Acceptance Criteria**:
- [ ] Script runs: `python backend/scripts/evaluate_alerts.py`
- [ ] Evaluates all active alert rules
- [ ] Logs triggered alerts
- [ ] Runs daily via scheduler (cron or similar)
- [ ] Completes in < 10 seconds for 50 positions

**Tests**:
- [ ] Integration test: `test_scheduled_alert_evaluation()`
- [ ] Integration test: `test_alert_notification()`

**Test File**: `backend/tests/test_evaluate_alerts.py`

**Estimated Time**: 2.5 hours

---

## Performance Optimization

### Chart Rendering
- Downsample data to max 500 points for display
- Use WebGL rendering for large datasets (Plotly supports this)
- Lazy load chart data (only when tab is opened)
- Cache chart images for static views

### Alert Evaluation
- Batch process all positions in single database query
- Cache technical indicator values
- Only evaluate active rules
- Use database indexes on (symbol, date)

### Frontend Optimization
- Debounce indicator toggle (wait 300ms)
- Virtualize alert history list (if > 50 alerts)
- Preload chart data for likely next timeframe

---

## Data Validation Rules

### Alert Rules
- Threshold values must be > 0
- Confirmation days between 0 and 5
- MA periods must exist in technical_indicators table
- Action must be valid ('sell_50_percent', 'sell_100_percent', 'notify')

### Chart Data
- Date range must be valid (start < end)
- Indicators requested must exist
- Timeframe must be valid option

---

## UI/UX Considerations

### Chart Interactivity
- Smooth zoom and pan
- Crosshair for precise value reading
- Legend shows/hides indicators
- Responsive to window resize

### Alert Display
- Non-intrusive badges (don't clutter UI)
- Clear visual hierarchy (critical alerts stand out)
- Easy to dismiss or acknowledge
- Show recommended action clearly

### Mobile Considerations
- Charts adapt to smaller screens
- Touch-friendly zoom/pan
- Simplified indicator selection on mobile

---

## Future Enhancements (Document but Don't Implement)

### Options-Based Support/Resistance
- Integrate options data API (when available)
- Calculate max pain levels
- Display high open interest strikes
- Update `support_resistance_levels` table

### Advanced Alerts
- Multi-condition alerts (price AND volume)
- Pattern-based alerts (breakout detection)
- Relative strength alerts (vs SPY)

### Real-Time Updates
- WebSocket for live price updates
- Real-time alert evaluation
- Live chart updates during market hours

---

## Acceptance Criteria

- [ ] Interactive price charts display on position detail page
- [ ] Technical indicators overlay correctly (SMA, EMA, RSI, Mansfield RSI, Volume)
- [ ] Alert rules can be created, edited, and deleted
- [ ] Alerts trigger correctly (MA crossovers, gain thresholds)
- [ ] Alert badges display on positions list
- [ ] Alert history tracked and displayed
- [ ] Charts render in < 2 seconds
- [ ] Zoom, pan, and hover work smoothly
- [ ] All tests passing (unit, integration, API, frontend)
- [ ] Scheduled alert evaluation runs daily

---

## Related Requirements

- [PHASE_6_DATA_INFRASTRUCTURE.md](./PHASE_6_DATA_INFRASTRUCTURE.md) - Provides price and technical indicator data
- [PHASE_7_POSITION_DETAILS.md](./PHASE_7_POSITION_DETAILS.md) - Position detail page where charts are displayed

---

## Notes

- **Chart Library**: Plotly.js chosen for interactivity and ease of use
- **Alert Frequency**: Daily evaluation sufficient for now (not day-trading)
- **Mansfield RSI**: Requires SPY data - ensure SPY is fetched in Phase 6
- **Support/Resistance**: Manual/historical pivots for now, options data later
- **Performance**: Optimize for 50+ positions with 2 years of data each

---

## Quick Links

- [Previous Phase: Position Details](./PHASE_7_POSITION_DETAILS.md)
- [Next Phase: Market Sentiment](./PHASE_9_MARKET_SENTIMENT.md)
