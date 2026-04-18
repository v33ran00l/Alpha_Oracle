import os
import pandas as pd
from dotenv import load_dotenv
from SmartApi import SmartConnect
import pyotp

def fetch_ltp(symbol):
    """
    Phase 4c: Live Quote Handshake.
    Maps Symbol -> Token -> Live Price.
    """
    load_dotenv()
    
    # 1. Map Symbol to Token
    try:
        token_df = pd.read_csv("data/nse_tokens.csv")
        match = token_df[token_df['clean_symbol'] == symbol.upper()]
        
        if match.empty:
            print(f"⚠️ {symbol} not found in local Token list.")
            return None
        
        token = str(match.iloc[0]['token'])
        print(f"🔍 Mapping {symbol} to Token: {token}")

        # 2. Login to Angel One
        totp = pyotp.TOTP(os.getenv("ANGEL_TOTP_SECRET")).now()
        smartApi = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))
        smartApi.generateSession(os.getenv("ANGEL_CLIENT_ID"), os.getenv("ANGEL_PASSWORD"), totp)

        # 3. Fetch Live Price (LTP)
        # exch_seg 'NSE' and token are required
        quote = smartApi.ltpData("NSE", symbol + "-EQ", token)
        
        if quote['status']:
            ltp = quote['data']['ltp']
            print(f"✅ Live Price for {symbol}: ₹{ltp}")
            return ltp
        else:
            print(f"❌ Error fetching quote: {quote['message']}")
            return None

    except Exception as e:
        print(f"❌ Phase 4c Error: {str(e)}")
        return None

if __name__ == "__main__":
    # Test with a major Nifty stock
    fetch_ltp("RELIANCE")