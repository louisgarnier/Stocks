# Logging Setup Guide

Template pour configurer les logs dans un projet fullstack. Ce guide couvre les 4 couches essentielles:

| Couche | Où les logs apparaissent |
|--------|--------------------------|
| **Backend (Python/FastAPI)** | Terminal backend |
| **Frontend Terminal (Next.js)** | Terminal frontend (via API Proxy) |
| **Frontend Browser** | Console DevTools du navigateur |
| **Database** | Terminal backend |

---

## ⚠️ Checklist de Setup

Avant de commencer le développement, vérifiez que ces éléments sont en place:

- [ ] **Backend**: Logger configuré avec timestamps et emojis
- [ ] **Backend**: Middleware de logging des requêtes HTTP
- [ ] **Frontend**: API Proxy route pour logs terminal
- [ ] **Frontend**: Utilitaire logger pour browser console
- [ ] **Database**: Logs SQL activés (optionnel, pour debug)

---

## 1. Backend (Python/FastAPI)

### 1.1 Configuration du logger principal

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

# Loggers par module
api_logger = get_logger("api")
db_logger = get_logger("database")

def log_event(event_type: str, entity: str, entity_id: int = None, details: dict = None):
    """Log un événement métier."""
    id_str = f"#{entity_id}" if entity_id else ""
    details_str = f" - {details}" if details else ""
    logger.info(f"📌 [{event_type}] {entity}{id_str}{details_str}")
```

### 1.2 Middleware de logging HTTP

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

### 1.3 Intégration dans main.py

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

### 1.4 Résultat dans le terminal backend

```
2026-02-08 12:37:24,089 - app - INFO - 🚀 Starting API
2026-02-08 12:37:33,719 - app.api.requests - INFO - 📥 GET /health
2026-02-08 12:37:33,724 - app.api.requests - INFO - 📤 GET /health - 200 - 4.85ms
```

---

## 2. Frontend Terminal (Next.js API Proxy)

### ⚠️ IMPORTANT

**Les `console.log` dans le navigateur ne sont PAS visibles dans le terminal.**

Pour voir les logs frontend dans le terminal, utilisez un **API Proxy Route**:

### 2.1 Créer le proxy route

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

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const endpoint = '/' + path.join('/');
  
  console.log(`${formatTimestamp()} 📡 [Frontend->API] POST ${endpoint}`);
  
  try {
    let body = null;
    try { body = await request.json(); } catch {}
    
    const response = await fetch(`${BACKEND_URL}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await response.json();
    
    console.log(`${formatTimestamp()} ✅ [Frontend->API] POST ${endpoint} - ${response.status}`);
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error(`${formatTimestamp()} ❌ [Frontend->API] POST ${endpoint} - Error:`, error);
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 503 });
  }
}
```

### 2.2 Utilisation dans les composants

```typescript
// ❌ Direct (pas de logs terminal)
const response = await fetch('http://localhost:8000/api/users');

// ✅ Via proxy (logs dans terminal frontend)
const response = await fetch('/api/proxy/api/users');
```

### 2.3 Résultat dans le terminal frontend

```
2026-02-08 11:40:24.400 📡 [Frontend->API] GET /api/users
2026-02-08 11:40:24.411 ✅ [Frontend->API] GET /api/users - 200
```

---

## 3. Frontend Browser (Console DevTools)

### 3.1 Utilitaire de logging

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

### 3.2 Utilisation

```typescript
import { logger } from '@/src/utils/logger';

logger.info('Data loaded', { component: 'UserTable', data: { count: 10 } });
logger.error('Failed to fetch', { component: 'API' });
```

### 3.3 Logs dans les hooks

```typescript
useEffect(() => {
  console.log('🔄 [UserTable] Loading data...');
  
  fetchData()
    .then(data => console.log('✅ [UserTable] Loaded:', data.length))
    .catch(err => console.error('❌ [UserTable] Error:', err));
}, []);
```

---

## 4. Database (SQLite/SQLAlchemy)

### 4.1 Logs des opérations DB

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

### 4.2 Logs SQL avec SQLAlchemy (optionnel)

```python
import logging

# Activer les logs SQL
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Ou via create_engine
engine = create_engine(DATABASE_URL, echo=True)
```

---

## 5. Conventions

### 5.1 Emojis standards

| Emoji | Usage |
|-------|-------|
| 📥 | Requête entrante |
| 📤 | Réponse sortante |
| 📡 | Appel API |
| ✅ | Succès |
| ❌ | Erreur |
| ⚠️ | Warning |
| 🔄 | Loading/Processing |
| 🗄️ | Database |
| 🚀 | Startup |
| 📌 | Event métier |

### 5.2 Préfixes

```
[ComponentName] Message
[API] Message
[DB] Message
[Auth] Message
```

### 5.3 Niveaux de log

| Niveau | Usage |
|--------|-------|
| `DEBUG` | Détails techniques, variables |
| `INFO` | Flux normal, événements métier |
| `WARNING` | Situations anormales mais gérées |
| `ERROR` | Erreurs nécessitant attention |

### 5.4 Ne jamais logger

- Mots de passe ou tokens
- Données personnelles sensibles
- Numéros de carte bancaire

---

## 6. Exemple de flux complet

```
# Utilisateur clique sur "Créer"

[Terminal Frontend]
2026-02-08 11:40:24.400 📡 [Frontend->API] POST /api/users
2026-02-08 11:40:24.450 ✅ [Frontend->API] POST /api/users - 201

[Terminal Backend]
2026-02-08 11:40:24,410 - app.api.requests - INFO - 📥 POST /api/users
2026-02-08 11:40:24,420 - app.database - INFO - 🗄️ INSERT users
2026-02-08 11:40:24,430 - app - INFO - 📌 [CREATED] User#123
2026-02-08 11:40:24,440 - app.api.requests - INFO - 📤 POST /api/users - 201 - 30.00ms

[Browser Console]
📘 [UserForm] Form submitted
✅ [UserForm] User created successfully
```

---

## 7. Configuration par environnement

### Backend (.env)

```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

### Frontend (.env.local)

```bash
BACKEND_URL=http://localhost:8000
```

---

*Ce template est réutilisable pour tout projet fullstack Python/FastAPI + Next.js/React.*
