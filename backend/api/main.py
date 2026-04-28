"""
FastAPI main application - IBKR Portfolio Tracker

⚠️ Before making changes, read: ../../docs/workflow/BEST_PRACTICES.md
Always check with the user before modifying this file.
"""

import sys
from pathlib import Path

# Add project root to path for shared imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from backend.database.connection import init_database, get_db_connection, get_db_path
from backend.api.middleware.logging_middleware import log_requests
from backend.api.utils.logger import logger, api_logger
from backend.api.routes.transactions import router as transactions_router
from backend.api.routes.corporate_actions import router as corporate_actions_router
from backend.api.routes.updated_transactions import router as updated_transactions_router
from backend.api.routes.positions import router as positions_router
from backend.api.routes.sync import router as sync_router
from backend.api.routes.universe import router as universe_router
from backend.api.routes.market_data import router as market_data_router
from backend.api.routes.indicators import router as indicators_router

# Create FastAPI app
app = FastAPI(
    title="IBKR Portfolio Tracker API",
    description="API for tracking IBKR portfolio holdings and transactions",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
app.add_middleware(BaseHTTPMiddleware, dispatch=log_requests)

# Include routers
app.include_router(transactions_router)
app.include_router(corporate_actions_router)
app.include_router(updated_transactions_router, prefix="/api/updated-transactions", tags=["updated-transactions"])
app.include_router(positions_router)
app.include_router(sync_router)
app.include_router(universe_router)
app.include_router(market_data_router)
app.include_router(indicators_router)


@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    logger.info("🚀 Starting IBKR Portfolio Tracker API")
    init_database()
    logger.info("✅ Application startup complete")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "IBKR Portfolio Tracker API",
        "status": "ok",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Health check endpoint with database status."""
    db_path = get_db_path()
    db_exists = db_path.exists()
    
    # Check database connection
    db_status = "disconnected"
    transaction_count = 0
    position_count = 0
    
    if db_exists:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get counts
            cursor.execute("SELECT COUNT(*) FROM transactions")
            transaction_count = cursor.fetchone()[0]
            
            # positions table no longer exists
            position_count = 0
            
            conn.close()
            db_status = "connected"
        except Exception as e:
            db_status = f"error: {str(e)}"
    
    return {
        "status": "ok",
        "database": db_status,
        "database_path": str(db_path),
        "transactions": transaction_count,
        "positions": position_count
    }




