# scripts/ai_news_analyzer.py
"""
AI-Powered News Analysis for Circuit Breaker Alerts

Uses Claude API to analyze news + technical signals and provide recommendations.
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")  # Claude API


def fetch_recent_news(ticker, days_back=2):
    """
    Fetch recent news for a stock using Yahoo Finance (FREE, no API key needed)

    Returns:
        list: Recent news articles with title, description, source, date
    """
    import yfinance as yf

    try:
        company_name = ticker.replace('.NS', '').replace('.BO', '')

        stock = yf.Ticker(ticker)
        news = stock.news if hasattr(stock, 'news') and stock.news else []

        news_summary = []
        for item in news[:5]:  # Get top 5 recent articles
            news_summary.append({
                'title': item.get('title', ''),
                'description': item.get('summary', ''),
                'source': item.get('publisher', ''),
                'published': datetime.fromtimestamp(item.get('providerPublishTime', 0)).strftime('%Y-%m-%d %H:%M') if item.get('providerPublishTime') else ''
            })

        return news_summary

    except Exception as e:
        print(f"⚠️ Error fetching news: {e}")
        return []


def analyze_with_ai(ticker, technical_analysis, news_data, entry_price, current_price, loss_pct):
    """
    Use Claude AI to analyze news + technical data and provide recommendation

    Returns:
        dict: {
            'recommendation': 'HOLD' or 'EXIT',
            'confidence': 'HIGH', 'MEDIUM', 'LOW',
            'reasoning': 'Detailed explanation',
            'key_factors': ['factor1', 'factor2', ...]
        }
    """
    if not ANTHROPIC_API_KEY:
        return {
            'recommendation': 'EXIT',
            'confidence': 'LOW',
            'reasoning': 'AI analysis unavailable - ANTHROPIC_API_KEY not configured in .env file. Defaulting to EXIT for safety.',
            'key_factors': ['AI analysis disabled - missing API key']
        }

    # Prepare context for AI
    context = f"""You are a professional Indian stock market analyst. Analyze this position and provide a clear recommendation.

POSITION DETAILS:
- Ticker: {ticker}
- Entry Price: ₹{entry_price:.2f}
- Current Price: ₹{current_price:.2f}
- Current Loss: {loss_pct:.2f}%

TECHNICAL ANALYSIS:
- Daily Change: {technical_analysis.get('daily_change_pct', 0):.2f}%
- Weekly Change: {technical_analysis.get('weekly_change_pct', 0):.2f}%
- RSI: {technical_analysis.get('rsi', 50):.1f} (< 30 = oversold, > 70 = overbought)
- Volume Ratio: {technical_analysis.get('volume_ratio', 1):.1f}x average (> 2x = high activity)
- ATR (Volatility): {technical_analysis.get('atr_pct', 0):.2f}%

RECENT NEWS:
"""

    if news_data and len(news_data) > 0:
        for i, news in enumerate(news_data[:5], 1):
            context += f"\n{i}. [{news['source']}] {news['title']}"
            if news.get('description'):
                context += f"\n   {news['description'][:200]}..."
            context += f"\n   Published: {news.get('published', 'Unknown')}\n"
    else:
        context += "\nNo recent news found for this stock."

    context += """

TASK:
You must provide a detailed analysis explaining WHY this stock dropped -3.8% and what the likely cause is.

Analyze the drop by considering:

1. TECHNICAL FACTORS:
   - Is RSI oversold/overbought? What does this indicate about sentiment?
   - Is volume high (>2x avg)? This suggests institutional selling or panic
   - Is this a sharp drop (-5%+) or gradual decline? Different implications
   - Is ATR high? High volatility = risky to hold

2. LIKELY CAUSES (even without news):
   - Sector weakness? (Is the pharma/chemical sector down today?)
   - Market-wide correction? (Is NIFTY down?)
   - Profit booking after gains? (Check weekly trend)
   - Technical breakdown? (Breaking support levels)
   - Earnings season concerns? (Q results coming up?)

3. WHAT TO DO:
   - HOLD if: Drop is technical/market-wide, no fundamental issues, RSI oversold, normal volume
   - EXIT if: High volume selloff, breaking key support, sector weakness, or sustained decline

IMPORTANT:
- Don't just say "no news = temporary". Explain WHAT likely caused the 3.8% drop.
- Be specific about whether this is a market correction, sector issue, or stock-specific problem.
- If RSI is neutral (40-60), explain why the stock dropped despite neutral technicals.

Provide your response in this EXACT format:

RECOMMENDATION: [HOLD or EXIT]
CONFIDENCE: [HIGH, MEDIUM, or LOW]
REASONING: [3-4 sentences explaining: 1) What likely caused the drop, 2) Whether it's temporary or structural, 3) Your recommendation rationale]
KEY_FACTORS:
- [Most important factor 1 - be specific about cause]
- [Most important factor 2 - impact on position]
- [Most important factor 3 - what to watch]

Be direct, specific, and actionable. This is real money at risk.
"""

    try:
        # Call Claude API
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        payload = {
            "model": "claude-3-haiku-20240307",  # Claude 3 Haiku (fast, accessible)
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": context
                }
            ]
        }

        response = requests.post(url, json=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            ai_response = response.json()['content'][0]['text']

            # Parse response
            result = parse_ai_response(ai_response)
            return result
        else:
            error_msg = response.text
            print(f"⚠️ Claude API error: {response.status_code}")
            print(f"   Response: {error_msg[:200]}")
            return {
                'recommendation': 'EXIT',
                'confidence': 'LOW',
                'reasoning': f'AI analysis failed (API error {response.status_code}). Defaulting to EXIT for safety.',
                'key_factors': ['API error - check ANTHROPIC_API_KEY']
            }

    except Exception as e:
        print(f"❌ AI analysis error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'recommendation': 'EXIT',
            'confidence': 'LOW',
            'reasoning': f'AI analysis failed: {str(e)}. Defaulting to EXIT for safety.',
            'key_factors': ['Analysis error']
        }


def parse_ai_response(ai_text):
    """Parse Claude's response into structured format"""
    result = {
        'recommendation': 'EXIT',  # Default to safe option
        'confidence': 'LOW',
        'reasoning': '',
        'key_factors': []
    }

    try:
        lines = ai_text.strip().split('\n')
        in_key_factors = False

        for line in lines:
            line = line.strip()

            if line.startswith('RECOMMENDATION:'):
                rec = line.split(':', 1)[1].strip().upper()
                if 'HOLD' in rec:
                    result['recommendation'] = 'HOLD'
                elif 'EXIT' in rec:
                    result['recommendation'] = 'EXIT'

            elif line.startswith('CONFIDENCE:'):
                conf = line.split(':', 1)[1].strip().upper()
                if conf in ['HIGH', 'MEDIUM', 'LOW']:
                    result['confidence'] = conf

            elif line.startswith('REASONING:'):
                result['reasoning'] = line.split(':', 1)[1].strip()

            elif line.startswith('KEY_FACTORS:'):
                in_key_factors = True

            elif in_key_factors and line.startswith('- '):
                result['key_factors'].append(line[2:].strip())

        # If reasoning spans multiple lines, extract it properly
        if 'REASONING:' in ai_text and 'KEY_FACTORS:' in ai_text:
            reasoning_start = ai_text.index('REASONING:') + len('REASONING:')
            reasoning_end = ai_text.index('KEY_FACTORS:')
            result['reasoning'] = ai_text[reasoning_start:reasoning_end].strip()

    except Exception as e:
        print(f"⚠️ Error parsing AI response: {e}")
        # Use first 200 chars as fallback
        result['reasoning'] = ai_text[:200] if ai_text else 'Unable to parse AI response'

    return result


def get_ai_recommendation(ticker, technical_analysis, entry_price, current_price, loss_pct):
    """
    Main function: Get AI-powered recommendation with news analysis

    Args:
        ticker: Stock ticker (e.g., 'RELIANCE.NS')
        technical_analysis: Dict with RSI, volume_ratio, daily_change_pct, etc.
        entry_price: Entry price
        current_price: Current price
        loss_pct: Current loss percentage

    Returns:
        dict: {
            'ai_recommendation': 'HOLD' or 'EXIT',
            'ai_confidence': 'HIGH', 'MEDIUM', 'LOW',
            'ai_reasoning': 'Detailed explanation',
            'ai_key_factors': ['factor1', 'factor2', ...],
            'news_count': int,
            'news_headlines': ['headline1', 'headline2', ...]
        }
    """
    print(f"🤖 Fetching news for {ticker}...")
    news = fetch_recent_news(ticker, days_back=2)

    print(f"📰 Found {len(news)} recent news articles")

    if news:
        print("   Headlines:")
        for i, n in enumerate(news[:3], 1):
            print(f"   {i}. {n['title'][:70]}...")

    print(f"🤖 Analyzing with Claude AI...")

    ai_result = analyze_with_ai(ticker, technical_analysis, news, entry_price, current_price, loss_pct)

    print(f"   AI Recommendation: {ai_result['recommendation']} (Confidence: {ai_result['confidence']})")
    print(f"   Reasoning: {ai_result['reasoning'][:100]}...")

    return {
        'ai_recommendation': ai_result['recommendation'],
        'ai_confidence': ai_result['confidence'],
        'ai_reasoning': ai_result['reasoning'],
        'ai_key_factors': ai_result['key_factors'],
        'news_count': len(news),
        'news_headlines': [n['title'] for n in news[:3]]
    }
