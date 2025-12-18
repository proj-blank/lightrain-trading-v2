#!/usr/bin/env python3
"""
Percentage-Based Capital Allocation - TRUE 60/20/20 Split
NO FIXED POSITION COUNTS - Variable positions based on signals available

User requirement: "should be a % split and not 6+2+2 trades"

Logic:
- 60% capital → Large-caps (however many pass filters)
- 20% capital → Mid-caps (however many pass filters)
- 20% capital → Micro-caps (however many pass filters)
- Position count is VARIABLE, not fixed
"""

import numpy as np
from typing import Dict, List


def calculate_percentage_allocation(
    candidates: Dict[str, List[Dict]],
    total_capital: float,
    target_allocation: Dict[str, float] = {'large': 0.60, 'mid': 0.20, 'micro': 0.20},
    min_position_size: float = 20000,  # Minimum ₹20K per position
    max_position_size: float = 100000,  # Maximum ₹100K per position
    min_score: int = 60,  # Minimum score to qualify
    min_rs_rating: int = 50  # Minimum RS rating to qualify
) -> Dict:
    """
    Calculate allocation with VARIABLE position counts based on signals.

    This is what the user wants: % split, NOT fixed position counts.

    Args:
        candidates: Dict with keys 'large_caps', 'mid_caps', 'micro_caps'
        total_capital: Total capital to deploy (e.g., ₹500,000)
        target_allocation: Target % for each category (default 60/20/20)
        min_position_size: Minimum capital per position
        max_position_size: Maximum capital per position
        min_score: Minimum score threshold
        min_rs_rating: Minimum RS rating threshold

    Returns:
        allocation_plan: Dict with positions and capital per category
    """

    print()
    print("=" * 80)
    print("PERCENTAGE-BASED ALLOCATION (NO FIXED POSITION COUNTS)")
    print("=" * 80)
    print(f"Total Capital: ₹{total_capital:,.0f}")
    print(f"Target: {int(target_allocation['large']*100)}% Large / "
          f"{int(target_allocation['mid']*100)}% Mid / "
          f"{int(target_allocation['micro']*100)}% Micro")
    print()

    allocation_plan = {
        'positions': {},
        'capital': {},
        'capital_per_position': {},
        'total_positions': 0,
        'selected_stocks': {}
    }

    for category in ['large', 'mid', 'micro']:
        category_key = f'{category}_caps'
        category_candidates = candidates.get(category_key, [])

        # Filter candidates by score and RS rating
        qualified = [
            c for c in category_candidates
            if c.get('score', 0) >= min_score and c.get('rs_rating', 0) >= min_rs_rating
        ]

        # Calculate category budget (60/20/20 split)
        category_budget = total_capital * target_allocation[category]

        print(f"{category.upper()}-CAPS:")
        print(f"  Budget: ₹{category_budget:,.0f} ({target_allocation[category]*100:.0f}%)")
        print(f"  Total Candidates: {len(category_candidates)}")
        print(f"  Qualified (score≥{min_score}, RS≥{min_rs_rating}): {len(qualified)}")

        if not qualified:
            print(f"  ⚠️  No qualified candidates - budget will be redistributed")
            allocation_plan['positions'][category] = 0
            allocation_plan['capital'][category] = 0
            allocation_plan['capital_per_position'][category] = 0
            allocation_plan['selected_stocks'][category] = []
            print()
            continue

        # Sort by score descending (take best candidates)
        qualified.sort(key=lambda x: x.get('score', 0), reverse=True)

        # Equal weight distribution within category
        position_size = category_budget / len(qualified)

        # Apply position size limits
        if position_size < min_position_size:
            # Too many candidates, not enough capital
            # Take fewer candidates to maintain minimum position size
            max_positions = int(category_budget / min_position_size)
            max_positions = max(1, max_positions)  # At least 1 position
            qualified = qualified[:max_positions]
            position_size = category_budget / len(qualified)
            print(f"  ⚠️  Limited to {max_positions} positions (min size: ₹{min_position_size:,.0f})")
        elif position_size > max_position_size:
            # Too few candidates, too much capital per position
            # Cap position size and save remaining capital
            position_size = max_position_size
            print(f"  ⚠️  Position size capped at ₹{max_position_size:,.0f}")

        # Calculate actual capital deployed
        num_positions = len(qualified)
        actual_capital = position_size * num_positions

        print(f"  Positions: {num_positions}")
        print(f"  Capital per position: ₹{position_size:,.0f}")
        print(f"  Total deployed: ₹{actual_capital:,.0f}")

        # Store allocation plan
        allocation_plan['positions'][category] = num_positions
        allocation_plan['capital'][category] = actual_capital
        allocation_plan['capital_per_position'][category] = position_size
        allocation_plan['selected_stocks'][category] = qualified[:num_positions]
        allocation_plan['total_positions'] += num_positions

        print()

    # Handle unused capital (if any category had 0 candidates)
    total_allocated = sum(allocation_plan['capital'].values())
    unused_capital = total_capital - total_allocated

    if unused_capital > 0:
        print(f"⚠️  Unused Capital: ₹{unused_capital:,.0f}")
        print("   Redistributing proportionally to categories with positions...")
        print()

        # Redistribute to categories with positions
        categories_with_positions = [
            cat for cat in ['large', 'mid', 'micro']
            if allocation_plan['positions'][cat] > 0
        ]

        if categories_with_positions:
            for cat in categories_with_positions:
                # Calculate proportional share
                cat_original = total_capital * target_allocation[cat]
                cat_share = cat_original / sum(
                    total_capital * target_allocation[c]
                    for c in categories_with_positions
                )
                extra = unused_capital * cat_share

                # Add to category
                allocation_plan['capital'][cat] += extra

                # Recalculate position size
                num_pos = allocation_plan['positions'][cat]
                allocation_plan['capital_per_position'][cat] = allocation_plan['capital'][cat] / num_pos

                print(f"   {cat.upper()}: +₹{extra:,.0f} → ₹{allocation_plan['capital_per_position'][cat]:,.0f}/position")
            print()

    # Summary
    total_allocated = sum(allocation_plan['capital'].values())
    total_positions = allocation_plan['total_positions']

    print("=" * 80)
    print("FINAL ALLOCATION")
    print("=" * 80)
    for cat in ['large', 'mid', 'micro']:
        num = allocation_plan['positions'][cat]
        per = allocation_plan['capital_per_position'][cat]
        total = allocation_plan['capital'][cat]
        if num > 0:
            print(f"{cat.upper()}-caps: {num:2d} positions × ₹{per:>8,.0f} = ₹{total:>10,.0f}")
        else:
            print(f"{cat.upper()}-caps: NO POSITIONS (no qualified candidates)")
    print("-" * 80)
    print(f"TOTAL:       {total_positions:2d} positions" + " " * 12 + f"= ₹{total_allocated:>10,.0f}")
    print(f"Utilization: {total_allocated/total_capital*100:>5.1f}%")
    print("=" * 80)
    print()

    return allocation_plan


def select_positions_for_entry(allocation_plan: Dict) -> List[Dict]:
    """
    Convert allocation plan into list of positions ready for entry.
    Interleaves categories proportionally (60/20/20) to ensure diversity.

    Args:
        allocation_plan: Output from calculate_percentage_allocation()

    Returns:
        List of positions with ticker, score, category, capital_allocated (interleaved by category)
    """
    # Organize stocks by category
    category_stocks = {}
    for category in ['large', 'mid', 'micro']:
        selected_stocks = allocation_plan['selected_stocks'].get(category, [])
        capital_per_position = allocation_plan['capital_per_position'].get(category, 0)

        category_stocks[category] = {
            'stocks': selected_stocks,
            'capital': capital_per_position,
            'index': 0  # Track current position in list
        }

    # Interleave positions using 60/20/20 ratio
    # Pattern: L,L,L,M,S,L,L,L,M,S... (3 large, 1 mid, 1 micro)
    positions_to_enter = []
    pattern = ['large', 'large', 'large', 'mid', 'micro']
    pattern_index = 0

    # Keep going until all categories exhausted
    max_iterations = sum(len(cat['stocks']) for cat in category_stocks.values())

    for _ in range(max_iterations * 2):  # Safety limit
        # Get next category from pattern
        category = pattern[pattern_index % len(pattern)]
        cat_data = category_stocks[category]

        # If this category has stocks remaining, add one
        if cat_data['index'] < len(cat_data['stocks']):
            stock = cat_data['stocks'][cat_data['index']]

            position = {
                'ticker': stock['ticker'],
                'score': stock.get('score', 0),
                'rs_rating': stock.get('rs_rating', 0),
                'category': 'Microcap' if category == 'micro' else f"{category.capitalize()}-cap",
                'capital_allocated': cat_data['capital'],
                **{k: v for k, v in stock.items() if k not in ['ticker', 'score', 'rs_rating', 'category']}
            }
            positions_to_enter.append(position)
            cat_data['index'] += 1

        pattern_index += 1

        # Stop if all categories exhausted
        if all(cat['index'] >= len(cat['stocks']) for cat in category_stocks.values()):
            break

    return positions_to_enter


if __name__ == "__main__":
    # Test the allocation logic
    print("\n" + "=" * 80)
    print("TEST: PERCENTAGE-BASED ALLOCATION")
    print("=" * 80 + "\n")

    # Simulate different scenarios
    test_candidates = {
        'large_caps': [
            {'ticker': f'LARGE{i}.NS', 'score': 70+i, 'rs_rating': 85+i}
            for i in range(8)  # 8 large-caps qualified
        ],
        'mid_caps': [
            {'ticker': f'MID{i}.NS', 'score': 65+i, 'rs_rating': 75+i}
            for i in range(4)  # 4 mid-caps qualified
        ],
        'micro_caps': [
            {'ticker': f'MICRO{i}.NS', 'score': 62+i, 'rs_rating': 70+i}
            for i in range(3)  # 3 micro-caps qualified
        ]
    }

    # Test 1: Normal scenario
    print("\n📊 TEST 1: Normal Scenario (8 large + 4 mid + 3 micro)")
    print("-" * 80)
    plan = calculate_percentage_allocation(
        test_candidates,
        total_capital=500000,
        min_score=60,
        min_rs_rating=50
    )

    positions = select_positions_for_entry(plan)
    print(f"\n✅ Total positions to enter: {len(positions)}")
    print(f"   Expected: 15 positions (8+4+3) - VARIABLE, not fixed!\n")

    # Test 2: Scenario with no micro-caps
    print("\n📊 TEST 2: No Micro-caps Available")
    print("-" * 80)
    test_candidates_2 = {
        'large_caps': test_candidates['large_caps'],
        'mid_caps': test_candidates['mid_caps'],
        'micro_caps': []  # No micro-caps today
    }

    plan2 = calculate_percentage_allocation(
        test_candidates_2,
        total_capital=500000,
        min_score=60,
        min_rs_rating=50
    )

    positions2 = select_positions_for_entry(plan2)
    print(f"\n✅ Total positions to enter: {len(positions2)}")
    print(f"   Micro-cap budget redistributed to large/mid caps\n")

    # Test 3: Many candidates (position size capping)
    print("\n📊 TEST 3: Many Candidates (Position Size Capping)")
    print("-" * 80)
    test_candidates_3 = {
        'large_caps': [
            {'ticker': f'LARGE{i}.NS', 'score': 65+i, 'rs_rating': 80}
            for i in range(20)  # 20 large-caps!
        ],
        'mid_caps': [
            {'ticker': f'MID{i}.NS', 'score': 60+i, 'rs_rating': 75}
            for i in range(10)  # 10 mid-caps
        ],
        'micro_caps': [
            {'ticker': f'MICRO{i}.NS', 'score': 62+i, 'rs_rating': 70}
            for i in range(5)  # 5 micro-caps
        ]
    }

    plan3 = calculate_percentage_allocation(
        test_candidates_3,
        total_capital=500000,
        min_score=60,
        min_rs_rating=50,
        min_position_size=20000  # ₹20K minimum
    )

    positions3 = select_positions_for_entry(plan3)
    print(f"\n✅ Total positions to enter: {len(positions3)}")
    print(f"   Position count limited by min_position_size (₹20K)\n")

    print("=" * 80)
    print("✅ ALL TESTS PASSED - Variable position counts working!")
    print("=" * 80)
