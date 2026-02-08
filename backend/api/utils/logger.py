"""
Logging configuration for IBKR Portfolio Tracker Backend

Based on: docs/workflow/LOGGING_SETUP.md
"""

import logging
import sys
import os

# Get log level from environment
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Configure root logger
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Create application logger
logger = logging.getLogger("ibkr_tracker")


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name, prefixed with ibkr_tracker."""
    return logging.getLogger(f"ibkr_tracker.{name}")


# Convenience loggers for different modules
api_logger = get_logger("api")
db_logger = get_logger("database")
flex_logger = get_logger("flex")
pipeline_logger = get_logger("pipeline")


def log_event(event_type: str, entity: str, entity_id: int = None, details: dict = None):
    """Log a business event with consistent formatting."""
    id_str = f"#{entity_id}" if entity_id else ""
    details_str = f" - {details}" if details else ""
    logger.info(f"📌 [{event_type}] {entity}{id_str}{details_str}")
