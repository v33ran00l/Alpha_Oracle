import os
from dotenv import load_dotenv
from SmartApi import SmartConnect
import pyotp

# 1. Load your credentials
load_dotenv()

# 2. Setup TOTP
totp = pyotp.TOTP(os.getenv("ANGEL_TOTP_SECRET")).now()

# 3. Initialize Handshake
smartApi = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))

# 4. Login
session_data = smartApi.generateSession(
    os.getenv("ANGEL_CLIENT_ID"), 
    os.getenv("ANGEL_PASSWORD"), 
    totp
)

if session_data['status']:
    print("✅ HANDSHAKE SUCCESSFUL!")
    refresh_token = session_data['data']['refreshToken']
    
    # 5. Get Profile Details
    profile = smartApi.getProfile(refresh_token)
    if profile['status']:
        print(f"Logged in as: {profile['data']['name']}")
    
    # 6. Get Funds/Margin Details (CORRECTED FUNCTION NAME)
    funds = smartApi.rmsLimit() 
    if funds['status']:
        # In the 2026 SDK, rmsLimit doesn't always need the refresh_token explicitly
        # but it returns 'net' as your available cash
        print(f"Available Cash: ₹{funds['data']['net']}")
    else:
        print(f"❌ Could not fetch funds: {funds['message']}")
else:
    print(f"❌ Handshake Failed: {session_data['message']}")