# Troubleshooting Guide

## Common Issues and Solutions

### ModuleNotFoundError: No module named 'marnow'

**Problem**: When running `python3 tools/workflow.py`, you get an error that the `marnow` module cannot be found.

**Solution**: The workflow script now automatically adds the project root to the Python path. If you still see this error:
- Make sure you're running from the project root directory
- Check that `marnow/__init__.py` exists (it should be empty)

### Database Path Issues

**Problem**: Database operations fail with path errors like `/app/marnow.db` not found.

**Solution**: The workflow script now automatically sets `MARNOW_DB` environment variable to `./marnow.db` (local path). 

If you need to set it manually:
```bash
export MARNOW_DB=./marnow.db
python3 tools/workflow.py
```

Or for Docker:
```bash
export MARNOW_DB=/app/marnow.db
```

### Playwright Browser Not Found

**Problem**: Scraping fails with "Browser not found" errors.

**Solution**:
```bash
source .venv/bin/activate
python -m playwright install chromium
```

### Permission Errors

**Problem**: Cannot write to database or files.

**Solution**:
- Check file permissions: `ls -la marnow.db`
- Make sure you have write access to the project directory
- If using Docker, check volume mount permissions

### Import Errors in Virtual Environment

**Problem**: Packages not found even after installation.

**Solution**:
1. Make sure virtual environment is activated:
   ```bash
   source .venv/bin/activate
   which python  # Should show .venv/bin/python
   ```

2. Reinstall packages:
   ```bash
   uv pip install -r requirements.txt
   ```

### JD Files Not Being Ingested

**Problem**: JD files exist but ingestion shows "0 ingested".

**Solution**:
- Check if files already exist in database (they're skipped if hash matches)
- Verify JD files are in `app/data/jds/` directory
- Check file permissions: `ls -la app/data/jds/*.txt`

### Workflow Steps Failing

**Problem**: Individual steps fail with unclear errors.

**Solution**:
- Run steps individually to isolate the issue:
  ```bash
  # Step 1 only
  python tools/jobscraper/main.py
  
  # Step 2 only
  python tools/make_jds_from_jobs.py --limit 2
  
  # Step 3 only
  python -m marnow.cli initdb
  python -c "from marnow.ingest import ensure_db, ingest_jd; ensure_db(); ingest_jd('app/data/jds/test.txt')"
  ```

### Database Locked Errors

**Problem**: SQLite database is locked.

**Solution**:
- Close any other processes using the database
- Check for stale lock files: `ls -la marnow.db*`
- Restart the process

### Path Resolution Issues

**Problem**: Scripts can't find files (jobs.csv, JD files, etc.)

**Solution**:
- Always run scripts from the project root directory
- Use absolute paths if needed
- Check that `BASE_DIR` is resolving correctly

## Getting Help

If you encounter other issues:

1. Check the error message carefully
2. Verify all dependencies are installed
3. Ensure you're in the virtual environment
4. Try running steps individually
5. Check file permissions and paths

## Verification Checklist

Before reporting issues, verify:

- [ ] Virtual environment is activated
- [ ] All packages installed: `uv pip list`
- [ ] Playwright browsers installed: `python -m playwright install chromium`
- [ ] Running from project root directory
- [ ] Database path is correct: `echo $MARNOW_DB` (or check workflow.py sets it)
- [ ] File permissions are correct
- [ ] Python version is 3.8+: `python --version`
