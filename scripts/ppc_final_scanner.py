import sys
import io
import os
import pandas as pd
import pandas_ta as ta
from tqdm import tqdm
import warnings
from openbb import obb

# 1. Force UTF-8 encoding for Windows background processes
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
warnings.filterwarnings("ignore")

def run_logic():
    """
    Module B: The Logic Processor [cite: 5, 6]
    This function is the 'Brain' that the Alpha-Oracle UI will trigger.
    """
    print("--- PPC PRO SCANNER STARTING ---")
    
    # 2. Define the Universe (Top 500 US Stocks)
    print("Fetching market data...")
    try:
        # Utilizing OpenBB v4 Platform for standardized data 
        universe = obb.equity.search("", provider="sec").to_df()
        symbols = [s for s in universe['symbol'].head(500).tolist() if s.isalpha()]
    except Exception as e:
        print(f"Provider error: {e}. Using fallback blue-chip list.")
        symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "GOOGL", "AMZN", "NFLX", "AVGO"]

    matches = []
    
    # 3. Processing Logic
    print(f"Analyzing {len(symbols)} tickers...")
    for symbol in tqdm(symbols, desc="Scanning"):
        try:
            # Fetch historical data via local OpenBB API connection [cite: 4]
            df = obb.equity.price.historical(symbol=symbol, provider="yfinance", limit=250).to_df()
            
            if len(df) < 200:
                continue
            
            # Technical Indicators using pandas_ta
            df['sma20'] = ta.sma(df['close'], length=20)
            df['sma50'] = ta.sma(df['close'], length=50)
            df['sma200'] = ta.sma(df['close'], length=200)
            df['rsi'] = ta.rsi(df['close'], length=14)
            df['vol_sma5'] = ta.sma(df['volume'], length=5)
            
            curr = df.iloc[-1]
            
            # PPC Logic Criteria (Signal-to-Noise Compression) [cite: 2]
            price_trend = curr['close'] > curr['sma20'] > curr['sma50'] > curr['sma200']
            momentum = curr['rsi'] > 60
            volume_spike = curr['volume'] > curr['vol_sma5']
            
            if price_trend and momentum and volume_spike:
                matches.append({
                    "Ticker": symbol,
                    "Price": round(curr['close'], 2),
                    "RSI": round(curr['rsi'], 1),
                    "Vol_Ratio": round(curr['volume'] / curr['vol_sma5'], 2)
                })
                print(f" MATCH: {symbol}")
                
        except Exception:
            continue

    # 4. Return Data for UI 
    if matches:
        print(f"\nSUCCESS: {len(matches)} BREAKOUTS FOUND")
        results_df = pd.DataFrame(matches)
        
        # Save local backup 
        output_path = os.path.join("data", "ppc_results.json")
        results_df.to_json(output_path, orient="records", indent=4)
        
        return results_df
    else:
        print("\nNo stocks met the PPC criteria today.")
        return pd.DataFrame() # Returns empty DataFrame if no matches

if __name__ == "__main__":
    # Allows the script to still run standalone for testing
    run_logic()