#!/bin/bash
# Helper script to run stocks screening with correct env vars
cd ~/trading
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=lightrain
export DB_USER=lightrain_user
export DB_PASSWORD='LightRain2025@Secure'

python3 stocks_screening.py
