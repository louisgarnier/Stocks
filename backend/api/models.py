"""
Pydantic models for API requests and responses.

⚠️ Before making changes, read: ../../docs/workflow/BEST_PRACTICES.md
Always check with the user before modifying this file.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# Example models - customize for your project

class ExampleBase(BaseModel):
    """Base model for example entity."""
    name: str
    description: Optional[str] = None


class ExampleCreate(ExampleBase):
    """Model for creating an example."""
    pass


class ExampleUpdate(BaseModel):
    """Model for updating an example."""
    name: Optional[str] = None
    description: Optional[str] = None


class ExampleResponse(ExampleBase):
    """Model for example response."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True




