import gradio as gr
import pandas as pd
import os, webbrowser, importlib.util, requests, pyotp
import yfinance as yf
from datetime import datetime
from dotenv import load_dotenv
from SmartApi import SmartConnect
import scripts.agent_logic as oracle_brain 

load_dotenv()

# --- GLOBAL STATE ---
class BrokerState:
    api = None
    cash = "₹0"
    current_selection_ltp = 0
state = BrokerState()

# --- 1. DYNAMIC STRATEGY DISCOVERY ---
def get_all_scanners():
    """Scans the scripts folder for any file ending in _scanner.py"""
    try:
        files = os.listdir("scripts")
        # Filter for .py files that contain 'scanner'
        scanners = [f.replace(".py", "") for f in files if f.endswith("_scanner.py")]
        return scanners if scanners else ["india_scanner"]
    except:
        return ["india_scanner"]

# --- 2. MARKET & BROKER LOGIC ---
def fetch_live_market_data():
    try:
        data = yf.download(tickers="^NSEI ^BSESN INDIAVIX.NS", period="5d", interval="1d", progress=False)
        cleaned_df = data['Close'].ffill().dropna()
        last, prev = cleaned_df.iloc[-1], cleaned_df.iloc[-2]
        
        def format_val(val, p_val, is_vix=False):
            diff = val - p_val
            color = "🟢" if (diff >= 0 if not is_vix else diff <= 0) else "🔴"
            return f"{round(val, 2 if is_vix else 0)} ({color})"

        return (format_val(last['INDIAVIX.NS'], prev['INDIAVIX.NS'], True), 
                format_val(last['^NSEI'], prev['^NSEI']), 
                format_val(last['^BSESN'], prev['^BSESN']))
    except: return "17.20", "24,350", "80,305"

def broker_login():
    try:
        totp = pyotp.TOTP(os.getenv("ANGEL_TOTP_SECRET")).now()
        state.api = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))
        session = state.api.generateSession(os.getenv("ANGEL_CLIENT_ID"), os.getenv("ANGEL_PASSWORD"), totp)
        if session['status']:
            funds = state.api.rmsLimit()
            state.cash = f"₹{int(float(funds['data']['net']))}"
            vix, nifty, sensex = fetch_live_market_data()
            return "🟢 ONLINE", vix, nifty, sensex, state.cash
        return "🔴 FAILED", "N/A", "N/A", "N/A", "₹0"
    except Exception as e: return "⚠️ ERROR", "N/A", "N/A", "N/A", "₹0"

# --- 3. UI THEME ---
custom_css = """
.gradio-container { background-color: #0b111b; color: #e2e8f0; }
h1 { text-align: center; color: #00d4ff; font-weight: 800; font-size: 20px; margin: 0; padding: 10px; }
.header-row { background: #161b22; border-radius: 8px; border: 1px solid #30363d; padding: 5px; }
.small-text input { font-size: 13px !important; text-align: center; }
"""

with gr.Blocks(title="Alpha-Oracle", css=custom_css, theme=gr.themes.Soft()) as demo:
    gr.HTML("<h1>🏛️ ALPHA-ORACLE COMMAND CENTER</h1>")
    
    # --- DYNAMIC HEADER ---
    with gr.Row(elem_classes="header-row"):
        with gr.Column(scale=1, min_width=150):
            login_btn = gr.Button("🔗 INITIALIZE", variant="primary", size="sm")
            status_box = gr.Textbox(show_label=False, value="🔴 OFFLINE", interactive=False, elem_classes="small-text")
        with gr.Column(scale=1, min_width=100):
            vix_box = gr.Textbox(label="INDIA VIX", interactive=False, elem_classes="small-text")
        with gr.Column(scale=1, min_width=100):
            nifty_box = gr.Textbox(label="NIFTY 50", interactive=False, elem_classes="small-text")
        with gr.Column(scale=1, min_width=100):
            sensex_box = gr.Textbox(label="SENSEX", interactive=False, elem_classes="small-text")
        with gr.Column(scale=1, min_width=100):
            cash_box = gr.Textbox(label="CASH", interactive=False, elem_classes="small-text")

    with gr.Tabs():
        with gr.Tab("🛰️ SCANNER"):
            with gr.Row():
                # FIX: Dropdown now uses get_all_scanners() to find all your scripts
                strategy = gr.Dropdown(choices=get_all_scanners(), 
                                       label="Universe / Strategy", scale=2)
                run_btn = gr.Button("🔍 RUN STRATEGY SCAN", variant="secondary", scale=1)
            scanner_results = gr.Dataframe(label="Detected Opportunities", interactive=False)
            with gr.Row():
                with gr.Column():
                    sel_ticker = gr.Textbox(label="Ticker Focus", interactive=False)
                    live_ltp = gr.Textbox(label="Live LTP", interactive=False)
                    ai_ask_btn = gr.Button("🤖 ASK GEMMA 4", variant="primary")
                with gr.Column():
                    ai_memo = gr.Textbox(label="Oracle Reasoning", lines=5, interactive=False)

        with gr.Tab("💼 VAULT"):
            refresh_p_btn = gr.Button("🔄 REFRESH PORTFOLIO", variant="secondary")
            portfolio_table = gr.Dataframe()

        with gr.Tab("🔥 EXECUTION"):
            gr.Markdown("### ⚖️ Trade Journal")
            with gr.Row():
                exec_ticker = gr.Textbox(label="Symbol", interactive=False)
                exec_qty = gr.Number(label="Qty", value=1)
                exec_limit = gr.Number(label="Limit Price")
                exec_sl = gr.Number(label="Stop Loss")
            exec_reason = gr.Textbox(label="Reason for Trade", placeholder="Why this trade?", lines=2)
            confirm_btn = gr.Button("🚀 EXECUTE & LOG", variant="stop")
            exec_log = gr.Markdown("Waiting...")

        with gr.Tab("📋 JOURNAL & ORDERS"):
            refresh_j_btn = gr.Button("🔄 REFRESH ALL LOGS", variant="secondary")
            journal_table = gr.Dataframe(label="Local Journal")
            order_table = gr.Dataframe(label="Broker Order Book")

    # --- LOGIC INTEGRATION ---
    login_btn.click(fn=broker_login, outputs=[status_box, vix_box, nifty_box, sensex_box, cash_box])
    
    # This dynamically imports whichever scanner you pick from the dropdown
    def run_dynamic_scan(strategy_name):
        if not state.api:
            return pd.DataFrame([{"Error": "Initialize Handshake First!"}])

        spec = importlib.util.spec_from_file_location(strategy_name, f"scripts/{strategy_name}.py")
        if spec is None or spec.loader is None:
            return pd.DataFrame([{"Error": "Strategy module not found"}])

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # PASS the api to the scanner so it can fetch official data
        return module.run_logic(state.api)

    run_btn.click(fn=run_dynamic_scan, inputs=strategy, outputs=scanner_results)
    
    def on_select(evt: gr.SelectData):
        ticker = evt.value
        try:
            df = pd.read_csv("data/nse_tokens.csv")
            token = str(df[df['clean_symbol'] == ticker.upper()].iloc[0]['token'])
            quote = state.api.ltpData("NSE", f"{ticker}-EQ", token)
            ltp = float(quote['data']['ltp'])
            state.current_selection_ltp = ltp
        except: ltp = 0
        return ticker, str(ltp), "", ticker, round(ltp + 0.05, 2), round(ltp * 0.98, 2)

    scanner_results.select(fn=on_select, outputs=[sel_ticker, live_ltp, ai_memo, exec_ticker, exec_limit, exec_sl])
    ai_ask_btn.click(fn=oracle_brain.analyze_with_gemma4, inputs=[sel_ticker, live_ltp, gr.State(65)], outputs=ai_memo)
    
    # Direct function imports for Vault and Orders
    import app as main_logic # Ensure current logic is available
    refresh_p_btn.click(fn=lambda: main_logic.fetch_portfolio_clean(), outputs=portfolio_table)
    
    def refresh_logs_combined():
        j = main_logic.fetch_journal_log()
        o = main_logic.fetch_combined_logs()[1] # Fetch just the order book
        return j, o

    refresh_j_btn.click(fn=refresh_logs_combined, outputs=[journal_table, order_table])
    
    confirm_btn.click(fn=lambda t,q,p,s,r: main_logic.place_order_hardened(t,q,p,s,r), 
                     inputs=[exec_ticker, exec_qty, exec_limit, exec_sl, exec_reason], 
                     outputs=exec_log)

if __name__ == "__main__":
    demo.launch(server_port=7861)