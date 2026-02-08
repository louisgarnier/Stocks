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
            
            cursor.execute("SELECT COUNT(*) FROM positions")
            position_count = cursor.fetchone()[0]
            
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




