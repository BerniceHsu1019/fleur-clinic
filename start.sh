#!/bin/bash
cd "$(dirname "$0")"
pip3 install -r requirements.txt -q
python3 seed.py
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
