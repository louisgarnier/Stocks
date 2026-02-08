"""Routes module for IBKR Portfolio Tracker API."""

from backend.api.routes.flex import router as flex_router
from backend.api.routes.transactions import router as transactions_router
from backend.api.routes.splits import router as splits_router

__all__ = ["flex_router", "transactions_router", "splits_router"]
