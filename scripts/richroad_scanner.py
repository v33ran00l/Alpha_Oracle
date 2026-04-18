import sys
import io
import os
import pandas as pd
import pandas_ta as ta
from tqdm import tqdm
import warnings
from openbb import obb

# Force UTF-8 for Windows compatibility
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
warnings.filterwarnings("ignore")

def run_logic():
    """
    Module B: Richroad SWS Breakout Logic.
    Focuses on Volume Spread Analysis (VSA) and Bullish SMA Stacking.
    """
    print("--- RICHROAD SWS BREAKOUT SCANNER STARTING ---")
    
    # 1. Fetch Universe
    try:
        universe = obb.equity.search("", provider="sec").to_df()
        symbols = [s for s in universe['symbol'].head(500).tolist() if s.isalpha()]
    except:
        symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "GOOGL", "AMZN"]

    matches = []
    print(f"Scanning {len(symbols)} stocks for Trend + Volume Breakouts...")

    for symbol in tqdm(symbols, desc="Analyzing"):
        try:
            # Fetch 100 days of data
            df = obb.equity.price.historical(symbol=symbol, provider="yfinance", limit=100).to_df()
            if len(df) < 50: continue
            
            # --- RICHROAD LOGIC MATH ---
            df['sma20'] = ta.sma(df['close'], length=20)
            df['sma50'] = ta.sma(df['close'], length=50)
            df['vol_sma20'] = ta.sma(df['volume'], length=20)
            
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # Richroad Logic: 
            # 1. Price > 20 SMA
            # 2. 20 SMA > 50 SMA (Bullish Stack)
            # 3. Volume > 20-day Average
            # 4. Current Close > Previous High (VSA Breakout)
            price_above_sma = curr['close'] > curr['sma20']
            bullish_stack = curr['sma20'] > curr['sma50']
            volume_breakout = curr['volume'] > curr['vol_sma20']
            vsa_breakout = curr['close'] > prev['high']
            
            if price_above_sma and bullish_stack and volume_breakout and vsa_breakout:
                matches.append({
                    "Ticker": symbol,
                    "Price": round(curr['close'], 2),
                    "Vol_Jump": f"{curr['volume']/curr['vol_sma20']:.1f}x",
                    "Status": "Strong Breakout"
                })
        except:
            continue

    # 2. Results
    if matches:
        results_df = pd.DataFrame(matches)
        # Save to local data folder
        output_path = os.path.join("data", "richroad_results.json")
        results_df.to_json(output_path, orient="records")
        return results_df
    else:
        print("No Richroad breakouts found.")
        return pd.DataFrame()

if __name__ == "__main__":
    run_logic()