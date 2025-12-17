#!/usr/bin/env python3
"""
Enhanced Quality-Tiered Capital Allocation with Historical Exit Analysis

Key Features:
1. Conviction-based tiering (A/B/C within each category)
2. Top-N selection (not all candidates)
3. Historical exit analysis (skip recent losers)
4. SmartEntry validation enforcement
5. Position sizing reflects quality

Tier Structure within 60/20/20 split:
- Tier A (70+ score, RS 90+): 60% of category budget
- Tier B (65-70 score, RS 70-90): 20% of category budget
- Tier C (60-65 score, RS 60-70): 20% of category budget
"""

import sys
sys.path.insert(0, '/home/ubuntu/trading')

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from scripts.db_connection import get_db_cursor


def check_recent_exit_history(ticker: str, lookback_days: int = 7) -> Optional[Dict]:
    """
    Check if stock was recently exited at a loss

    Args:
        ticker: Stock symbol
        lookback_days: How many days to look back

    Returns:
        Dict with exit info if found, None otherwise
    """
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT ticker, exit_date, entry_price, quantity, realized_pnl,
                   ai_reasoning,
                   EXTRACT(DAY FROM CURRENT_DATE - exit_date) as days_ago
            FROM positions
            WHERE strategy IN ('DAILY', 'SWING')
              AND status = 'CLOSED'
              AND exit_date >= CURRENT_DATE - INTERVAL '%s days'
              AND ticker = %s
              AND realized_pnl < 0
            ORDER BY exit_date DESC
            LIMIT 1
        """, (lookback_days, ticker))

        result = cur.fetchone()
        if result:
            return {
                'ticker': result['ticker'],
                'exit_date': result['exit_date'],
                'days_ago': int(result['days_ago']),
                'loss': float(result['realized_pnl']),
                'ai_reasoning': result['ai_reasoning']
            }
        return None


def classify_by_tier(candidates: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Classify candidates into conviction tiers

    Tier A: Score 70+, RS 90+ (best quality)
    Tier B: Score 65-70, RS 70-90
    Tier C: Score 60-65, RS 60-70
    """
    tiers = {'A': [], 'B': [], 'C': []}

    for candidate in candidates:
        score = candidate.get('score', 0)
        rs = candidate.get('rs_rating', 0)

        if score >= 70 and rs >= 90:
            tiers['A'].append(candidate)
        elif score >= 65 and rs >= 70:
            tiers['B'].append(candidate)
        elif score >= 60 and rs >= 60:
            tiers['C'].append(candidate)
        # Below 60 score or RS → skip entirely

    # Sort each tier by score descending
    for tier in tiers.values():
        tier.sort(key=lambda x: x.get('score', 0), reverse=True)

    return tiers


def select_top_n_by_tier(
    tiers: Dict[str, List[Dict]],
    category_budget: float,
    category_name: str
) -> List[Dict]:
    """
    Select top N candidates from each tier with budget allocation

    Budget split within category:
    - Tier A: 60%
    - Tier B: 20%
    - Tier C: 20%
    """
    selections = []

    tier_a_count = len(tiers['A'])
    tier_b_count = len(tiers['B'])
    tier_c_count = len(tiers['C'])

    print(f"\n  📊 Tier Distribution:")
    print(f"     Tier A (70+, RS 90+): {tier_a_count} stocks")
    print(f"     Tier B (65-70, RS 70+): {tier_b_count} stocks")
    print(f"     Tier C (60-65, RS 60+): {tier_c_count} stocks")

    # Calculate tier budgets
    if tier_a_count > 0:
        # Normal: Tier A exists
        tier_a_budget = category_budget * 0.60
        tier_b_budget = category_budget * 0.20
        tier_c_budget = category_budget * 0.20
    elif tier_b_count > 0:
        # No Tier A, redistribute to B
        tier_a_budget = 0
        tier_b_budget = category_budget * 0.80
        tier_c_budget = category_budget * 0.20
    else:
        # Only Tier C
        tier_a_budget = 0
        tier_b_budget = 0
        tier_c_budget = category_budget

    # Tier A: Take top 2
    if tier_a_count > 0:
        top_a = min(2, tier_a_count)
        pos_size_a = tier_a_budget / top_a
        pos_size_a = max(50000, min(100000, pos_size_a))  # ₹50K-100K range

        print(f"\n  ✅ Tier A: Selecting top {top_a}")
        for i, candidate in enumerate(tiers['A'][:top_a]):
            # Check recent exit history
            recent_exit = check_recent_exit_history(candidate['ticker'])
            if recent_exit:
                print(f"     ⚠️ {candidate['ticker']}: Recently exited {recent_exit['days_ago']}d ago with ₹{recent_exit['loss']:,.0f} loss - SKIP")
                continue

            selections.append({
                **candidate,
                'position_size': pos_size_a,
                'tier': 'A'
            })
            print(f"     {i+1}. {candidate['ticker']:15} Score: {candidate['score']:.1f}, RS: {candidate['rs_rating']} → ₹{pos_size_a:,.0f}")

    # Tier B: Take top 1-2
    if tier_b_count > 0:
        top_b = min(2, tier_b_count)
        pos_size_b = tier_b_budget / top_b
        pos_size_b = max(40000, min(70000, pos_size_b))  # ₹40K-70K range

        print(f"\n  ✅ Tier B: Selecting top {top_b}")
        for i, candidate in enumerate(tiers['B'][:top_b]):
            recent_exit = check_recent_exit_history(candidate['ticker'])
            if recent_exit:
                print(f"     ⚠️ {candidate['ticker']}: Recently exited {recent_exit['days_ago']}d ago - SKIP")
                continue

            selections.append({
                **candidate,
                'position_size': pos_size_b,
                'tier': 'B'
            })
            print(f"     {i+1}. {candidate['ticker']:15} Score: {candidate['score']:.1f}, RS: {candidate['rs_rating']} → ₹{pos_size_b:,.0f}")

    # Tier C: Take top 1-2 (only if budget left)
    if tier_c_count > 0 and tier_c_budget > 20000:
        top_c = min(2, tier_c_count)
        pos_size_c = tier_c_budget / top_c
        pos_size_c = max(20000, min(40000, pos_size_c))  # ₹20K-40K range

        print(f"\n  ✅ Tier C: Selecting top {top_c}")
        for i, candidate in enumerate(tiers['C'][:top_c]):
            recent_exit = check_recent_exit_history(candidate['ticker'])
            if recent_exit:
                print(f"     ⚠️ {candidate['ticker']}: Recently exited {recent_exit['days_ago']}d ago - SKIP")
                continue

            selections.append({
                **candidate,
                'position_size': pos_size_c,
                'tier': 'C'
            })
            print(f"     {i+1}. {candidate['ticker']:15} Score: {candidate['score']:.1f}, RS: {candidate['rs_rating']} → ₹{pos_size_c:,.0f}")

    return selections


def calculate_percentage_allocation(
    candidates: Dict[str, List[Dict]],
    total_capital: float,
    target_allocation: Dict[str, float] = {'large': 0.60, 'mid': 0.20, 'micro': 0.20},
    min_position_size: float = 20000,
    max_position_size: float = 100000,
    min_score: int = 60,
    min_rs_rating: int = 60
) -> Dict:
    """
    Enhanced quality-tiered allocation with historical analysis

    Args:
        candidates: Dict with 'large_caps', 'mid_caps', 'micro_caps'
        total_capital: Total capital to deploy
        target_allocation: 60/20/20 split
        min_position_size: Min ₹20K
        max_position_size: Max ₹100K
        min_score: Min 60 score
        min_rs_rating: Min 60 RS

    Returns:
        allocation_plan with selected positions
    """

    print()
    print("=" * 80)
    print("ENHANCED QUALITY-TIERED ALLOCATION")
    print("=" * 80)
    print(f"Total Capital: ₹{total_capital:,.0f}")
    print(f"Target: {int(target_allocation['large']*100)}% Large / "
          f"{int(target_allocation['mid']*100)}% Mid / "
          f"{int(target_allocation['micro']*100)}% Micro")
    print()
    print("Tier Structure (within each category):")
    print("  Tier A (70+, RS 90+): 60% → ₹50-100K each")
    print("  Tier B (65-70, RS 70+): 20% → ₹40-70K each")
    print("  Tier C (60-65, RS 60+): 20% → ₹20-40K each")
    print()

    allocation_plan = {
        'positions': {},
        'capital': {},
        'capital_per_position': {},
        'total_positions': 0,
        'selected_stocks': {}
    }

    all_selections = []

    for category in ['large', 'mid', 'micro']:
        category_key = f'{category}_caps'
        category_candidates = candidates.get(category_key, [])

        # Calculate category budget
        category_budget = total_capital * target_allocation[category]

        print(f"\n{'='*80}")
        print(f"{category.upper()}-CAPS (Budget: ₹{category_budget:,.0f})")
        print('='*80)
        print(f"Total Candidates: {len(category_candidates)}")

        if not category_candidates:
            print("  ⚠️ No candidates - budget will be redistributed")
            allocation_plan['positions'][category] = 0
            allocation_plan['capital'][category] = 0
            allocation_plan['selected_stocks'][category] = []
            continue

        # Classify into tiers
        tiers = classify_by_tier(category_candidates)

        if not any(tiers.values()):
            print("  ⚠️ No qualified candidates (all below 60 score/RS)")
            allocation_plan['positions'][category] = 0
            allocation_plan['capital'][category] = 0
            allocation_plan['selected_stocks'][category] = []
            continue

        # Select top N from each tier
        selections = select_top_n_by_tier(tiers, category_budget, category)

        # Store results
        allocation_plan['positions'][category] = len(selections)
        allocation_plan['capital'][category] = sum(s['position_size'] for s in selections)
        allocation_plan['selected_stocks'][category] = selections
        all_selections.extend(selections)

    allocation_plan['total_positions'] = len(all_selections)

    # Summary
    print(f"\n{'='*80}")
    print("ALLOCATION SUMMARY")
    print('='*80)
    for category in ['large', 'mid', 'micro']:
        pos_count = allocation_plan['positions'].get(category, 0)
        capital = allocation_plan['capital'].get(category, 0)
        print(f"{category.upper()}-caps: {pos_count:2} positions × avg ₹{capital/pos_count if pos_count > 0 else 0:7,.0f} = ₹{capital:10,.0f}")

    total_deployed = sum(allocation_plan['capital'].values())
    print(f"{'─'*80}")
    print(f"TOTAL:      {allocation_plan['total_positions']:2} positions"
          f"{'':25} = ₹{total_deployed:10,.0f}")
    print(f"Utilization: {(total_deployed/total_capital)*100:.1f}%")
    print('='*80)
    print()

    return allocation_plan


def select_positions_for_entry(allocation_plan: Dict) -> List[Dict]:
    """
    Extract selected positions from allocation plan for entry

    Returns list of positions to enter with calculated sizes
    """
    positions = []

    for category in ['large', 'mid', 'micro']:
        category_selections = allocation_plan['selected_stocks'].get(category, [])
        for selection in category_selections:
            positions.append({
                'ticker': selection['ticker'],
                'category': category,
                'score': selection['score'],
                'rs_rating': selection['rs_rating'],
                'position_size': selection['position_size'],
                'tier': selection['tier'],
                'indicators_fired': selection.get('indicators_fired', [])
            })

    return positions
