#!/bin/bash
echo "🚀 Installing dependencies..."
pip install -r requirements.txt

echo "🐳 Starting GHCR Proxy..."
python proxy.py
