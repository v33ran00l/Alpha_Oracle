import pandas as pd
import pandas_ta as ta
import time
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

def scan_stock_angel(api, symbol, token, index, total):
    """Worker function with LIVE logging."""
    try:
        # Progress heartbeat for the terminal
        if index % 10 == 0:
            print(f"📡 [{index}/{total}] Scanning: {symbol}...")

        to_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        from_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d %H:%M")
        
        response = api.getCandleData({
            "exchange": "NSE",
            "symboltoken": str(token),
            "interval": "ONE_DAY",
            "fromdate": from_date,
            "todate": to_date
        })
        
        if not response.get('status') or not response.get('data'): 
            return None
        
        df = pd.DataFrame(response['data'], columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].apply(pd.to_numeric)
        
        if len(df) < 200: return None

        # --- PPC LOGIC ---
        df['turnover'] = df['close'] * df['volume']
        # SMA Turnover (10 Cr filter)
        sma_20_to = df['turnover'].rolling(20).mean().iloc[-1]
        sma_100_to = df['turnover'].rolling(100).mean().iloc[-1]
        
        if not (sma_20_to > 100000000 and sma_100_to > 100000000):
            return None

        # Indicators
        df['sma200'] = ta.sma(df['close'], length=200)
        atr100 = ta.atr(df['high'], df['low'], df['close'], length=100).iloc[-1]
        tr = ta.true_range(df['high'], df['low'], df['close']).iloc[-1]
        v_sma20 = ta.sma(df['volume'], length=20).iloc[-1]

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        # Breakout Conditions
        f_vol = curr['volume'] > v_sma20 * 1.5
        f_atr = tr > atr100 * 1.5
        f_trend = curr['close'] > df['sma200'].iloc[-1]
        
        if all([f_vol, f_atr, f_trend, curr['close'] > prev['close']]):
            print(f"🔥 [MATCH FOUND]: {symbol} at ₹{curr['close']}")
            return {
                "Ticker": symbol,
                "Price": round(curr['close'], 2),
                "Signal": "🚀 PPC BREAKOUT"
            }
    except Exception as e:
        return None
    return None

def run_logic(api_instance):
    print("\n" + "="*50)
    print("🛰️  ALPHA-ORACLE: UNIVERSAL PPC SCANNER v2.0")
    print("="*50)
    
    try:
        token_df = pd.read_csv("data/nse_tokens.csv")
        universe = token_df[['clean_symbol', 'token']].values.tolist()
        total_stocks = len(universe)
        print(f"📋 Loaded {total_stocks} stocks from local tokens.")
    except:
        return pd.DataFrame([{"Error": "Tokens Missing"}])

    matches = []
    
    # We use as_completed to see results as they happen
    with ThreadPoolExecutor(max_workers=6) as executor:
        # Create a list of tasks
        futures = {executor.submit(scan_stock_angel, api_instance, s[0], s[1], i, total_stocks): s for i, s in enumerate(universe)}
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                matches.append(result)
            
            # Tiny sleep to stay within Angel One Rate Limits (3 req/sec)
            time.sleep(0.35) 
            
    print(f"\n✅ SCAN COMPLETE. Found {len(matches)} matches.")
    return pd.DataFrame(matches)