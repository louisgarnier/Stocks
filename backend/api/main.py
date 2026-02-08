"""
FastAPI main application.

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
from backend.database.connection import init_database

# Import routes (create these as needed)
# from backend.api.routes import example

# Create FastAPI app
app = FastAPI(
    title="API Template",
    description="Template FastAPI application",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers (uncomment when routes are created)
# app.include_router(example.router, prefix="/api", tags=["example"])


@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    init_database()


@app.get("/")
async def root():
    """Root endpoint - health check."""
    return {"message": "API is running", "status": "ok"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}




