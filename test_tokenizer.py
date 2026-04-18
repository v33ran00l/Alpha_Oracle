import pandas as pd

def lookup_stock(symbol):
    try:
        df = pd.read_csv("data/nse_tokens.csv")
        # Ensure input is uppercase
        symbol = symbol.upper()
        
        result = df[df['clean_symbol'] == symbol]
        
        if not result.empty:
            token = result.iloc[0]['token']
            tick = result.iloc[0]['tick_size']
            print(f"🔍 Found {symbol}: Token={token}, Min Tick={tick}")
            return token
        else:
            print(f"⚠️ {symbol} not found in NSE Equity list.")
            return None
    except FileNotFoundError:
        print("❌ Token file missing. Run update_tokens.py first.")

# Test it
lookup_stock("RELIANCE")
lookup_stock("TCS")