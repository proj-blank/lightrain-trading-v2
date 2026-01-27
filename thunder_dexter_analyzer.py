#!/usr/bin/env python3
"""
Dexter-Lite Fundamental Analyzer - v2 with Phase 1 Improvements

PHASE 1 ENHANCEMENTS:
- Added earnings acceleration score (20 points)
- Reweighted scoring to emphasize earnings momentum
- Uses FREE data sources (yfinance) instead of paid Financial Datasets API
- Provides 80% of Dexter's value at 0% data cost

Cost: Only OpenAI API (~/bin/zsh.01-0.03 per analysis)
"""

import os
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from scripts.db_connection import get_db_cursor

load_dotenv()

# Use Claude (we already have ANTHROPIC_API_KEY)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def fetch_financial_metrics(ticker):
    """
    Fetch fundamental metrics using yfinance (FREE)

    Returns:
        dict with financial metrics including quarterly earnings history
    """
    try:
        stock = yf.Ticker(ticker)

        # Get key metrics from yfinance
        info = stock.info
        financials = stock.quarterly_financials  # Last 4 quarters
        balance_sheet = stock.quarterly_balance_sheet
        # earnings = stock.quarterly_earnings  # DEPRECATED - using quarterly_income_stmt instead

        # Calculate key metrics
        metrics = {
            'ticker': ticker,
            'company_name': info.get('longName', ticker),
            'sector': info.get('sector', 'Unknown'),
            'industry': info.get('industry', 'Unknown'),

            # Growth metrics
            'revenue_growth_yoy': info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else None,
            'earnings_growth_yoy': info.get('earningsGrowth', 0) * 100 if info.get('earningsGrowth') else None,

            # Profitability
            'operating_margin': info.get('operatingMargins', 0) * 100 if info.get('operatingMargins') else None,
            'net_margin': info.get('profitMargins', 0) * 100 if info.get('profitMargins') else None,
            'roe': info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else None,

            # Financial health
            'debt_to_equity': info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else None,
            'current_ratio': info.get('currentRatio', 0),
            'quick_ratio': info.get('quickRatio', 0),

            # Cash flow
            'operating_cash_flow': info.get('operatingCashflow', 0),
            'free_cash_flow': info.get('freeCashflow', 0),

            # Valuation
            'pe_ratio': info.get('trailingPE', 0),
            'forward_pe': info.get('forwardPE', 0),
            'peg_ratio': info.get('pegRatio', 0),
            'price_to_book': info.get('priceToBook', 0),

            # Quality indicators
            'recommendation': info.get('recommendationKey', 'none'),
            'target_price': info.get('targetMeanPrice', 0)
        }

        # Calculate quarterly revenue trend (growth trajectory)
        if financials is not None and not financials.empty and 'Total Revenue' in financials.index:
            revenues = financials.loc['Total Revenue'].dropna()
            if len(revenues) >= 4:
                # QoQ growth rate
                qoq_growth = []
                for i in range(len(revenues) - 1):
                    growth = ((revenues.iloc[i] - revenues.iloc[i+1]) / revenues.iloc[i+1]) * 100
                    qoq_growth.append(growth)

                metrics['avg_qoq_revenue_growth'] = sum(qoq_growth) / len(qoq_growth) if qoq_growth else 0
                metrics['revenue_trend'] = 'GROWING' if metrics['avg_qoq_revenue_growth'] > 0 else 'DECLINING'

        # PHASE 1: Calculate earnings acceleration using quarterly_income_stmt
        # (quarterly_earnings is deprecated in yfinance)
        quarterly_income = stock.quarterly_income_stmt
        if quarterly_income is not None and not quarterly_income.empty:
            # Try Diluted EPS first, then Basic EPS, then Net Income
            eps_values = None
            eps_source = None
            
            if 'Diluted EPS' in quarterly_income.index:
                eps_values = quarterly_income.loc['Diluted EPS'].dropna()
                eps_source = 'Diluted EPS'
            elif 'Basic EPS' in quarterly_income.index:
                eps_values = quarterly_income.loc['Basic EPS'].dropna()
                eps_source = 'Basic EPS'
            elif 'Net Income' in quarterly_income.index:
                # Use Net Income as fallback (not per-share but still shows growth)
                eps_values = quarterly_income.loc['Net Income'].dropna()
                eps_source = 'Net Income'
            
            if eps_values is not None and len(eps_values) >= 3:
                # Calculate QoQ growth rates (most recent first in yfinance)
                qoq_eps_growth = []
                eps_list = list(eps_values.values)[:4]  # Last 4 quarters
                
                for i in range(len(eps_list) - 1):
                    current = eps_list[i]
                    previous = eps_list[i + 1]
                    if previous != 0 and not pd.isna(previous) and not pd.isna(current):
                        growth = ((current - previous) / abs(previous)) * 100
                        qoq_eps_growth.append(growth)
                
                # Check for acceleration: EPS growing AND growth rate increasing
                # Acceleration = each quarter's growth rate > previous quarter's growth rate
                acceleration_count = 0
                if len(qoq_eps_growth) >= 2:
                    for i in range(len(qoq_eps_growth) - 1):
                        # qoq_eps_growth[0] is most recent, so we check if recent > older
                        if qoq_eps_growth[i] > qoq_eps_growth[i + 1]:
                            acceleration_count += 1
                
                metrics['earnings_acceleration_quarters'] = acceleration_count
                metrics['qoq_eps_growth'] = qoq_eps_growth
                metrics['eps_source'] = eps_source
                # Accelerating if at least 1 quarter of increasing growth rate AND positive recent growth
                metrics['is_accelerating'] = acceleration_count >= 1 and (qoq_eps_growth[0] > 0 if qoq_eps_growth else False)
            else:
                metrics['earnings_acceleration_quarters'] = 0
                metrics['is_accelerating'] = False
                metrics['eps_source'] = None
        else:
            metrics['earnings_acceleration_quarters'] = 0
            metrics['is_accelerating'] = False
            metrics['eps_source'] = None

        return metrics

    except Exception as e:
        print(f"❌ Error fetching metrics for {ticker}: {e}")
        return None


def calculate_dexter_score(metrics):
    """
    Calculate overall fundamental thunder score (0-100)
    
    PHASE 1 ENHANCED SCORING:
    - Earnings Acceleration (20 points) - NEW!
    - Revenue Growth (15 points) - reduced from 30
    - EPS Growth (10 points) - NEW split from revenue
    - Profitability (25 points) - unchanged
    - Financial Health (20 points) - reduced from 25
    - Quality (10 points) - reduced from 20
    
    Total: 100 points
    Emphasis on EARNINGS MOMENTUM over static metrics
    """

    if not metrics:
        return 0

    score = 0

    # 1. EARNINGS ACCELERATION SCORE (20 points) - PHASE 1 NEW!
    acceleration_quarters = metrics.get('earnings_acceleration_quarters', 0)
    is_accelerating = metrics.get('is_accelerating', False)
    
    if acceleration_quarters >= 2:
        score += 20  # 2+ consecutive quarters of acceleration
    elif acceleration_quarters == 1:
        score += 10  # 1 quarter of acceleration
    
    # 2. REVENUE GROWTH SCORE (15 points)
    revenue_growth = metrics.get('revenue_growth_yoy', 0) or 0
    if revenue_growth > 25:
        score += 15
    elif revenue_growth > 20:
        score += 12
    elif revenue_growth > 15:
        score += 10
    elif revenue_growth > 10:
        score += 7
    elif revenue_growth > 5:
        score += 5

    # 3. EPS GROWTH SCORE (10 points) - PHASE 1 NEW!
    earnings_growth = metrics.get('earnings_growth_yoy', 0) or 0
    if earnings_growth > 30:
        score += 10
    elif earnings_growth > 25:
        score += 8
    elif earnings_growth > 20:
        score += 6
    elif earnings_growth > 15:
        score += 4

    # 4. PROFITABILITY SCORE (25 points)
    operating_margin = metrics.get('operating_margin', 0) or 0
    roe = metrics.get('roe', 0) or 0

    if operating_margin > 20:
        score += 15
    elif operating_margin > 15:
        score += 12
    elif operating_margin > 10:
        score += 9
    elif operating_margin > 5:
        score += 6

    if roe > 20:
        score += 10
    elif roe > 15:
        score += 7
    elif roe > 10:
        score += 5

    # 5. FINANCIAL HEALTH SCORE (20 points)
    debt_to_equity = metrics.get('debt_to_equity', 999) or 999
    current_ratio = metrics.get('current_ratio', 0) or 0

    # Lower debt is better
    if debt_to_equity < 0.3:
        score += 12
    elif debt_to_equity < 0.5:
        score += 10
    elif debt_to_equity < 1.0:
        score += 7
    elif debt_to_equity < 2.0:
        score += 4

    # Liquidity
    if current_ratio > 2.0:
        score += 8
    elif current_ratio > 1.5:
        score += 6
    elif current_ratio > 1.0:
        score += 4

    # 6. QUALITY SCORE (10 points)
    fcf = metrics.get('free_cash_flow', 0) or 0
    revenue_trend = metrics.get('revenue_trend', 'UNKNOWN')

    if fcf > 0:
        score += 5

    if revenue_trend == 'GROWING':
        score += 5

    return min(score, 100)  # Cap at 100


def analyze_with_ai(ticker, metrics, earnings_in_days):
    """
    Use Claude AI to provide qualitative analysis and earnings prediction

    Returns:
        dict with AI recommendation and reasoning
    """

    if not ANTHROPIC_API_KEY:
        return {
            'recommendation': 'UNKNOWN',
            'confidence': 'LOW',
            'reasoning': 'AI analysis unavailable - no API key',
            'earnings_prediction': 'UNKNOWN'
        }

    # Prepare context with safe None handling
    def safe_format(value, format_spec='', default='N/A'):
        """Safely format value, handling None"""
        if value is None:
            return default
        try:
            if format_spec:
                return format(value, format_spec)
            return str(value)
        except:
            return default

    # PHASE 1: Include earnings acceleration in AI context
    acceleration_status = "✅ ACCELERATING" if metrics.get('is_accelerating') else "❌ NOT ACCELERATING"
    acceleration_quarters = metrics.get('earnings_acceleration_quarters', 0)

    context = f"""You are a fundamental analyst evaluating a stock for a 30-60 day thunder-based trade.

COMPANY: {metrics.get('company_name', ticker)} ({ticker})
SECTOR: {metrics.get('sector', 'Unknown')}

FUNDAMENTAL METRICS:
- Revenue Growth YoY: {safe_format(metrics.get('revenue_growth_yoy'), '.1f', 'N/A')}%
- EPS Growth YoY: {safe_format(metrics.get('earnings_growth_yoy'), '.1f', 'N/A')}%
- Earnings Acceleration: {acceleration_status} ({acceleration_quarters} quarters)
- Operating Margin: {safe_format(metrics.get('operating_margin'), '.1f', 'N/A')}%
- Net Margin: {safe_format(metrics.get('net_margin'), '.1f', 'N/A')}%
- ROE: {safe_format(metrics.get('roe'), '.1f', 'N/A')}%
- Debt-to-Equity: {safe_format(metrics.get('debt_to_equity'), '.2f', 'N/A')}
- Current Ratio: {safe_format(metrics.get('current_ratio'), '.2f', 'N/A')}
- Free Cash Flow: ₹{safe_format(metrics.get('free_cash_flow'), ',.0f', 'N/A')} Cr
- Revenue Trend: {metrics.get('revenue_trend', 'UNKNOWN')}

EARNINGS: Reporting in {safe_format(earnings_in_days, '', 'N/A')} days

TASK:
1. Evaluate if this is a high-thunder fundamental play
2. Predict earnings outcome (BEAT, MISS, or INLINE)
3. Recommend: STRONG_BUY, BUY, HOLD, or AVOID

IMPORTANT:
- Focus on business thunder (margins, debt, cash flow)
- EARNINGS ACCELERATION is critical - accelerating growth = higher probability of beat
- Consider earnings catalyst (will fundamentals translate to earnings beat?)
- We plan to HOLD THROUGH EARNINGS (not a quick flip)

Provide response in this format:

RECOMMENDATION: [STRONG_BUY/BUY/HOLD/AVOID]
CONFIDENCE: [HIGH/MEDIUM/LOW]
EARNINGS_PREDICTION: [BEAT/INLINE/MISS]
REASONING: [2-3 sentences explaining your view]
KEY_STRENGTHS: [Top 2-3 strengths]
KEY_RISKS: [Top 2-3 risks]

Be specific and actionable."""

    try:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        payload = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": context}]
        }

        response = requests.post(url, json=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            ai_response = response.json()['content'][0]['text']
            return parse_ai_analysis(ai_response)
        else:
            print(f"⚠️ Claude API error: {response.status_code}")
            return {
                'recommendation': 'UNKNOWN',
                'confidence': 'LOW',
                'reasoning': 'API error',
                'earnings_prediction': 'UNKNOWN'
            }

    except Exception as e:
        print(f"❌ AI analysis error: {e}")
        return {
            'recommendation': 'UNKNOWN',
            'confidence': 'LOW',
            'reasoning': str(e),
            'earnings_prediction': 'UNKNOWN'
        }


def parse_ai_analysis(ai_text):
    """Parse Claude's analysis into structured format"""

    result = {
        'recommendation': 'HOLD',
        'confidence': 'MEDIUM',
        'earnings_prediction': 'INLINE',
        'reasoning': '',
        'key_strengths': [],
        'key_risks': []
    }

    try:
        lines = ai_text.strip().split('\n')
        current_section = None

        for line in lines:
            line = line.strip()

            if line.startswith('RECOMMENDATION:'):
                rec = line.split(':', 1)[1].strip().upper()
                result['recommendation'] = rec

            elif line.startswith('CONFIDENCE:'):
                conf = line.split(':', 1)[1].strip().upper()
                result['confidence'] = conf

            elif line.startswith('EARNINGS_PREDICTION:'):
                pred = line.split(':', 1)[1].strip().upper()
                result['earnings_prediction'] = pred

            elif line.startswith('REASONING:'):
                result['reasoning'] = line.split(':', 1)[1].strip()
                current_section = 'reasoning'

            elif line.startswith('KEY_STRENGTHS:'):
                current_section = 'strengths'

            elif line.startswith('KEY_RISKS:'):
                current_section = 'risks'

            elif line.startswith('- ') or line.startswith('• '):
                item = line[2:].strip()
                if current_section == 'strengths':
                    result['key_strengths'].append(item)
                elif current_section == 'risks':
                    result['key_risks'].append(item)

        # Extract multi-line reasoning if present
        if 'REASONING:' in ai_text and ('KEY_STRENGTHS:' in ai_text or 'KEY_RISKS:' in ai_text):
            reasoning_start = ai_text.index('REASONING:') + len('REASONING:')
            reasoning_end = min(
                ai_text.index('KEY_STRENGTHS:') if 'KEY_STRENGTHS:' in ai_text else len(ai_text),
                ai_text.index('KEY_RISKS:') if 'KEY_RISKS:' in ai_text else len(ai_text)
            )
            result['reasoning'] = ai_text[reasoning_start:reasoning_end].strip()

    except Exception as e:
        print(f"⚠️ Error parsing AI response: {e}")
        result['reasoning'] = ai_text[:200] if ai_text else 'Parse error'

    return result


def analyze_thunder_candidate(ticker, earnings_date):
    """
    Complete Dexter-Lite analysis for a thunder strategy candidate

    Returns:
        dict with complete analysis
    """

    print("=" * 70)
    print(f"🔍 DEXTER-LITE ANALYSIS v2: {ticker}")
    print("=" * 70)

    # Calculate days to earnings
    if isinstance(earnings_date, str):
        earnings_date = pd.to_datetime(earnings_date).date()

    days_to_earnings = (earnings_date - datetime.now().date()).days

    print(f"\n📅 Earnings Date: {earnings_date}")
    print(f"⏰ Days to Earnings: {days_to_earnings}")

    # Step 1: Fetch financial metrics (FREE - yfinance)
    print(f"\n📊 Fetching financial metrics...")
    metrics = fetch_financial_metrics(ticker)

    if not metrics:
        print("❌ Failed to fetch metrics")
        return None

    # Step 2: Calculate Dexter score
    dexter_score = calculate_dexter_score(metrics)
    print(f"\n🎯 Dexter Quality Score: {dexter_score}/100")
    
    # PHASE 1: Show earnings acceleration
    if metrics.get('is_accelerating'):
        print(f"   ✅ Earnings ACCELERATING ({metrics.get('earnings_acceleration_quarters')} quarters)")
    else:
        print(f"   ⚠️ Earnings NOT accelerating")

    # Step 3: AI analysis (costs ~/bin/zsh.01)
    print(f"\n🤖 Running AI analysis...")
    ai_analysis = analyze_with_ai(ticker, metrics, days_to_earnings)

    # Step 4: Combine results
    full_analysis = {
        'ticker': ticker,
        'company_name': metrics.get('company_name'),
        'sector': metrics.get('sector'),
        'earnings_date': earnings_date,
        'days_to_earnings': days_to_earnings,

        # Metrics
        'revenue_growth_yoy': metrics.get('revenue_growth_yoy'),
        'earnings_growth_yoy': metrics.get('earnings_growth_yoy'),
        'earnings_acceleration_quarters': metrics.get('earnings_acceleration_quarters'),
        'is_accelerating': metrics.get('is_accelerating'),
        'operating_margin': metrics.get('operating_margin'),
        'debt_to_equity': metrics.get('debt_to_equity'),
        'roe': metrics.get('roe'),
        'free_cash_flow': metrics.get('free_cash_flow'),

        # Scoring
        'dexter_score': dexter_score,
        'recommendation': ai_analysis.get('recommendation'),
        'confidence': ai_analysis.get('confidence'),
        'earnings_prediction': ai_analysis.get('earnings_prediction'),

        # Analysis
        'reasoning': ai_analysis.get('reasoning'),
        'key_strengths': ai_analysis.get('key_strengths', []),
        'key_risks': ai_analysis.get('key_risks', []),

        'analysis_date': datetime.now().date()
    }

    # Print summary
    print("\n" + "=" * 70)
    print("📊 ANALYSIS SUMMARY")
    print("=" * 70)
    print(f"\n🎯 Dexter Score: {dexter_score}/100")
    print(f"📈 Recommendation: {ai_analysis.get('recommendation')} (Confidence: {ai_analysis.get('confidence')})")
    print(f"📅 Earnings Prediction: {ai_analysis.get('earnings_prediction')}")
    print(f"\n💭 Reasoning: {ai_analysis.get('reasoning')}")

    if ai_analysis.get('key_strengths'):
        print(f"\n✅ Key Strengths:")
        for strength in ai_analysis.get('key_strengths', []):
            print(f"   • {strength}")

    if ai_analysis.get('key_risks'):
        print(f"\n⚠️ Key Risks:")
        for risk in ai_analysis.get('key_risks', []):
            print(f"   • {risk}")

    print("\n" + "=" * 70)

    # Save to cache
    # save_to_cache(full_analysis)  # TODO: Update to use thunder_evaluations

    return full_analysis


def save_to_cache(analysis):
    """Save Dexter analysis to cache (avoid re-querying)"""

    try:
        with get_db_cursor() as cur:
            # Determine quarter
            earnings_date = analysis['earnings_date']
            month = earnings_date.month
            year = earnings_date.year

            if month in [1, 2, 3]:
                quarter = f"Q4 {year-1}"
            elif month in [4, 5, 6]:
                quarter = f"Q1 {year}"
            elif month in [7, 8, 9]:
                quarter = f"Q2 {year}"
            else:
                quarter = f"Q3 {year}"

            cur.execute("""
                INSERT INTO dexter_analysis_cache
                    (ticker, analysis_date, quarter,
                     revenue_growth_yoy, operating_margin, debt_to_equity,
                     roe, overall_score, recommendation, reasoning,
                     key_strengths, key_risks)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, analysis_date)
                DO UPDATE SET
                    revenue_growth_yoy = EXCLUDED.revenue_growth_yoy,
                    operating_margin = EXCLUDED.operating_margin,
                    debt_to_equity = EXCLUDED.debt_to_equity,
                    roe = EXCLUDED.roe,
                    overall_score = EXCLUDED.overall_score,
                    recommendation = EXCLUDED.recommendation,
                    reasoning = EXCLUDED.reasoning,
                    key_strengths = EXCLUDED.key_strengths,
                    key_risks = EXCLUDED.key_risks
            """, (
                analysis['ticker'],
                analysis['analysis_date'],
                quarter,
                analysis.get('revenue_growth_yoy'),
                analysis.get('operating_margin'),
                analysis.get('debt_to_equity'),
                analysis.get('roe'),
                analysis['dexter_score'],
                analysis['recommendation'],
                analysis['reasoning'],
                ', '.join(analysis.get('key_strengths', [])),
                ', '.join(analysis.get('key_risks', []))
            ))

        print(f"✅ Analysis cached for {analysis['ticker']}")

    except Exception as e:
        print(f"⚠️ Could not cache analysis: {e}")


if __name__ == "__main__":
    # Test analysis
    test_ticker = "TCS.NS"
    test_earnings_date = datetime.now().date() + timedelta(days=21)  # 3 weeks out

    result = analyze_thunder_candidate(test_ticker, test_earnings_date)

    if result:
        print(f"\n✅ Analysis complete for {test_ticker}")
        print(f"   Dexter Score: {result['dexter_score']}/100")
        print(f"   Recommendation: {result['recommendation']}")
        print(f"   Earnings Acceleration: {result['is_accelerating']}")
