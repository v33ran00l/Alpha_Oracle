import pandas as pd
import pandas_ta as ta
from tqdm import tqdm
from openbb import obb
import os

def run_logic():
    """
    NSE Momentum Scanner (2026 Edition)
    Logic: Price > 20 SMA AND RSI > 60 (Standard Momentum)
    """
    print("--- 🇮🇳 ALPHA-ORACLE: NSE SCANNER ACTIVE ---")
    
    # High-Conviction NSE Watchlist (Nifty Blue-Chips)
    # Note: Using .NS suffix for Indian Stocks
    symbols = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", 
        "SBIN.NS", "BHARTIARTL.NS", "LICI.NS", "ITC.NS", "HINDUNILVR.NS",
        "TATAMOTORS.NS", "ADANIENT.NS", "SUNPHARMA.NS", "AXISBANK.NS", "TITAN.NS"
    ]

    matches = []

    for symbol in tqdm(symbols):
        try:
            # Fetch data via yfinance provider (Standard for NSE in 2026)
            df = obb.equity.price.historical(symbol=symbol, provider="yfinance", limit=50).to_df()
            
            # Technical Indicators
            df['sma20'] = ta.sma(df['close'], length=20)
            df['rsi'] = ta.rsi(df['close'], length=14)
            
            curr = df.iloc[-1]
            
            # The Logic Check
            if curr['close'] > curr['sma20'] and curr['rsi'] > 60:
                matches.append({
                    "Ticker": symbol.replace(".NS", ""),
                    "Price": round(curr['close'], 2),
                    "RSI": round(curr['rsi'], 1),
                    "Condition": "✅ Momentum Breakout"
                })
        except Exception:
            continue # Skip if data fetch fails for a ticker

    # If no matches, return an empty but structured dataframe
    if not matches:
        return pd.DataFrame(columns=["Ticker", "Price", "RSI", "Condition"])
        
    return pd.DataFrame(matches)