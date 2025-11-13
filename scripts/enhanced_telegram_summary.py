"""
Enhanced Telegram Summary Functions
Add to scripts/telegram_bot.py or create new file
"""

def format_entry_with_ai_validation(positions_entered):
    """
    Format entered positions with AI validation

    positions_entered: List of dicts with:
    {
        'ticker': 'RELIANCE.NS',
        'entry_price': 2500.0,
        'quantity': 20,
        'capital': 50000,
        'technical_score': 75,
        'rs_rating': 90,
        'indicators': ['RSI', 'MACD', 'Volume'],
        'ai_agrees': True,
        'ai_confidence': 0.85,
        'ai_reasoning': "Strong momentum...",
        'ai_verdict': 'AGREE'
    }
    """

    if not positions_entered:
        return "No positions entered today"

    from scripts.ai_validator import get_verdict_emoji

    message = f"✅ **ENTERED {len(positions_entered)} POSITIONS**\n\n"

    agree_count = sum(1 for p in positions_entered if p.get('ai_agrees') == True)

    for i, pos in enumerate(positions_entered, 1):
        # Basic info
        message += f"{i}. 📈 **{pos['ticker']}** @ Rs.{pos['entry_price']:,.2f}\n"
        message += f"   Quantity: {pos['quantity']} shares = Rs.{pos['capital']:,.0f}\n"

        # Technical breakdown
        message += f"   Score: {pos['technical_score']} | RS: {pos['rs_rating']}\n"

        # Indicators fired
        indicators_str = ' + '.join(pos.get('indicators', []))
        message += f"   Signals: {indicators_str}\n"

        # AI validation
        if pos.get('ai_verdict'):
            emoji = get_verdict_emoji(pos['ai_verdict'])
            confidence_pct = int(pos.get('ai_confidence', 0.5) * 100)
            reasoning = pos.get('ai_reasoning', 'No reasoning provided')

            verdict_text = pos['ai_verdict'].title()
            message += f"   AI: {emoji} **{verdict_text}** ({confidence_pct}%) - \"{reasoning}\"\n"

        message += "\n"

    # AI agreement summary
    if any(p.get('ai_verdict') for p in positions_entered):
        agreement_pct = int((agree_count / len(positions_entered)) * 100)
        message += f"📊 **AI Agreement: {agree_count}/{len(positions_entered)} ({agreement_pct}%)**\n"

    return message


def send_daily_summary_enhanced(positions_entered, portfolio_metrics, trades_today, strategy='DAILY'):
    """
    Send enhanced daily summary with AI validation
    """

    from scripts.telegram_bot import send_telegram_message
    from datetime import datetime

    message = f"🤖 **{strategy} TRADING SUMMARY**\n"
    message += f"📅 {datetime.now().strftime('%d %b %Y, %H:%M')}\n"
    message += "=" * 40 + "\n\n"

    # Positions entered with AI validation
    if positions_entered:
        message += format_entry_with_ai_validation(positions_entered)
        message += "\n"

    # Portfolio metrics
    message += f"💰 **Capital Deployed:** Rs.{sum(p['capital'] for p in positions_entered):,.0f}\n"
    message += f"📊 **Active Positions:** {portfolio_metrics.get('total_positions', 0)}\n"
    message += f"📈 **Portfolio P&L:** Rs.{portfolio_metrics.get('total_unrealized_pnl', 0):,.2f}\n"

    # Trades executed
    if trades_today:
        message += f"🔄 **Trades Executed:** {len(trades_today)}\n"

    message += "\n" + "=" * 40

    send_telegram_message(message)

    return message
