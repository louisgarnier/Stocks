# Raw Requirements - IBKR Portfolio Tracker

## Project Overview

Visualize exact holdings from Interactive Brokers (IBKR) with a Nuxt3 frontend interface. The system processes historical transactions and daily trade updates via the **IBKR Flex Web Service API** to maintain synchronized portfolio positions.

---

## Core Requirements

### 1. IBKR Holdings Visualization

**Goal**: Display accurate, real-time portfolio holdings that match IBKR exactly.

**Data Sources**:
- Historical transactions (initial bulk import via Flex Query)
- Daily trade updates (fetched via Flex Web Service API)

**Processing Pipeline**:

| Step | Script | Description |
|------|--------|-------------|
| A | `a_flex_fetch.py` | Fetch Flex Query report via IBKR Flex Web Service API |
| B | `b_daily_trades.py` | Process flex files, deduplicate using IBKR TransactionID, insert into SQLite DB |
| C | `c_trans_update.py` | Apply stock split adjustments to transactions |
| D | `d_positions.py` | Calculate current positions from all transactions |

---

## Flex Web Service API Configuration

### Overview
The **Flex Web Service** is IBKR's HTTP API for programmatically retrieving pre-configured Flex Query reports. This replaces the email-based approach with direct API calls.

### Setup Requirements (One-time in Client Portal)

1. **Enable Flex Web Service**
   - Navigate to: `Reporting` → `Flex Queries` → `Flex Web Service Configuration`
   - Enable the service and save
   - Note the **Current Token** (valid 6 hours to 1 year)

2. **Create a Flex Query**
   - Create an Activity Flex Query with required fields (trades, transactions)
   - Note the **Query ID** from the info icon

3. **Required Credentials**
   | Credential | Description | Where to Store |
   |------------|-------------|----------------|
   | Token | Access token for API authentication | `.env` file (never commit!) |
   | Query ID | Identifies which report template to fetch | Config file |

### API Workflow (Two-Step Process)

```
Step 1: Request Report Generation
────────────────────────────────────────────────────────────────
GET https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/SendRequest
    ?t={Token}
    &q={QueryID}
    &v=3

Response: <ReferenceCode>1234567890</ReferenceCode>

Step 2: Retrieve Generated Report (wait ~20 seconds)
────────────────────────────────────────────────────────────────
GET https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/GetStatement
    ?t={Token}
    &q={ReferenceCode}
    &v=3

Response: CSV/XML data with transactions
```

### Python Implementation Pattern

```python
import requests
import xml.etree.ElementTree as ET
import time

FLEX_BASE_URL = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
TOKEN = os.getenv("IBKR_FLEX_TOKEN")
QUERY_ID = os.getenv("IBKR_QUERY_ID")

def fetch_flex_report():
    # Step 1: Request report generation
    send_response = requests.get(
        f"{FLEX_BASE_URL}/SendRequest",
        params={"t": TOKEN, "q": QUERY_ID, "v": 3},
        headers={"User-Agent": "Python/FlexFetcher"}
    )
    
    # Parse reference code from XML response
    root = ET.fromstring(send_response.text)
    status = root.find("Status").text
    if status != "Success":
        raise Exception(f"Failed: {root.find('ErrorMessage').text}")
    
    ref_code = root.find("ReferenceCode").text
    
    # Step 2: Wait and retrieve report
    time.sleep(20)  # Allow report to generate
    
    get_response = requests.get(
        f"{FLEX_BASE_URL}/GetStatement",
        params={"t": TOKEN, "q": ref_code, "v": 3},
        headers={"User-Agent": "Python/FlexFetcher"}
    )
    
    return get_response.content  # CSV or XML data
```

### Benefits Over Email-Based Approach

| Aspect | Email (Old) | Flex API (New) |
|--------|-------------|----------------|
| **Dependency** | Outlook + Microsoft Graph API | Direct IBKR API |
| **Trigger** | Manual or scheduled email check | On-demand API call |
| **Latency** | Wait for email delivery | Immediate (T+1 data) |
| **Complexity** | OAuth + email parsing | Simple HTTP GET |
| **Reliability** | Email delivery issues possible | Direct API, more reliable |

**Key Features**:
- Deduplication using IBKR's `TransactionID` to prevent duplicate entries
- Stock split adjustments (e.g., 4-for-1 splits) applied to historical transactions
- Position calculation using split-adjusted quantities
- CSV backup exports for audit trail

### 2. Nuxt3 Frontend Interface

**Goal**: Track each processing step from a modern web interface.

**Critical Constraint**: ⚠️ **Keeping the interface synchronized with IBKR is tricky** - must be very careful about data consistency.

**Required Views**:
- Dashboard showing current holdings
- Transaction history with filtering
- Processing pipeline status (which step ran, when, results)
- Sync status indicator (last sync time, any discrepancies)

**Tech Stack**:
- Frontend: Nuxt3 (Vue.js)
- Backend: Python (FastAPI recommended)
- Database: SQLite (as per example scripts)

---

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DAILY WORKFLOW                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    IBKR Flex Web Service API                  │   │
│  │  1. SendRequest (Token + QueryID) → ReferenceCode             │   │
│  │  2. GetStatement (Token + RefCode) → CSV/XML Data             │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                 │                                    │
│                                 ▼                                    │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐           │
│  │  Flex Fetch  │───▶│ Daily Trades │───▶│ Trans Update │           │
│  │   (Step A)   │    │   (Step B)   │    │   (Step C)   │           │
│  └──────────────┘    └──────────────┘    └──────┬───────┘           │
│                                                  │                   │
│                                                  ▼                   │
│  ┌──────────────┐    ┌──────────────────────────────────────────┐   │
│  │  Positions   │◀───│              SQLite Database              │   │
│  │   (Step D)   │    │  - transactions (with split adjustments) │   │
│  └──────┬───────┘    │  - positions (current holdings)          │   │
│         │            └──────────────────────────────────────────┘   │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Nuxt3 Frontend                             │   │
│  │  - Holdings dashboard                                         │   │
│  │  - Transaction history                                        │   │
│  │  - Sync status & pipeline monitoring                          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Database Schema (from example scripts)

### transactions table
| Column | Type | Description |
|--------|------|-------------|
| transaction_id | TEXT | Internal ID (TR00000001 format) |
| source_file | TEXT | Original flex file name |
| asset_category | TEXT | "Stocks" |
| currency | TEXT | e.g., "USD", "EUR" |
| symbol | TEXT | Stock ticker |
| trade_date | TEXT | DD/MM/YYYY format |
| quantity | REAL | Original quantity |
| t_price | REAL | Trade price |
| c_price | REAL | Close price |
| proceeds | REAL | Trade proceeds |
| comm_fee | REAL | Commission/fees |
| basis | REAL | Cost basis |
| original_transaction_id | TEXT | IBKR_TXN_xxxxx (for deduplication) |
| stock_splits_applied | TEXT | Split description or "no split" |
| updated_quantity | REAL | Split-adjusted quantity |
| updated_t_price | REAL | Split-adjusted price |

### positions table
| Column | Type | Description |
|--------|------|-------------|
| symbol | TEXT | Stock ticker |
| total_updated_quantity | REAL | Current holding (split-adjusted) |
| transaction_count | INTEGER | Number of transactions |

---

## Synchronization Concerns

⚠️ **Critical**: The interface must stay in sync with IBKR. Key considerations:

1. **Deduplication**: Use `original_transaction_id` (IBKR TransactionID) to prevent duplicates
2. **Stock Splits**: Must apply splits to historical transactions correctly
3. **Daily Updates**: Fetch Flex Query daily to capture new trades
4. **Audit Trail**: Keep CSV backups for verification
5. **Error Handling**: Log all processing steps for debugging

---

## Input Files

### Flex Query Reports (via API)
- Source: IBKR Flex Web Service API
- Format: CSV or XML (configurable in Flex Query settings)
- Trigger: On-demand API call or scheduled (cron/scheduler)

### Stock Splits Configuration
- Location: `input/specs/stock_splits.csv`
- Format: `SYMBOL;DD/MM/YYYY;ratio-for-1` (semicolon-separated)
- Example: `AAPL;28/08/2020;4-for-1`

---

## Output Files

| File | Location | Description |
|------|----------|-------------|
| transactions_DD_MM_YYYY.csv | output/ibkr/ | Transaction backup |
| positions_DD_MM_YYYY.csv | output/ibkr/ | Positions backup |
| finance.db | output/database/ | SQLite database |

---

## Notes & Context

- **IBKR Flex Web Service**: Direct API access to Flex Query reports (no email dependency)
- **Token Management**: Flex token valid 6 hours to 1 year (configurable in Client Portal)
- **European Number Format**: CSV exports use comma as decimal separator
- **Asset Filter**: Only STK (stocks) asset class is processed
- **Rate Limiting**: Allow ~20 seconds between SendRequest and GetStatement calls

---

## Environment Variables

```bash
# .env file (never commit to git!)
IBKR_FLEX_TOKEN=your_flex_token_here
IBKR_QUERY_ID=your_query_id_here
```

---

**Next Step**: Analyze and structure these requirements in `ANALYZED_REQUIREMENTS.md`

