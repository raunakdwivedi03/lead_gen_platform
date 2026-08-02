#!/usr/bin/env bash
# Build script for Render deployment
set -e

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installing Playwright Chromium..."
playwright install chromium

echo "Build complete!"
