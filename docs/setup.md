# Setup notes

This page mirrors `SETUP.md` (kept in the repo root).

## Quick start (uv)

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
python -m playwright install chromium
```

## Alternative (venv)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```
