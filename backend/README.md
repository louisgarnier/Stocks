# Backend API

FastAPI backend application.

⚠️ **Before making changes, read: `docs/workflow/BEST_PRACTICES.md`**

## Setup

1. Create virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Initialize database:
```bash
# Database will be auto-created on first run
# Or run: python3 -c "from backend.database.connection import init_database; init_database()"
```

## Running

```bash
# Development server
python3 -m uvicorn backend.api.main:app --reload --port 8000

# Production server
python3 -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
```

## API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend --cov-report=html
```

## Project Structure

```
backend/
├── api/              # API routes and models
│   ├── main.py      # FastAPI application
│   ├── models.py    # Pydantic models
│   └── routes/      # API route handlers
├── database/         # Database connection and schema
│   ├── connection.py # Database connection
│   └── schema.sql    # Database schema
└── tests/            # Test files
```

## Best Practices

- Always check `docs/workflow/BEST_PRACTICES.md` before making changes
- Propose tests after developing new code
- Get user approval before committing changes




