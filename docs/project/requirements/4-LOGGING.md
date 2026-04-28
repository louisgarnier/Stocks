# 🔧 Stage 4 — Logging Setup & Architecture
> **Output →** `docs/project/config/logging.md`
> **Instructions:** Configure comprehensive logging BEFORE starting development.
> Logging is essential for debugging, monitoring, and maintaining any project.
> This must be implemented immediately after architecture decisions are locked.
> Status: `[ ] Draft` → `[ ] Configured` → `[ ] Tested` → `[ ] Locked`

## 📥 Inputs from 3-ARCHITECTURE.md
- **Tech Stack** → Choose appropriate logging libraries (Python logging vs Winston, etc.)
- **Component Breakdown** → Identify which components need logging instrumentation
- **System Overview** → Design logging flow to match data flow
- **Folder Structure** → Place logger modules and log files appropriately
- **Environment Variables** → Configure LOG_LEVEL and log destinations
- **API Design** → Implement HTTP request/response logging middleware
- **Technical Decisions** → Make logging implementation choices (format, rotation, etc.)
- **Performance Assumptions** → Ensure logging doesn't impact performance requirements

---

## Overview

Every project needs **comprehensive, multi-layered logging** that captures every change, request, and error across the entire stack. This enables complete traceability and debugging capabilities.

### Key Requirements
- ✅ **Complete request/response logging** - Every API call logged with timing
- ✅ **Automatic error capture** - All exceptions caught and logged with full stack traces
- ✅ **Multi-layer integration** - Frontend, backend, and database logs unified
- ✅ **Console + file output** - Logs appear in terminal AND are persisted to files
- ✅ **Daily rotation** - Log files created per day (e.g., `backend_2026-03-10.log`)

---

## Log Files Structure

All log files are stored in the **`/logs`** directory at the project root:

```
/logs/
├── backend_YYYY-MM-DD.log      # All backend activity, errors, startup
├── api_YYYY-MM-DD.log          # API routes, requests, responses
├── database_YYYY-MM-DD.log     # Database operations, queries
├── frontend_YYYY-MM-DD.log     # Frontend logs sent from browser
└── tests_YYYY-MM-DD.log        # Test execution logs
```

### File Purposes

| File | Purpose | What's Logged |
|------|---------|---------------|
| **backend_*.log** | General backend operations | Server startup, exceptions, stdout/stderr, all errors |
| **api_*.log** | API request/response tracking | HTTP requests, responses, status codes, timing |
| **database_*.log** | Database operations | SQL queries, connection issues, data operations |
| **frontend_*.log** | Frontend application logs | User actions, API calls from browser, frontend errors |
| **tests_*.log** | Test execution | Test runs, assertions, test errors |

---

## Backend Logging (Python/FastAPI)

### 1. Logger Configuration

```python
# backend/api/utils/logger.py
import logging
import sys
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("app")

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(f"app.{name}")

# Loggers by module
api_logger = get_logger("api")
db_logger = get_logger("database")

def log_event(event_type: str, entity: str, entity_id: int = None, details: dict = None):
    """Log a business event."""
    id_str = f"#{entity_id}" if entity_id else ""
    details_str = f" - {details}" if details else ""
    logger.info(f"📌 [{event_type}] {entity}{id_str}{details_str}")
```

### 2. HTTP Request Logging Middleware

```python
# backend/api/middleware/logging_middleware.py
import time
import logging
from fastapi import Request

logger = logging.getLogger("app.api.requests")

async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    logger.info(f"📥 {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    process_time = (time.time() - start_time) * 1000
    logger.info(f"📤 {request.method} {request.url.path} - {response.status_code} - {process_time:.2f}ms")
    
    return response
```

### 3. Main Application Setup

```python
# backend/api/main.py
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from backend.api.middleware.logging_middleware import log_requests
from backend.api.utils.logger import logger

app = FastAPI()
app.add_middleware(BaseHTTPMiddleware, dispatch=log_requests)

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting API")
```

---

## Frontend Logging

### 1. Terminal Logging (API Proxy)

**Important:** `console.log` in the browser is NOT visible in the terminal.
For terminal logs, use an **API Proxy Route**:

```typescript
// frontend/app/api/proxy/[...path]/route.ts
import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

const formatTimestamp = () => {
  return new Date().toISOString().replace('T', ' ').substring(0, 23);
};

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const endpoint = '/' + path.join('/');
  const searchParams = request.nextUrl.searchParams.toString();
  const fullPath = searchParams ? `${endpoint}?${searchParams}` : endpoint;
  
  console.log(`${formatTimestamp()} 📡 [Frontend->API] GET ${fullPath}`);
  
  try {
    const response = await fetch(`${BACKEND_URL}${fullPath}`, {
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await response.json();
    
    console.log(`${formatTimestamp()} ✅ [Frontend->API] GET ${fullPath} - ${response.status}`);
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error(`${formatTimestamp()} ❌ [Frontend->API] GET ${fullPath} - Error:`, error);
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 503 });
  }
}
```

### 2. Browser Console Logging

```typescript
// frontend/src/utils/logger.ts
const isDev = process.env.NODE_ENV === 'development';

type LogLevel = 'info' | 'warn' | 'error' | 'debug';

interface LogOptions {
  component?: string;
  data?: unknown;
}

const log = (level: LogLevel, message: string, options?: LogOptions) => {
  if (!isDev && level === 'debug') return;
  
  const prefix = options?.component ? `[${options.component}]` : '';
  const emoji = { info: '📘', warn: '⚠️', error: '❌', debug: '🔍' }[level];
  const logFn = { info: console.log, warn: console.warn, error: console.error, debug: console.debug }[level];
  
  if (options?.data) {
    logFn(`${emoji} ${prefix} ${message}`, options.data);
  } else {
    logFn(`${emoji} ${prefix} ${message}`);
  }
};

export const logger = {
  info: (msg: string, opts?: LogOptions) => log('info', msg, opts),
  warn: (msg: string, opts?: LogOptions) => log('warn', msg, opts),
  error: (msg: string, opts?: LogOptions) => log('error', msg, opts),
  debug: (msg: string, opts?: LogOptions) => log('debug', msg, opts),
};
```

---

## Database Logging

```python
# backend/database/connection.py
from backend.api.utils.logger import db_logger

def get_db_connection():
    db_logger.debug("🗄️ Opening database connection")
    conn = sqlite3.connect(DB_FILE)
    return conn

def init_database():
    db_logger.info("🗄️ Initializing database")
    # ... schema creation
    db_logger.info("✅ Database initialized")
```

### SQL Logging (Optional)

```python
import logging

# Enable SQL logs
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Or via create_engine
engine = create_engine(DATABASE_URL, echo=True)
```

---

## Logging Conventions

### Standard Emojis

| Emoji | Usage |
|-------|-------|
| 📥 | Incoming request |
| 📤 | Outgoing response |
| 📡 | API call |
| ✅ | Success |
| ❌ | Error |
| ⚠️ | Warning |
| 🔄 | Loading/Processing |
| 🗄️ | Database |
| 🚀 | Startup |
| 📌 | Business event |

### Prefixes

```
[ComponentName] Message
[API] Message
[DB] Message
[Auth] Message
```

### Log Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Technical details, variables |
| `INFO` | Normal flow, business events |
| `WARNING` | Abnormal but handled situations |
| `ERROR` | Errors requiring attention |

### Never Log

- Passwords or tokens
- Personal sensitive data
- Credit card numbers

---

## Environment Configuration

### Backend (.env)

```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

### Frontend (.env.local)

```bash
BACKEND_URL=http://localhost:8000
```

---

## Complete Request Flow Example

```
# User clicks "Create"

[Frontend Terminal]
2026-03-15 10:40:24.400 📡 [Frontend->API] POST /api/users
2026-03-15 10:40:24.450 ✅ [Frontend->API] POST /api/users - 201

[Backend Terminal]
2026-03-15 10:40:24,410 - app.api.requests - INFO - 📥 POST /api/users
2026-03-15 10:40:24,420 - app.database - INFO - 🗄️ INSERT users
2026-03-15 10:40:24,430 - app - INFO - 📌 [CREATED] User#123
2026-03-15 10:40:24,440 - app.api.requests - INFO - 📤 POST /api/users - 201 - 30.00ms

[Browser Console]
📘 [UserForm] Form submitted
✅ [UserForm] User created successfully
```

---

## Implementation Checklist

Before proceeding to development:

- [ ] **Backend**: Logger configured with timestamps and emojis
- [ ] **Backend**: HTTP request logging middleware implemented
- [ ] **Frontend**: API Proxy route for terminal logs
- [ ] **Frontend**: Browser console logger utility
- [ ] **Database**: Database operation logging
- [ ] **Environment**: LOG_LEVEL configuration in .env
- [ ] **Testing**: Log a test request end-to-end and verify all layers

---

## 📤 Outputs for 5-EPICS.md

**Once LOGGING is CONFIGURED and TESTED, these outputs feed directly into epic planning:**

- **Logging Infrastructure** → EPICS Story 1.2 foundation (logging is already set up)
- **Component Logging Points** → EPICS individual stories (each component knows how to log)
- **Error Handling Patterns** → EPICS error handling stories (consistent error logging approach)
- **Testing Logging Setup** → EPICS testing stories (verify logs work in each story)
- **Performance Considerations** → EPICS performance stories (logging overhead accounted for)
- **Environment Configuration** → EPICS deployment stories (LOG_LEVEL and log file setup)
- **Debugging Workflow** → EPICS development process (how to debug using logs)

---

*→ Once logging is configured and tested, proceed to `5-EPICS.md` with the structured outputs above*
