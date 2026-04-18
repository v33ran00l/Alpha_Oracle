import requests
import pandas as pd
import os
import io
import zipfile
import json

def update_instrument_list():
    """
    Phase 4b (2026 Patched): The Tokenizer.
    Uses the corrected OpenAPI_File path for Angel One.
    """
    # CORRECTED 2026 URL
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    
    print(f"📡 Connecting to: {url}")
    
    try:
        response = requests.get(url, timeout=30)
        
        # Security & Status Check
        if response.status_code != 200:
            print(f"❌ Server Error: {response.status_code}. The URL might have changed again.")
            return False

        # Check if the response is binary (ZIP) or plain text (JSON)
        if response.content.startswith(b'PK'):
            print("📦 Decompressing instrument master...")
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                filename = z.namelist()[0]
                with z.open(filename) as f:
                    data = json.load(f)
        else:
            print("📄 Reading JSON data...")
            data = response.json()

        df = pd.DataFrame(data)
        print(f"📊 Total Instruments Found: {len(df)}")

        # --- ALPHA-ORACLE FILTERING ---
        # We only want NSE Equity (Standard Stocks)
        # Note: 'exch_seg' is the column for Exchange Segment
        filtered_df = df[
            (df['exch_seg'] == 'NSE') & 
            (df['instrumenttype'] == '') & 
            (df['symbol'].str.endswith('-EQ'))
        ].copy()

        # Clean "RELIANCE-EQ" to "RELIANCE"
        filtered_df['clean_symbol'] = filtered_df['symbol'].str.replace('-EQ', '')
        
        # Select only the columns needed for the scanner
        final_df = filtered_df[['clean_symbol', 'token', 'lotsize', 'tick_size']]
        
        os.makedirs("data", exist_ok=True)
        final_df.to_csv("data/nse_tokens.csv", index=False)
        
        print(f"✅ SUCCESS: {len(final_df)} NSE Tokens saved to data/nse_tokens.csv")
        return True

    except Exception as e:
        print(f"❌ Tokenizer Error: {str(e)}")
        return False

if __name__ == "__main__":
    update_instrument_list()