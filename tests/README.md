# Tests

This folder contains all test files for the project, ensuring code quality and correctness.

## Intended Contents

- **Unit tests**: Test individual functions and methods in isolation
- **Integration tests**: Test interaction between different modules
- **End-to-end tests**: Test complete workflows and use cases
- **Test fixtures**: Sample data and mock objects for testing
- **Test utilities**: Helper functions for testing

## Running Tests

Use pytest to run tests:
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_specific.py

# Run with coverage
pytest --cov=DataStandards
```

## Guidelines

- Mirror the structure of the `DataStandards/` directory
- Name test files with `test_` prefix
- Write clear, focused test cases
- Aim for high test coverage
- Use meaningful test names that describe what is being tested
