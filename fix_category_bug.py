#!/usr/bin/env python3
import re

file_path = '/home/ubuntu/trading/scripts/percentage_based_allocation.py'

with open(file_path, 'r') as f:
    content = f.read()

# Fix line 212 - exclude 'category' from pass-through to prevent overwriting
old_line = "                **{k: v for k, v in stock.items() if k not in ['ticker', 'score', 'rs_rating']}"
new_line = "                **{k: v for k, v in stock.items() if k not in ['ticker', 'score', 'rs_rating', 'category']}"

if old_line in content:
    content = content.replace(old_line, new_line)

    with open(file_path, 'w') as f:
        f.write(content)

    print('✅ Fixed percentage_based_allocation.py')
    print('   Excluded "category" from pass-through dict')
    print('   This prevents large_caps/mid_caps/micro_caps from overwriting Large-cap/Mid-cap/Microcap')
else:
    print('❌ Original line not found - may already be fixed')
