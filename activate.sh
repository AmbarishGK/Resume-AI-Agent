#!/bin/bash
# Quick activation script for the uv virtual environment

if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Creating it..."
    uv venv
    source .venv/bin/activate
    uv pip install -r requirements.txt
    python -m playwright install chromium
    echo "✓ Virtual environment created and dependencies installed!"
else
    source .venv/bin/activate
    echo "✓ Virtual environment activated!"
fi
