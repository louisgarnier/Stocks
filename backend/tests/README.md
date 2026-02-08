# Backend Tests

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_api.py

# Run with coverage
pytest --cov=backend --cov-report=html
```

## Test Structure

- `test_api.py` - API endpoint tests
- `test_database.py` - Database tests
- `test_models.py` - Model validation tests

## Best Practices

- Write tests for all new code
- Tests should be independent and isolated
- Use fixtures for common setup
- Mock external dependencies

---

**Remember**: Always propose tests after developing new code (see `docs/workflow/BEST_PRACTICES.md`)




