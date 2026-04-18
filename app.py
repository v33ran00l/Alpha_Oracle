import gradio as gr
import pandas as pd
import sys, os, webbrowser, importlib.util, requests, pyotp
from dotenv import load_dotenv
from SmartApi import SmartConnect
# Import your new Internet-Aware Agent
import scripts.agent_logic as oracle_brain 

load_dotenv()

# --- GLOBAL STATE ---
class BrokerState:
    api = None
    cash = "Connect First"
state = BrokerState()

# --- BROKER LOGIC ---
def broker_login():
    try:
        totp = pyotp.TOTP(os.getenv("ANGEL_TOTP_SECRET")).now()
        state.api = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))
        session = state.api.generateSession(os.getenv("ANGEL_CLIENT_ID"), os.getenv("ANGEL_PASSWORD"), totp)
        if session['status']:
            funds = state.api.rmsLimit()
            state.cash = f"₹{funds['data']['net']}"
            return f"🟢 ONLINE | Balance: {state.cash}"
        return "🔴 Login Failed"
    except Exception as e: return f"⚠️ Error: {str(e)}"

def place_order_final(ticker, qty, price):
    """FIXED: Now properly retrieves state for execution"""
    if not state.api: return "❌ System Offline: Connect Angel One"
    if not ticker or price <= 0: return "❌ Invalid Order Data"
    
    try:
        # 1. Get Token from local dict
        df = pd.read_csv("data/nse_tokens.csv")
        token = str(df[df['clean_symbol'] == ticker.upper()].iloc[0]['token'])
        
        # 2. SEBI 2026 Limit Order Packet
        params = {
            "variety": "NORMAL", "tradingsymbol": f"{ticker}-EQ",
            "symboltoken": token, "transactiontype": "BUY",
            "exchange": "NSE", "ordertype": "LIMIT",
            "producttype": "DELIVERY", "duration": "DAY",
            "price": str(price), "quantity": str(int(qty))
        }
        order_id = state.api.placeOrder(params)
        return f"🚀 SUCCESS! Order ID: {order_id}"
    except Exception as e: return f"❌ Failed: {str(e)}"

# --- UI ARCHITECTURE ---
with gr.Blocks(title="Alpha-Oracle 2026", theme=gr.themes.Soft()) as demo:
    gr.HTML("<h1 style='text-align: center; color: #00d4ff;'>🏛️ ALPHA-ORACLE: INTERNET-AWARE</h1>")
    
    # 1. Header (Static)
    with gr.Row():
        login_btn = gr.Button("🔗 INITIALIZE HANDSHAKE", variant="primary")
        status_box = gr.Textbox(label="System Status", value="🔴 DISCONNECTED", interactive=False)
        gr.Textbox(label="Regime", value="🟢 T+0 SETTLEMENT ACTIVE", interactive=False)

    with gr.Tabs() as tabs:
        # TAB 1: SCANNER
        with gr.Tab("🛰️ SCANNER"):
            scan_btn = gr.Button("🔍 SCAN NIFTY 500 (LIVE BATCH)")
            scanner_results = gr.Dataframe(label="Momentum Signals", interactive=False)
            
            with gr.Row():
                with gr.Column():
                    sel_ticker = gr.Textbox(label="Active Focus", interactive=False)
                    live_ltp = gr.Textbox(label="Live Price (LTP)", interactive=False)
                with gr.Column():
                    # COMPUTE CONTROL: AI only runs on demand
                    ai_ask_btn = gr.Button("🤖 ASK ORACLE (Search + Analysis)", variant="primary")
                    ai_memo = gr.Textbox(label="Agentic Reasoning", lines=6, interactive=False)

        # TAB 2: EXECUTION
        with gr.Tab("🔥 EXECUTION"):
            with gr.Row():
                exec_ticker = gr.Textbox(label="Ticker", interactive=False)
                exec_qty = gr.Number(label="Qty", value=1)
                exec_limit = gr.Number(label="Limit Price (SEBI 2026)")
            buy_confirm_btn = gr.Button("⚡ CONFIRM & SEND TO EXCHANGE", variant="stop")
            order_status = gr.Markdown("### Status: Waiting...")

        # TAB 3: PORTFOLIO
        with gr.Tab("💼 VAULT"):
            refresh_btn = gr.Button("🔄 FETCH LIVE P&L")
            portfolio_df = gr.Dataframe(label="Current Holdings")

    # --- DATA PIPELINE LOGIC ---
    login_btn.click(fn=broker_login, outputs=status_box)
    
    # Selecting a stock in the scanner tab now fills EVERYTHING
    def on_select(evt: gr.SelectData):
        ticker = evt.value
        # 1. Open TradingView
        webbrowser.open(f"https://www.tradingview.com/chart/?symbol=NSE:{ticker}")
        # 2. Get Live LTP
        try:
            df = pd.read_csv("data/nse_tokens.csv")
            token = str(df[df['clean_symbol'] == ticker.upper()].iloc[0]['token'])
            quote = state.api.ltpData("NSE", f"{ticker}-EQ", token)
            ltp = quote['data']['ltp']
        except: ltp = 0
        
        # 3. Auto-calc Limit
        limit = round(float(ltp) + 0.05, 2)
        return ticker, ltp, "", ticker, limit # Clear AI memo on new select

    scanner_results.select(fn=on_select, outputs=[sel_ticker, live_ltp, ai_memo, exec_ticker, exec_limit])

    # AI AGENTIC TRIGGER (Now with Internet Search)
    def run_agent(ticker, ltp):
        if not ticker: return "Select a stock first."
        # Call your new logic: Internet Search -> Gemma 3 Reasoning
        return oracle_brain.analyze_with_context(ticker, ltp, "N/A")

    ai_ask_btn.click(fn=run_agent, inputs=[sel_ticker, live_ltp], outputs=ai_memo)

    # FINAL EXECUTION TRIGGER
    buy_confirm_btn.click(fn=place_order_final, 
                          inputs=[exec_ticker, exec_qty, exec_limit], 
                          outputs=order_status)

demo.launch(server_port=7861)