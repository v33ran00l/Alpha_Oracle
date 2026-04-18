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

# --- 1. DYNAMIC MARKET PULSE (Hardened VIX Fix) ---
def fetch_live_market_data():
    try:
        # Fetch 1 month to ensure we have valid history to fill gaps
        data = yf.download(tickers="^NSEI ^BSESN INDIAVIX.NS", period="1mo", interval="1d", progress=False)
        
        # Multi-stage cleaning: Forward fill then pick the last row that isn't all NaN
        cleaned_df = data['Close'].ffill().dropna()
        if cleaned_df.empty: return "17.20", "24,350", "80,305"
        
        last = cleaned_df.iloc[-1]
        prev = cleaned_df.iloc[-2]

        def format_val(val, p_val, is_vix=False):
            diff = val - p_val
            color = "🟢" if (diff >= 0 if not is_vix else diff <= 0) else "🔴"
            return f"{round(val, 2 if is_vix else 0)} ({color})"

        return (format_val(last['INDIAVIX.NS'], prev['INDIAVIX.NS'], True), 
                format_val(last['^NSEI'], prev['^NSEI']), 
                format_val(last['^BSESN'], prev['^BSESN']))
    except:
        return "17.20 (Stable)", "24,350", "80,305"

# --- 2. JOURNAL & ORDER LOGIC ---
def log_trade_local(ticker, qty, exec_price, stop_loss, reason, order_id):
    log_dir = os.path.join(os.getcwd(), "data")
    log_file = os.path.join(log_dir, "trade_journal.csv")
    os.makedirs(log_dir, exist_ok=True)
    
    new_entry = {
        "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Stock": ticker,
        "Qty": int(qty),
        "Selection_Price": state.current_selection_ltp,
        "Execution_Price": float(exec_price),
        "Stop_Loss": float(stop_loss),
        "Reason": str(reason),
        "Order_ID": str(order_id)
    }
    pd.DataFrame([new_entry]).to_csv(log_file, mode='a', index=False, header=not os.path.exists(log_file))

def fetch_combined_logs():
    """Fetches BOTH local journal and live broker orders."""
    # A. Local Journal
    log_file = os.path.join(os.getcwd(), "data", "trade_journal.csv")
    journal_df = pd.read_csv(log_file).iloc[::-1] if os.path.exists(log_file) else pd.DataFrame([{"Status": "No Journal Entries"}])
    
    # B. Broker Orders
    order_df = pd.DataFrame([{"Status": "Broker Offline"}])
    if state.api:
        try:
            ob = state.api.orderBook()
            if ob['status'] and ob['data']:
                order_df = pd.DataFrame(ob['data'])[['tradingsymbol', 'orderstatus', 'quantity', 'price', 'text', 'orderid']]
                order_df = order_df.iloc[::-1] # Newest first
        except: order_df = pd.DataFrame([{"Status": "API Error fetching orders"}])
    
    return journal_df, order_df

# --- 3. BROKER CORE ---
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
    except Exception as e: return f"⚠️ ERROR: {str(e)[:20]}", "N/A", "N/A", "N/A", "₹0"

def fetch_portfolio_clean():
    if not state.api: return pd.DataFrame([{"Message": "Connect First"}])
    try:
        h_resp = state.api.holding()
        if h_resp.get('status') and h_resp.get('data'):
            df = pd.DataFrame(h_resp['data'])
            # Ensure numbers are treated as numbers
            df['ltp'] = pd.to_numeric(df['ltp'], errors='coerce')
            df['averageprice'] = pd.to_numeric(df['averageprice'], errors='coerce')
            df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce')
            
            df['P&L'] = ((df['ltp'] - df['averageprice']) * df['quantity']).fillna(0).round(0).astype(int)
            df['Status'] = df['P&L'].apply(lambda x: "🟢 PROFIT" if x >= 0 else "🔴 LOSS")
            return df[['tradingsymbol', 'quantity', 'averageprice', 'ltp', 'P&L', 'Status']]
        return pd.DataFrame([{"Status": "No holdings."}])
    except: return pd.DataFrame([{"Error": "API Fail"}])

def place_order_hardened(ticker, qty, price, stop_loss, reason):
    if not state.api: return "❌ System Offline"
    if not reason or len(reason) < 3: return "⚠️ Please provide a reason."
    try:
        df = pd.read_csv("data/nse_tokens.csv")
        token = str(df[df['clean_symbol'] == ticker.upper()].iloc[0]['token'])
        params = {
            "variety": "NORMAL", "tradingsymbol": f"{ticker}-EQ",
            "symboltoken": token, "transactiontype": "BUY", "exchange": "NSE",
            "ordertype": "LIMIT", "producttype": "DELIVERY", "duration": "DAY",
            "price": str(round(float(price), 2)), "quantity": str(int(qty)), "scripconsent": "YES" 
        }
        res = state.api.placeOrder(params)
        
        # IDENTIFY SUCCESS (Handle raw string or dict)
        oid = "FAILED"
        if isinstance(res, str) and len(res) > 5: oid = res
        elif isinstance(res, dict) and res.get('status'): oid = res['data']['script']
        
        if oid != "FAILED":
            log_trade_local(ticker, qty, price, stop_loss, reason, oid)
            return f"🚀 SUCCESS! Order {oid} logged."
        return f"❌ REJECTED: {res.get('message', 'Unknown Error')}"
    except Exception as e: return f"❌ Error: {str(e)}"

# --- 4. UI CONSTRUCTION ---
custom_css = """
.gradio-container { background-color: #0b111b; color: #e2e8f0; }
h1 { text-align: center; color: #00d4ff; font-weight: 800; font-size: 20px; margin: 0; padding: 10px; }
.header-row { background: #161b22; border-radius: 8px; border: 1px solid #30363d; padding: 5px; }
.small-text input { font-size: 13px !important; text-align: center; }
"""

with gr.Blocks(title="Alpha-Oracle", css=custom_css, theme=gr.themes.Soft()) as demo:
    gr.HTML("<h1>🏛️ ALPHA-ORACLE COMMAND CENTER</h1>")
    
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
                strategy = gr.Dropdown(choices=["india_scanner"], value="india_scanner", label="Universe", scale=2)
                run_btn = gr.Button("🔍 SCAN NIFTY 500", variant="secondary", scale=1)
            scanner_results = gr.Dataframe(label="Targets", interactive=False)
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
            gr.Markdown("### 📒 Local Trade Journal (Reasoning)")
            journal_table = gr.Dataframe()
            gr.Markdown("---")
            gr.Markdown("### 📡 Live Broker Order Book (Execution Status)")
            order_table = gr.Dataframe()

    # --- LOGIC ---
    login_btn.click(fn=broker_login, outputs=[status_box, vix_box, nifty_box, sensex_box, cash_box])
    run_btn.click(fn=lambda s: importlib.import_module(f"scripts.{s}").run_logic(), inputs=strategy, outputs=scanner_results)
    
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
    refresh_p_btn.click(fn=fetch_portfolio_clean, outputs=portfolio_table)
    refresh_j_btn.click(fn=fetch_combined_logs, outputs=[journal_table, order_table])
    confirm_btn.click(fn=place_order_hardened, inputs=[exec_ticker, exec_qty, exec_limit, exec_sl, exec_reason], outputs=exec_log)

if __name__ == "__main__":
    demo.launch(server_port=7861)