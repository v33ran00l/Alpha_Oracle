# Create this as a new utility: scripts/agent_logic.py

import requests
from googlesearch import search # pip install googlesearch-python

def get_market_news(ticker):
    """Fetches the last 3 news headlines for the ticker."""
    query = f"{ticker} stock news NSE India"
    results = []
    try:
        # 2026 Search: Grabbing top 3 live headlines
        for j in search(query, num=3, stop=3, pause=2):
            results.append(j)
        return "\n".join(results)
    except:
        return "No recent news found."

def analyze_with_context(ticker, ltp, rsi):
    """The 'Oracle' reasoning engine."""
    # 1. Get Live News
    news = get_market_news(ticker)
    
    # 2. Build the 'Briefing Document'
    context = f"""
    INSTRUMENT: {ticker}
    LIVE PRICE: ₹{ltp}
    RSI (14): {rsi}
    RECENT NEWS/LINKS: 
    {news}
    
    TASK: Act as a SEBI-registered technical analyst. 
    Analyze the momentum based on the RSI and the current price. 
    Cross-reference with any news sentiment if available.
    Give a 2-sentence verdict: BULLISH, BEARISH, or NEUTRAL.
    """
    
    # 3. Send to Gemma 3
    try:
        r = requests.post("http://localhost:11434/api/generate", 
                          json={"model": "gemma3:4b", "prompt": context, "stream": False})
        return r.json().get("response", "Analysis Failed.")
    except:
        return "AI Brain Offline."