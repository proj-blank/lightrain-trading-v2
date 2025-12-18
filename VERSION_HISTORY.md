# LightRain Trading System - Version History

## v5 - 2025-12-11 17:00 IST (CURRENT - PRODUCTION)
**Changes:**
- Added 5% profit target check to thunder_pipeline.py
- Function `check_and_exit_profitable_positions()` runs at 10:30 AM before entering new positions
- Checks all ACTIVE THUNDER positions for 5%+ profit and exits them
- Frees up capital before entering new THUNDER positions
- Added market hours check (9:15 AM - 3:30 PM IST)
- Profit exits run even when market closed (uses previous day's closing prices)
- New entries only allowed during market hours

**THUNDER v3 Features:**
- Profit check runs FIRST in pipeline (before earnings scan)
- Updates both `thunder_positions` AND `positions` tables on exit
- Sends Telegram alert with exit details
- Solves weekend holding issue (e.g., WIPRO earnings Wed, would exit Sat but market closed)

**Test Run Results (Dec 11, 2025 - 4:56 PM):**
- Market: Closed (profit exit ran successfully)
- WIPRO.NS: Exited with 5.36% profit (₹3,413.62 PnL)
  - Entry: Nov 20, ₹246.07
  - Exit: Dec 11, ₹259.25
- Exit reason: "Profit target hit (5.4% >= 5.0%)"
- Both tables updated: ✅ VERIFIED
- Telegram alert sent: ✅ VERIFIED

**Active Scripts:**
- daily_trading_pg.py (v3) - ₹100k max per position
- swing_trading_pg.py (v4) - ₹70k max per position
- thunder_pipeline.py (v3) - Added 5% profit exit + market hours check
- scripts/percentage_based_allocation.py (v3) - ₹100k hard cap

**Backups:**
- thunder_pipeline_v3_20251211_profit_check.py (NEW)
- thunder_pipeline_v2_20251211_baseline.py (pre-profit check)
- daily_trading_pg_v3_20251211_final.py
- swing_trading_pg_v4_20251211_final.py

## v4 - 2025-12-11 13:00 IST
**Changes:**
- Cleaned up SWING duplicate positions (31 positions with ₹1.37M deployed → 0)
- Re-ran swing_trading_pg.py with fixed ₹100k allocation cap
- All SWING positions now under ₹70k limit (14% of ₹500k)
- Verified ₹100k hard cap is working for SWING strategy

**SWING Test Run Results:**
- Universe: 337 NSE stocks
- BUY Signals: 9 total (4 Large, 5 Mid, 0 Micro)
- Allocation Plan: 4 Large + 3 Mid (7 total positions)
- Actual Entries: 7 positions (4 Large + 3 Mid)
  - M&M.NS: ₹69,122 (Large)
  - BPCL.NS: ₹69,090 (Large)
  - BHARTIARTL.NS: ₹67,789 (Large)
  - EICHERMOT.NS: ₹65,520 (Large)
  - NYKAA.NS: ₹30,707 (Mid)
  - BIOCON.NS: ₹30,492 (Mid)
  - POLICYBZR.NS: ₹29,100 (Mid)
- Total Deployed: ₹361,820 / ₹491,738 available (74% utilization)
- All positions under ₹70k: ✅ VERIFIED

**Active Scripts:**
- daily_trading_pg.py (v3) - ₹100k max per position
- swing_trading_pg.py (v4) - ₹70k max per position
- scripts/percentage_based_allocation.py (v3) - ₹100k hard cap

**Backups:**
- daily_trading_pg_v3_20251211_final.py
- swing_trading_pg_v4_20251211_final.py
- swing_trading_pg_v1_20251211_baseline.py (pre-cleanup state)
- daily_trading_pg_v1_20251211.py

## v3 - 2025-12-11 12:40 IST
**Changes:**
- Fixed percentage_based_allocation.py: max_position_size from ₹150k → ₹100k (affects both DAILY and SWING)
- Fixed daily_trading_pg.py: Updated comments to reflect actual MAX_POSITION_PCT = 0.20 (₹100k max)
- Fixed line 576 print statement: "30% limit" → "20% limit (₹100k max)"
- Disabled daily_screening.py (8:55 AM) - now using full NSE universe (337 stocks) from stocks_screening.py
- Cleaned up duplicate position entries in database
- Reset capital_tracker to correct values

**Impact:**
- DAILY: Now enforces ₹100k max per position (was allowing ₹147k)
- SWING: Also benefits from ₹100k allocation cap (was using ₹150k in allocation)
- 337-stock NSE universe screening (vs previous 70 manual stocks)

**Position Sizing:**
- MAX_POSITION_PCT = 0.20 for DAILY (₹100k max per position)
- MAX_POSITION_PCT = 0.14 for SWING (₹70k max per position)
- Allocation module enforces ₹100k hard cap across both strategies

**Cron Changes:**
- REMOVED: 55 8 * * 1-5 daily_screening.py (was overwriting NSE universe with 70 stocks)
- ACTIVE: 30 8 * * 1-5 stocks_screening.py (337 stocks from Nifty 50 + Midcap 150 + Smallcap 250)

## v2 - 2025-12-11 10:50 IST
**Changes:**
- Fixed MAX_POSITION_PCT from 0.30 to 0.20 (₹100k max per position)
- Disabled daily_screening.py (8:55 AM) - using stocks_screening.py (8:30 AM) instead
- Now screens full NSE universe (337 stocks) instead of manual 70
- Fixed capital_tracker debit/credit logic

## v1 - 2025-12-11 09:43 IST
**Initial state before systematic version control**
- MAX_POSITION_PCT = 0.30 (WRONG - allowed ₹147k positions)
- MAX_DAILY_POSITIONS = 10
- MIN_COMBINED_SCORE = 60
- Used manual 70-stock screening

---

## Key Configuration Values (v5 - Current)

### Daily Trading (daily_trading_pg.py v3)
- ACCOUNT_SIZE = 500000
- MAX_DAILY_POSITIONS = 10
- MAX_POSITION_PCT = 0.20  (₹100k max per position)
- MIN_COMBINED_SCORE = 60
- MIN_RS_RATING = 60
- USE_ATR_SIZING = True
- MAX_HOLD_DAYS = 3

### Swing Trading (swing_trading_pg.py v4)
- ACCOUNT_SIZE = 500000
- MAX_SWING_POSITIONS = 13
- MAX_POSITION_PCT = 0.14  (₹70k max per position)
- MIN_COMBINED_SCORE = 60
- MIN_RS_RATING = 50
- MAX_HOLD_DAYS = 20

### THUNDER Trading (thunder_pipeline.py v3)
- Runs at: 10:30 AM IST (cron)
- Universe: LARGE_CAPS + MID_CAPS (20 stocks)
- Entry Window: 14-30 days before earnings
- Profit Target: 5% (exits automatically)
- Exit Logic: 2 days after earnings OR 5%+ profit (whichever comes first)
- Market Hours Check: 9:15 AM - 3:30 PM IST
- Position Updates: Both `thunder_positions` and `positions` tables

### Allocation Module (scripts/percentage_based_allocation.py v3)
- target_allocation = 60% Large / 20% Mid / 20% Micro
- min_position_size = 20000  (₹20K minimum)
- max_position_size = 100000  (₹100K maximum - HARD CAP)
- min_score = 60
- min_rs_rating = 50  (Note: daily_trading overrides this to 60)

---

## Testing Log (v5)

### THUNDER Test Run: 2025-12-11 16:56 IST (v3)
- **Market**: Closed (profit exit logic tested successfully)
- **Active Positions**: 4 → 3 (WIPRO exited)
- **Exit**: WIPRO.NS at ₹259.25 (5.36% profit, ₹3,413.62 PnL)
- **Profit Exit Logic**: ✅ Working correctly
- **Market Hours Check**: ✅ Detected market closed, skipped new entries
- **Database Sync**: ✅ Both `thunder_positions` and `positions` tables updated
- **Telegram Alert**: ✅ Sent successfully

### DAILY Test Run: 2025-12-11 12:24 IST (v3)
- **Universe**: 337 NSE stocks
- **BUY Signals**: 23 total (9 Large, 14 Mid, 0 Micro)
- **Entries**: 5 positions (3 Large + 2 Mid)
- **Total Deployed**: ₹481,918 / ₹490,162 (98% utilization)
- **All positions under ₹100k**: ✅

### SWING Test Run: 2025-12-11 12:58 IST (v4)
- **Universe**: 337 NSE stocks
- **BUY Signals**: 9 total (4 Large, 5 Mid, 0 Micro)
- **Entries**: 7 positions (4 Large + 3 Mid)
- **Total Deployed**: ₹361,820 / ₹491,738 (74% utilization)
- **All positions under ₹70k**: ✅

### Known Issues:
1. **No Micro-cap entries**: 0 out of 204 micro-caps passed RS filters for both strategies
   - DAILY: RS >= 60 filter too strict
   - SWING: RS >= 50 filter also too strict
   - Micro-cap budget (20%) redistributed to Large/Mid caps
   - Consider lowering RS threshold for micro-caps in future (e.g., RS >= 40)

---

## Rollback Instructions

### Restore v5 (Current - THUNDER profit check):
```bash
cd ~/trading
cp daily_trading_pg_v3_20251211_final.py daily_trading_pg.py
cp swing_trading_pg_v4_20251211_final.py swing_trading_pg.py
cp thunder_pipeline_v3_20251211_profit_check.py thunder_pipeline.py
```

### Rollback to v4 (Before THUNDER profit check):
```bash
cd ~/trading
cp daily_trading_pg_v3_20251211_final.py daily_trading_pg.py
cp swing_trading_pg_v4_20251211_final.py swing_trading_pg.py
cp thunder_pipeline_v2_20251211_baseline.py thunder_pipeline.py
```

### Rollback to v3 (DAILY working, SWING with duplicates):
```bash
cd ~/trading
cp daily_trading_pg_v3_20251211_final.py daily_trading_pg.py
cp swing_trading_pg_v1_20251211_baseline.py swing_trading_pg.py
```

---

**Last Updated**: 2025-12-11 17:00 IST
**Current Production Version**: v5
**Status**: ACTIVE - All strategies tested and verified ✅ (DAILY, SWING, THUNDER)

## v6 - 2025-12-17 22:00 IST (CRITICAL FIXES)

### CRITICAL BUG FIXES:

1. **Capital Calculation Bug** (db_connection.py)
   - OLD: get_available_cash() read from deprecated capital_tracker table
   - NEW: Calculates from positions + trades tables
   - Formula: (500K - Total Losses) - Deployed Capital
   - Impact: DAILY showed ₹-48K → now ₹441K available

2. **DAILY ACCOUNT_SIZE Bug** (daily_trading_pg.py line 55)
   - OLD: ACCOUNT_SIZE = get_available_cash("DAILY") → ₹264K
   - NEW: ACCOUNT_SIZE = 500000 (hardcoded)
   - Impact: Could only enter 1 position → now can enter 12

3. **Enhanced Position Sizing** (percentage_based_allocation.py v3→v4)
   - OLD: Equal spread across all candidates (₹22K × 9)
   - NEW: Quality-tiered allocation with top-N selection

### NEW ALLOCATION LOGIC:

Tier Structure within each 60/20/20 category:
- Tier A (70+ score, RS 90+): 60% budget → ₹50-100K each (top 2)
- Tier B (65-70, RS 70+): 20% budget → ₹40-70K each (top 1-2)
- Tier C (60-65, RS 60+): 20% budget → ₹20-40K each (top 1-2)

Features:
- Historical exit check (skip recent losers)
- Top-N selection (not all candidates)
- Position size reflects conviction
- Max 3-5 positions per category

### TODAY'S EXAMPLE (Dec 17):

Large-caps (₹265K budget):
OLD: 9 pos × ₹22K = ₹198K
NEW: 4 pos (₹71K, ₹71K, ₹71K, ₹53K) = ₹266K

Mid-caps (₹88K budget):
OLD: 9 pos × ₹9K = ₹81K
NEW: 5 pos (₹26K, ₹26K, ₹44K, ₹44K, ₹18K) = ₹158K

Result: Better quality concentration

### FILES CHANGED:
- scripts/db_connection.py (get_available_cash rewrite)
- daily_trading_pg.py (ACCOUNT_SIZE fix)
- scripts/percentage_based_allocation.py (v3→v4)

### BACKUPS:
- percentage_based_allocation_v3_old_equal_split.py
- percentage_based_allocation_v4_tiered_quality.py
- percentage_based_allocation_OLD_20251217.py

### GIT COMMITS:
- 0754535: Capital calculation fix
- 3b585c8: ACCOUNT_SIZE fix
- c17fbfb: Enhanced allocation

### WHY THIS WEEK FAILED:
Mon-Fri: DAILY couldn't enter (capital bug)
Only 1 position all week (₹8K HINDZINC)
Missed 15+ signals daily

### TOMORROW EXPECTED:
✅ ₹441K available
✅ 9-12 quality positions
✅ ₹20K-100K sized by tier
✅ Auto-skip recent losers
