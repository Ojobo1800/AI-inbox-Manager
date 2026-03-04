@echo off
REM Setup script for new developers (Windows)

echo Setting up development environment...

REM Check Python version
echo Checking Python version...
python --version

REM Create virtual environment
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
) else (
    echo Virtual environment already exists.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Install package in development mode
echo Installing package in development mode...
pip install -e .[dev]

REM Create .env if it doesn't exist
if not exist ".env" (
    echo Creating .env from template...
    copy .env.example .env
    echo Please edit .env with your configuration.
) else (
    echo .env already exists.
)

REM Create tmp directory
echo Creating tmp directory...
if not exist "tmp\" mkdir tmp

REM Run tests to verify setup
echo.
echo Running tests to verify setup...
pytest

echo.
echo Setup complete!
echo Activate the virtual environment with: venv\Scripts\activate.bat
