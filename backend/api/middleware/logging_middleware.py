"""
Request/Response logging middleware for FastAPI

Based on: docs/workflow/LOGGING_SETUP.md
"""

import time
import logging
from fastapi import Request

logger = logging.getLogger("ibkr_tracker.api.requests")


async def log_requests(request: Request, call_next):
    """Log incoming requests and outgoing responses with timing."""
    start_time = time.time()
    
    # Log incoming request
    logger.info(f"📥 {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    # Log response with timing
    process_time = (time.time() - start_time) * 1000
    logger.info(f"📤 {request.method} {request.url.path} - {response.status_code} - {process_time:.2f}ms")
    
    return response
