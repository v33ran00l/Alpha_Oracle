import requests
import os
from googlesearch import search

def get_live_context(ticker):
    """Fetches the latest 3 headlines for the stock to bypass knowledge cutoff."""
    query = f"{ticker} stock news NSE India today"
    headlines = []
    try:
        # Grabbing real-time results from the web
        for url in search(query, num_results=3):
            headlines.append(url)
        return "\n".join(headlines)
    except:
        return "No live news found. Relying on technical data only."

def analyze_with_gemma4(ticker, ltp, rsi):
    """The Oracle's Reasoning Engine using Gemma 4:e4b."""
    news_context = get_live_context(ticker)
    
    # We provide the 'Internet Data' in the prompt
    prompt = f"""
    [SYSTEM: FINANCIAL ANALYST MODE]
    You are an expert SEBI-certified analyst. 
    
    CURRENT MARKET DATA:
    - Stock: {ticker}
    - Current Price (LTP): ₹{ltp}
    - RSI: {rsi}
    - Recent News/Links: {news_context}
    
    TASK: Analyze if this is a safe Momentum entry. 
    Check if the stock is overextended (RSI > 75) or if news is negative.
    Verdicts: BULLISH, BEARISH, or NEUTRAL. Max 2 sentences.
    """
    
    try:
        # CRITICAL: Pointing to your local Gemma 4 model
        r = requests.post("http://localhost:11434/api/generate", 
                          json={"model": "gemma4:e4b", "prompt": prompt, "stream": False}, 
                          timeout=120)
        return r.json().get("response", "AI Reasoning Failed.")
    except Exception as e:
        return f"🤖 Gemma 4 Connection Error: {str(e)}"