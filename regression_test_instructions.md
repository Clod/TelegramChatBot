# Regression Test Instructions for Telegram Bot Application

This document provides detailed instructions for running the comprehensive regression tests for the Telegram bot application.

## Prerequisites

Before running the tests, ensure you have the following:

1. Python 3.7 or higher installed
2. All required dependencies installed (same as those required by app.py)
3. Access to the application code (app.py)

## Setup

1. **Install Required Dependencies**

   ```bash
   pip install flask telebot python-dotenv google-auth requests
   pip install unittest-mock pytest pytest-cov
   ```

2. **Place Test Files**

   Ensure the following files are in the same directory:
   - app.py (the main application file)
   - test_app_regression.py (the regression test file)

3. **Environment Setup**

   The tests are designed to use mock environment variables, so you don't need to set up a .env file for testing.

## Running the Tests

### Method 1: Using unittest directly

1. Open a terminal or command prompt
2. Navigate to the directory containing the test files
3. Run the following command:

   ```bash
   python -m unittest test_app_regression.py
   ```

### Method 2: Using pytest (recommended for detailed reports)

1. Open a terminal or command prompt
2. Navigate to the directory containing the test files
3. Run the following command:

   ```bash
   pytest test_app_regression.py -v
   ```

   For a more detailed report with test coverage:

   ```bash
   pytest test_app_regression.py -v --cov=app
   ```

## Test Coverage Report

To generate a detailed HTML coverage report:

```bash
pytest test_app_regression.py --cov=app --cov-report=html
```

This will create a directory named `htmlcov` containing an HTML report. Open `htmlcov/index.html` in a web browser to view the coverage report.

## Understanding Test Results

The test output will show:

1. The number of tests run
2. The number of tests passed/failed
3. Any errors or failures with detailed information
4. The time taken to run the tests

A successful test run will show all tests passing with no failures or errors.

## Troubleshooting Common Issues

### ImportError

If you see an ImportError, ensure:
- All required dependencies are installed
- The app.py file is in the same directory as the test file
- The import statements in the test file match the structure of app.py

### AttributeError

If you see an AttributeError, it might indicate:
- The app.py file has been modified and some functions or variables have changed
- The mocking in the tests doesn't match the actual implementation

### Database Errors

The tests use a temporary SQLite database, so you shouldn't encounter issues with the production database. If you see database errors:
- Ensure SQLite is properly installed
- Check if the app.py file has database operations that aren't properly mocked in the tests

## Extending the Tests

To add new tests:

1. Open test_app_regression.py
2. Add new test methods to the AppRegressionTest class
3. Ensure each test method name starts with "test_"
4. Run the tests to verify your additions

## Continuous Integration

These tests can be integrated into a CI/CD pipeline. For GitHub Actions, create a workflow file (.github/workflows/test.yml) with:

```yaml
name: Run Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install flask telebot python-dotenv google-auth requests
        pip install pytest pytest-cov
    - name: Test with pytest
      run: |
        pytest test_app_regression.py -v --cov=app
```

## Contact

If you encounter any issues with the tests or have questions, please contact the development team.
