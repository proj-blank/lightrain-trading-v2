#!/bin/bash
# Fixed EOD report script for AWS

cd /home/ubuntu/trading

# Set environment
export PYTHONPATH=/home/ubuntu/trading
export TZ='Asia/Kolkata'

# Run EOD report
python3 send_eod_report.py >> logs/eod_report.log 2>&1
