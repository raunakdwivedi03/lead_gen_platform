#!/usr/bin/env bash
# Build script for Render deployment
set -e

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installing Playwright Chromium with system dependencies..."
playwright install --with-deps chromium

echo "Build complete!"
