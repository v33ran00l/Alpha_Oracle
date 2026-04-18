import gradio as gr
import pandas as pd
import sys, os, webbrowser, importlib.util, requests, pyotp
from datetime import datetime
from dotenv import load_dotenv
from SmartApi import SmartConnect
from openbb import obb

load_dotenv()

# --- GLOBAL BROKER STATE ---
class BrokerState:
    api = None
    cash_balance = "Click Login"

state = BrokerState()

# --- BROKER LOGIC ---
def broker_login():
    try:
        totp = pyotp.TOTP(os.getenv("ANGEL_TOTP_SECRET")).now()
        state.api = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))
        session = state.api.generateSession(os.getenv("ANGEL_CLIENT_ID"), os.getenv("ANGEL_PASSWORD"), totp)
        if session['status']:
            funds = state.api.rmsLimit()
            state.cash_balance = f"₹{funds['data']['net']}"
            return f"✅ ONLINE | Balance: {state.cash_balance}"
        return "❌ Login Failed"
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

def place_broker_order(ticker, qty, price):
    """Phase 5b: Final Execution Logic (SEBI 2026 Compliant)"""
    if not state.api: return "❌ Error: Not Logged In"
    try:
        token_df = pd.read_csv("data/nse_tokens.csv")
        match = token_df[token_df['clean_symbol'] == ticker.upper()]
        token = str(match.iloc[0]['token'])

        # Order Parameters
        order_params = {
            "variety": "NORMAL",
            "tradingsymbol": f"{ticker}-EQ",
            "symboltoken": token,
            "transactiontype": "BUY",
            "exchange": "NSE",
            "ordertype": "LIMIT",
            "producttype": "DELIVERY", # Safer for novices (no auto-squareoff)
            "duration": "DAY",
            "price": str(price),
            "quantity": str(int(qty))
        }
        
        order_id = state.api.placeOrder(order_params)
        return f"🚀 ORDER PLACED! ID: {order_id}"
    except Exception as e:
        return f"❌ Execution Error: {str(e)}"

# --- UI COMMAND CENTER ---
with gr.Blocks(title="Alpha-Oracle Command Center", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🏛️ Alpha-Oracle Command Center (Final MVP)")
    
    with gr.Row():
        login_btn = gr.Button("🔗 CONNECT ANGEL ONE", variant="primary")
        balance_display = gr.Textbox(label="Status", value=state.cash_balance, interactive=False)

    with gr.Tabs():
        with gr.Tab("🚀 Active Scanner"):
            with gr.Row():
                strategy_select = gr.Dropdown(choices=["india_scanner"], value="india_scanner", label="Strategy")
                run_btn = gr.Button("RUN GLOBAL SCAN")
            
            results_table = gr.Dataframe(label="Signals", interactive=False)

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 📊 Execution Panel")
                    sel_ticker = gr.Textbox(label="Ticker", interactive=False)
                    live_ltp = gr.Textbox(label="Live LTP", interactive=False)
                    order_qty = gr.Number(label="Qty", value=1)
                    limit_price = gr.Number(label="Limit Price")
                    execute_btn = gr.Button("🔥 CONFIRM & EXECUTE TRADE", variant="stop")
                    order_status = gr.Markdown("Ready for orders...")
                
                with gr.Column(scale=1):
                    gr.Markdown("### 🤖 AI Analyst (Gemma 3)")
                    ai_memo = gr.Textbox(label="Risk Assessment", lines=8, interactive=False)

    # --- LOGIC FLOWS ---
    login_btn.click(fn=broker_login, outputs=balance_display)
    run_btn.click(fn=lambda s: importlib.import_module(f"scripts.{s}").run_logic(), 
                  inputs=strategy_select, outputs=results_table)
    
    def on_select(evt: gr.SelectData):
        ticker = evt.value
        webbrowser.open(f"https://www.tradingview.com/chart/?symbol=NSE:{ticker}")
        
        # 1. Get Live Price
        token_df = pd.read_csv("data/nse_tokens.csv")
        token = str(token_df[token_df['clean_symbol'] == ticker.upper()].iloc[0]['token'])
        quote = state.api.ltpData("NSE", f"{ticker}-EQ", token)
        ltp = quote['data']['ltp'] if quote['status'] else 0
        
        # 2. Get AI Synthesis
        prompt = f"Risk check for {ticker} at ₹{ltp}. 2 sentences max."
        r = requests.post("http://localhost:11434/api/generate", 
                          json={"model": "gemma3:4b", "prompt": prompt, "stream": False}, timeout=100)
        memo = r.json().get("response", "AI Offline")
        
        return ticker, ltp, memo, round(float(ltp) + 0.05, 2)

    results_table.select(fn=on_select, outputs=[sel_ticker, live_ltp, ai_memo, limit_price])
    
    execute_btn.click(fn=place_broker_order, 
                      inputs=[sel_ticker, order_qty, limit_price], 
                      outputs=order_status)

if __name__ == "__main__":
    demo.launch(server_port=7861)