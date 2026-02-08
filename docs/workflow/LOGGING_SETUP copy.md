# Logging Setup Guide

Template pour configurer les logs dans un projet fullstack (Backend Python/FastAPI + Frontend Next.js/React + Database PostgreSQL).

---

## 1. Backend (Python/FastAPI)

### 1.1 Configuration de base avec `logging`

```python
# backend/api/main.py ou backend/config/logging.py
import logging
import sys

# Configuration du logger principal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Logger spécifique pour l'application
logger = logging.getLogger(__name__)
```

### 1.2 Logs par module/service

```python
# Dans chaque fichier de service
import logging

logger = logging.getLogger(__name__)

def my_function():
    logger.info("Starting function")
    logger.debug("Debug details: %s", some_variable)
    logger.warning("Warning message")
    logger.error("Error occurred: %s", error_message)
```

### 1.3 Middleware de logging pour les requêtes API

```python
# backend/api/middleware/logging_middleware.py
import time
import logging
from fastapi import Request

logger = logging.getLogger("api.requests")

async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log de la requête entrante
    logger.info(f"📥 {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    # Log de la réponse
    process_time = (time.time() - start_time) * 1000
    logger.info(f"📤 {request.method} {request.url.path} - {response.status_code} - {process_time:.2f}ms")
    
    return response

# Dans main.py
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

app = FastAPI()
app.add_middleware(BaseHTTPMiddleware, dispatch=log_requests)
```

### 1.4 Logs avec préfixes pour faciliter le filtrage

```python
# Convention de préfixes
logger.info("[BilanService] Calculating bilan for property %d", property_id)
logger.info("[TransactionService] Created transaction: %s", transaction_id)
logger.error("[AuthService] Authentication failed for user: %s", username)

# Ou avec emojis pour une meilleure lisibilité
logger.info("📊 [BilanService] Calculating bilan for property %d", property_id)
logger.info("💰 [TransactionService] Created transaction: %s", transaction_id)
logger.error("🔐 [AuthService] Authentication failed for user: %s", username)
```

### 1.5 Logs structurés (JSON) pour production

```python
import json
import logging

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)

# Utilisation
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
```

---

## 2. Frontend (Next.js/React)

### 2.1 Console logs avec préfixes

```typescript
// Convention de logs frontend
console.log('[ComponentName] Message');
console.log('[API] Fetching data from /api/endpoint');
console.error('[Error] Failed to load data:', error);

// Avec emojis pour une meilleure lisibilité
console.log('🔄 [BilanTable] Loading data...');
console.log('✅ [BilanTable] Data loaded successfully');
console.error('❌ [BilanTable] Error loading data:', error);
console.warn('⚠️ [BilanTable] Warning: missing property');
```

### 2.2 Utilitaire de logging centralisé

```typescript
// frontend/src/utils/logger.ts
const isDev = process.env.NODE_ENV === 'development';

type LogLevel = 'info' | 'warn' | 'error' | 'debug';

interface LogOptions {
  component?: string;
  data?: any;
}

const log = (level: LogLevel, message: string, options?: LogOptions) => {
  if (!isDev && level === 'debug') return;
  
  const prefix = options?.component ? `[${options.component}]` : '';
  const emoji = {
    info: '📘',
    warn: '⚠️',
    error: '❌',
    debug: '🔍'
  }[level];
  
  const logFn = {
    info: console.log,
    warn: console.warn,
    error: console.error,
    debug: console.debug
  }[level];
  
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

// Utilisation
import { logger } from '@/utils/logger';

logger.info('Data loaded', { component: 'BilanTable', data: { count: 10 } });
logger.error('Failed to fetch', { component: 'API' });
```

### 2.3 Logs dans les appels API

```typescript
// frontend/src/api/client.ts
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function apiCall<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
  console.log(`📡 [API] ${options?.method || 'GET'} ${endpoint}`);
  
  try {
    const response = await fetch(url, options);
    
    if (!response.ok) {
      console.error(`❌ [API] ${endpoint} - ${response.status} ${response.statusText}`);
      throw new Error(`API Error: ${response.status}`);
    }
    
    const data = await response.json();
    console.log(`✅ [API] ${endpoint} - Success`);
    
    return data;
  } catch (error) {
    console.error(`❌ [API] ${endpoint} - Error:`, error);
    throw error;
  }
}
```

### 2.4 Logs dans les hooks/effects

```typescript
// Dans un composant React
useEffect(() => {
  console.log('[BilanTable] useEffect triggered', { 
    propertyId: activeProperty?.id, 
    refreshKey 
  });
  
  const loadData = async () => {
    console.log('[BilanTable] Loading data...');
    try {
      const data = await fetchData();
      console.log('[BilanTable] Data loaded:', { count: data.length });
    } catch (error) {
      console.error('[BilanTable] Error loading data:', error);
    }
  };
  
  loadData();
}, [activeProperty?.id, refreshKey]);
```

---

## 3. Database (SQLAlchemy/PostgreSQL)

### 3.1 Activer les logs SQL

```python
# backend/database.py ou config
import logging

# Logger pour SQLAlchemy
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)  # Logs des requêtes
logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)   # Logs du pool de connexions

# Ou via create_engine
from sqlalchemy import create_engine

engine = create_engine(
    DATABASE_URL,
    echo=True,  # Active les logs SQL
    echo_pool=True  # Active les logs du pool
)
```

### 3.2 Logs personnalisés pour les opérations DB

```python
# backend/api/services/base_service.py
import logging

logger = logging.getLogger("database")

class BaseService:
    def log_query(self, operation: str, table: str, filters: dict = None):
        logger.info(f"🗄️ [{operation}] {table} - Filters: {filters}")
    
    def log_result(self, operation: str, table: str, count: int):
        logger.info(f"🗄️ [{operation}] {table} - Result: {count} rows")

# Utilisation
class TransactionService(BaseService):
    def get_transactions(self, property_id: int):
        self.log_query("SELECT", "transactions", {"property_id": property_id})
        results = db.query(Transaction).filter_by(property_id=property_id).all()
        self.log_result("SELECT", "transactions", len(results))
        return results
```

---

## 4. Logs des événements métier

### 4.1 Backend - Events logger

```python
# backend/api/utils/event_logger.py
import logging
from datetime import datetime

event_logger = logging.getLogger("events")

def log_event(event_type: str, entity: str, entity_id: int, details: dict = None):
    """Log un événement métier"""
    event_logger.info(
        f"📌 [{event_type}] {entity}#{entity_id} - {details or {}}"
    )

# Utilisation
log_event("CREATED", "Transaction", transaction.id, {"amount": 1500})
log_event("UPDATED", "Property", property.id, {"field": "name"})
log_event("DELETED", "LoanPayment", payment.id)
```

### 4.2 Frontend - Events dispatcher

```typescript
// frontend/src/utils/events.ts
export const dispatchEvent = (eventName: string, detail?: any) => {
  console.log(`🎯 [Event] Dispatching: ${eventName}`, detail);
  window.dispatchEvent(new CustomEvent(eventName, { detail }));
};

// Utilisation
dispatchEvent('transactionCreated', { id: 123 });
dispatchEvent('loanConfigUpdated');
```

---

## 5. Bonnes pratiques

### 5.1 Niveaux de log

| Niveau | Usage |
|--------|-------|
| `DEBUG` | Détails techniques, variables, états internes |
| `INFO` | Flux normal, actions utilisateur, événements métier |
| `WARNING` | Situations anormales mais gérées |
| `ERROR` | Erreurs qui nécessitent une attention |
| `CRITICAL` | Erreurs fatales, système down |

### 5.2 Convention de préfixes

```
[ServiceName] Message
[ComponentName] Message
[API] Message
[DB] Message
[Auth] Message
[Event] Message
```

### 5.3 Emojis recommandés

| Emoji | Usage |
|-------|-------|
| 📥 | Requête entrante |
| 📤 | Réponse sortante |
| ✅ | Succès |
| ❌ | Erreur |
| ⚠️ | Warning |
| 🔄 | Chargement/Processing |
| 📊 | Données/Calculs |
| 💰 | Transactions financières |
| 🗄️ | Database |
| 🔐 | Auth/Security |
| 📌 | Event |
| 🎯 | Action utilisateur |

### 5.4 Ne pas logger

- Mots de passe ou tokens
- Données personnelles sensibles
- Données de carte bancaire
- Informations médicales

### 5.5 Filtrage des logs en développement

```bash
# Backend - filtrer par niveau
LOG_LEVEL=DEBUG python -m uvicorn main:app

# Backend - filtrer par module
python -m uvicorn main:app 2>&1 | grep "\[BilanService\]"

# Frontend - filtrer dans la console du navigateur
# Utiliser les filtres de la console DevTools
```

---

## 6. Configuration par environnement

### 6.1 Backend

```python
# backend/config.py
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "text")  # "text" ou "json"

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' if LOG_FORMAT == "text" else None
)
```

### 6.2 Frontend

```typescript
// frontend/src/config.ts
export const config = {
  logLevel: process.env.NEXT_PUBLIC_LOG_LEVEL || 'info',
  enableDebugLogs: process.env.NODE_ENV === 'development',
};
```

---

## 7. Exemple complet d'un flux

```
# Utilisateur clique sur "Créer transaction"

[Frontend]
🎯 [TransactionForm] User clicked submit
📡 [API] POST /api/transactions
✅ [API] /api/transactions - Success
🎯 [Event] Dispatching: transactionCreated

[Backend]
📥 POST /api/transactions
📊 [TransactionService] Creating transaction for property 25
🗄️ [SELECT] properties - Filters: {'id': 25}
🗄️ [INSERT] transactions - Data: {'amount': 1500, 'category': 'Loyer'}
📌 [CREATED] Transaction#456 - {'amount': 1500}
📤 POST /api/transactions - 201 - 45.23ms

[Frontend]
🔄 [BilanTable] Event transactionCreated received
📡 [API] GET /api/bilan/calculate?property_id=25
✅ [API] /api/bilan/calculate - Success
✅ [BilanTable] Data refreshed
```

---

*Ce template peut être adapté selon les besoins spécifiques du projet.*
