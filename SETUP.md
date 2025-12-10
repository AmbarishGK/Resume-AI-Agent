# Setup Instructions

## Quick Start with UV

This project uses [uv](https://github.com/astral-sh/uv) for fast Python package management.

### 1. Install UV (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or via pip:
```bash
pip install uv
```

### 2. Create Virtual Environment

```bash
# Create venv with uv
uv venv

# Activate it
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows
```

### 3. Install Dependencies

```bash
# Install all packages from requirements.txt
uv pip install -r requirements.txt

# Install Playwright browsers
python -m playwright install chromium
```

**Or use the quick setup script:**
```bash
./activate.sh  # Creates venv and installs everything automatically
```

### 4. Verify Installation

```bash
# Check Python version
python --version

# Verify packages
python -c "import playwright, yaml, requests, bs4, typer; print('All packages installed!')"
```

## Alternative: Standard pip/venv

If you prefer standard Python tooling:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Running the Workflow

Once setup is complete:

```bash
# Activate venv (if not already active)
source .venv/bin/activate

# Run the complete workflow
python tools/workflow.py

# Or run individual steps
python tools/jobscraper/main.py
python tools/make_jds_from_jobs.py
python -m marnow.cli initdb
```

## Troubleshooting

### Playwright browser not found
```bash
playwright install chromium
```

### Permission errors
Make sure you're in the virtual environment:
```bash
which python  # Should show .venv/bin/python
```

### Database path issues
Set environment variable for local development:
```bash
export MARNOW_DB=./marnow.db
```
