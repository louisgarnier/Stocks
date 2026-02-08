"""
Example API routes.

⚠️ Before making changes, read: ../../../docs/workflow/BEST_PRACTICES.md
Always check with the user before modifying this file.

This is a template route file. Customize it for your needs or delete it.
"""

from fastapi import APIRouter, HTTPException
from typing import List
from backend.api.models import ExampleCreate, ExampleUpdate, ExampleResponse

router = APIRouter()


@router.get("/examples", response_model=List[ExampleResponse])
async def get_examples():
    """
    Get all examples.
    
    Returns:
        List of all examples
    """
    # TODO: Implement database query
    return []


@router.get("/examples/{example_id}", response_model=ExampleResponse)
async def get_example(example_id: int):
    """
    Get a single example by ID.
    
    Args:
        example_id: The ID of the example
        
    Returns:
        The example if found
        
    Raises:
        HTTPException: If example not found
    """
    # TODO: Implement database query
    raise HTTPException(status_code=404, detail="Example not found")


@router.post("/examples", response_model=ExampleResponse, status_code=201)
async def create_example(example: ExampleCreate):
    """
    Create a new example.
    
    Args:
        example: Example creation data
        
    Returns:
        Created example
    """
    # TODO: Implement database insert
    raise HTTPException(status_code=501, detail="Not implemented")


@router.put("/examples/{example_id}", response_model=ExampleResponse)
async def update_example(example_id: int, example: ExampleUpdate):
    """
    Update an example.
    
    Args:
        example_id: The ID of the example
        example: Update data
        
    Returns:
        Updated example
        
    Raises:
        HTTPException: If example not found
    """
    # TODO: Implement database update
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/examples/{example_id}", status_code=204)
async def delete_example(example_id: int):
    """
    Delete an example.
    
    Args:
        example_id: The ID of the example
        
    Raises:
        HTTPException: If example not found
    """
    # TODO: Implement database delete
    raise HTTPException(status_code=501, detail="Not implemented")




