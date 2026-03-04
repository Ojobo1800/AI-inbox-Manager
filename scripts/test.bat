@echo off
REM Run all tests with coverage (Windows)

echo Running tests with coverage...
pytest --cov=execution --cov=services --cov-report=html --cov-report=term-missing -v

echo.
echo Coverage report generated in htmlcov\index.html
echo Done!
