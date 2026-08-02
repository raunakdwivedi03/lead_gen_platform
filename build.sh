#!/usr/bin/env bash
# Build script for Render deployment
set -e

# Force Playwright to install browser binaries into python packages folder
export PLAYWRIGHT_BROWSERS_PATH=0

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installing Playwright Chromium..."
python -m playwright install chromium

echo "Build complete!"
