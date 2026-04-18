import pandas as pd
import pandas_ta as ta
from tqdm import tqdm
from openbb import obb
import time

def run_logic():
    print("--- 🇮🇳 ALPHA-ORACLE: NIFTY 500 BATCH SCANNER ---")
    
    # 1. Load the "Full Universe" from your Phase 4b data
    try:
        token_df = pd.read_csv("data/nse_tokens.csv")
        # We take the top 500 (or however many you want) 
        # based on the order in the file
        full_universe = token_df['clean_symbol'].tolist()[:500] 
    except:
        print("❌ Token file missing. Run update_tokens.py first.")
        return pd.DataFrame()

    matches = []
    
    # 2. Batch Processing (Groups of 50 to protect 16GB RAM)
    batch_size = 50
    for i in range(0, len(full_universe), batch_size):
        batch = full_universe[i:i+batch_size]
        print(f"📦 Scanning Batch {i//batch_size + 1}...")

        for symbol in batch:
            try:
                # Append .NS for OpenBB/yfinance
                full_symbol = f"{symbol}.NS"
                
                # Fetch 30 days of data (faster than 50 days)
                df = obb.equity.price.historical(symbol=full_symbol, provider="yfinance", limit=30).to_df()
                
                # Momentum Logic
                df['sma20'] = ta.sma(df['close'], length=20)
                df['rsi'] = ta.rsi(df['close'], length=14)
                
                curr = df.iloc[-1]
                
                # 2026 Alpha Filter: Price > SMA20 AND RSI between 60-75 (not overbought)
                if curr['close'] > curr['sma20'] and 60 <= curr['rsi'] <= 75:
                    matches.append({
                        "Ticker": symbol,
                        "Price": round(curr['close'], 2),
                        "RSI": round(curr['rsi'], 1),
                        "Signal": "🔥 Momentum"
                    })
            except:
                continue
        
        # 3. The "Cool Down" (Wait 2 seconds between batches to avoid API blocks)
        time.sleep(2)

    return pd.DataFrame(matches)