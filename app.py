import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import random
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Wolf Brokerage", layout="wide", initial_sidebar_state="collapsed")

# Mobile-Friendly Styling
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: white; }
    /* Larger buttons for thumbs */
    .stButton > button { 
        width: 100%; 
        height: 3rem; 
        font-weight: bold; 
        border-radius: 10px;
    }
    /* Metric styling for small screens */
    [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
    /* Remove padding for a tighter mobile look */
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ARCHITECTURE ---
MARKET_FILE = "market_history.csv"
PORTFOLIO_FILE = "portfolios.json"
TEAMS = ["Team Alpha", "Team Wolf"]
STARTING_CASH = 100000.0
START_DATE = "2020-01-01"

BASE_STOCKS = {
    "Nvidia": {"sector": "Tech", "region": "USA"}, "ASML": {"sector": "Tech", "region": "EU"}, "Samsung": {"sector": "Tech", "region": "WORLD"},
    "ExxonMobil": {"sector": "Energy", "region": "USA"}, "TotalEnergies": {"sector": "Energy", "region": "EU"}, "CNOOC": {"sector": "Energy", "region": "WORLD"},
    "Siemens": {"sector": "Industry", "region": "EU"}, "Caterpillar": {"sector": "Industry", "region": "USA"}, "Toyota": {"sector": "Industry", "region": "WORLD"},
    "Rheinmetall": {"sector": "Defense", "region": "EU"}, "Lockheed_Martin": {"sector": "Defense", "region": "USA"}, "Elbit_Systems": {"sector": "Defense", "region": "WORLD"},
    "Novartis": {"sector": "Health", "region": "EU"}, "United_Health": {"sector": "Health", "region": "USA"}, "AstraZeneca": {"sector": "Health", "region": "EU"},
    "Lotus_Bakeries": {"sector": "Consumer", "region": "EU"}, "Nike": {"sector": "Consumer", "region": "USA"}, "AB_Inbev": {"sector": "Consumer", "region": "EU"}
}
SECTORS = ["Tech", "Energy", "Industry", "Defense", "Health", "Consumer"]
REGIONS = ["USA", "EU", "WORLD"]
ETF_LIST = [f"ETF_{s}" for s in SECTORS] + [f"ETF_{r}" for r in REGIONS]
ALL_ASSETS = list(BASE_STOCKS.keys()) + ["Bitcoin"] + ETF_LIST

if 'pending_shocks' not in st.session_state: st.session_state.pending_shocks = []

# --- 3. CORE LOGIC (Same robust math as before) ---
def get_constituents(asset_name):
    if asset_name.startswith("ETF_"):
        cat = asset_name.replace("ETF_", "")
        if cat in SECTORS: return [s for s, d in BASE_STOCKS.items() if d["sector"] == cat]
        if cat in REGIONS: return list(BASE_STOCKS.keys()) if cat == "WORLD" else [s for s, d in BASE_STOCKS.items() if d["region"] == cat]
    return [asset_name]

def init_data():
    if not os.path.exists(MARKET_FILE):
        init_row = {"Date": START_DATE, "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Bitcoin": 50000.0}
        for s in BASE_STOCKS: init_row[s] = 100.0
        df = pd.DataFrame([init_row]); df = calculate_etfs(df); df.to_csv(MARKET_FILE, index=False)
    if not os.path.exists(PORTFOLIO_FILE):
        portfolios = {team: {"Cash": STARTING_CASH, "Holdings": {a: 0 for a in ALL_ASSETS}, "DailyVolume": {a: 0 for a in ALL_ASSETS}} for team in TEAMS}
        with open(PORTFOLIO_FILE, 'w') as f: json.dump(portfolios, f, indent=4)

def load_market():
    df = pd.read_csv(MARKET_FILE)
    if not df.empty:
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
        cols = df.columns.drop(['Date', 'Timestamp'])
        df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
    return df

def calculate_etfs(df):
    for i, row in df.iterrows():
        for s in SECTORS:
            s_list = [float(row[stk]) for stk in get_constituents(f"ETF_{s}")]
            df.at[i, f"ETF_{s}"] = sum(s_list) / len(s_list) if s_list else 0
        for r in REGIONS:
            r_list = [float(row[stk]) for stk in get_constituents(f"ETF_{r}")]
            df.at[i, f"ETF_{r}"] = sum(r_list) / len(r_list) if r_list else 0
    return df

def advance_market(days=1, manual_shocks=None):
    df = load_market(); ports = json.load(open(PORTFOLIO_FILE, 'r'))
    eff_shocks = {}
    if manual_shocks:
        for target, pct in manual_shocks.items():
            for c in get_constituents(target): eff_shocks[c] = eff_shocks.get(c, 0) + (pct / 100.0)
    for _ in range(days):
        last_date = pd.to_datetime(df.iloc[-1]['Date'])
        last_prices = df.iloc[-1]
        new_date = last_date + pd.Timedelta(days=1)
        new_row = {"Date": new_date.strftime('%Y-%m-%d'), "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        total_volume = {a: 0 for a in list(BASE_STOCKS.keys()) + ["Bitcoin"]}
        for team in TEAMS:
            for asset, vol in ports[team]["DailyVolume"].items():
                if vol != 0:
                    for c in get_constituents(asset): total_volume[c] += vol
            ports[team]["DailyVolume"] = {a: 0 for a in ALL_ASSETS}
        for asset in list(BASE_STOCKS.keys()) + ["Bitcoin"]:
            old_p = float(last_prices[asset])
            if asset == "Bitcoin":
                rand = random.uniform(-0.12, 0.12)
                if old_p > 150000: rand -= 0.03
                if old_p < 25000: rand += 0.03
            else: rand = random.uniform(-0.035, 0.035)
            vol_impact = (total_volume[asset] / (abs(total_volume[asset]) + 100)) * 0.12
            shock = 1.0 + eff_shocks.get(asset, 0)
            new_row[asset] = max(1.0, old_p * (1 + rand + vol_impact) * shock)
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df = calculate_etfs(df); df.to_csv(MARKET_FILE, index=False)
    with open(PORTFOLIO_FILE, 'w') as f: json.dump(ports, f, indent=4)

# --- 4. APP STARTUP ---
init_data(); df = load_market(); ports = json.load(open(PORTFOLIO_FILE, 'r'))
curr_p = df.iloc[-1]; prev_p = df.iloc[-2] if len(df) > 1 else curr_p
week_p = df.iloc[-7] if len(df) >= 7 else df.iloc[0]

st.sidebar.title("🐺 Wolf Admin")
st.sidebar.write(f"📅 **Date:** {curr_p['Date']}")
if st.sidebar.checkbox("Show Phone Install Tip"):
    st.sidebar.info("💡 **Install Tip:** Tap 'Share' (iOS) or 'Menu' (Android) and select 'Add to Home Screen' to use this as an app!")

tab_m, tab_b, tab_p, tab_a = st.tabs(["🌎 Market", "💹 Trade", "💼 Portfolio", "⚙️ Admin"])

# --- TAB: MARKET (Mobile optimized columns) ---
with tab_m:
    st.header(curr_p['Date'])
    m1, m2 = st.columns(2)
    btc_chg = ((float(curr_p['Bitcoin']) - float(prev_p['Bitcoin']))/float(prev_p['Bitcoin']))*100
    m1.metric("BITCOIN", f"${float(curr_p['Bitcoin']):,.0f}", f"{btc_chg:+.1f}%")
    m2.metric("WORLD", f"${float(curr_p['ETF_WORLD']):,.1f}")
    
    tf = st.select_slider("History Scale", options=["7D", "30D", "MAX"], value="30D")
    d_map = {"7D": 7, "30D": 30, "MAX": len(df)}
    df_f = df.tail(d_map[tf])
    
    st.plotly_chart(px.line(df_f, x="Date", y=['ETF_USA', 'ETF_EU', 'ETF_WORLD'], template="plotly_dark").update_layout(height=300, margin=dict(l=0,r=0,t=10,b=0)), use_container_width=True)
    
    with st.expander("📊 View Today's Full Price List"):
        all_chg = []
        for a in ALL_ASSETS:
            p_n, p_o = float(curr_p[a]), float(prev_p[a])
            all_chg.append({"Asset": a, "Price": p_n, "%": ((p_n-p_o)/p_o)*100})
        st.dataframe(pd.DataFrame(all_chg).sort_values("%", ascending=False), hide_index=True, use_container_width=True)

# --- TAB: TRADE (Big Inputs for Smartphones) ---
with tab_b:
    st.header("Trading Desk")
    team = st.selectbox("Who are you?", TEAMS)
    asset = st.selectbox("Stock/ETF:", ALL_ASSETS)
    
    st.plotly_chart(go.Figure(go.Scatter(x=df.tail(30)["Date"], y=df.tail(30)[asset], fill='tozeroy', line=dict(color='#00CC96'))).update_layout(height=250, template="plotly_dark", margin=dict(l=0,r=0,t=0,b=0)), use_container_width=True)
    
    p_now = float(curr_p[asset]); cash = float(ports[team]['Cash']); owned = ports[team]['Holdings'][asset]
    st.write(f"💰 Cash: **${cash:,.0f}** | 📦 Owned: **{owned}**")
    
    side = st.radio("Action", ["Buy", "Sell"], horizontal=True)
    qty = st.number_input("Shares:", min_value=1, step=1)
    total = qty * p_now
    
    if st.button(f"CONFIRM {side.upper()} (${total:,.2f})", type="primary"):
        if side == "Buy" and cash >= total:
            ports[team]['Cash'] -= total; ports[team]['Holdings'][asset] += qty; ports[team]['DailyVolume'][asset] += qty
            with open(PORTFOLIO_FILE, 'w') as f: json.dump(ports, f, indent=4)
            st.success("Trade Executed!"); st.rerun()
        elif side == "Sell" and owned >= qty:
            ports[team]['Cash'] += total; ports[team]['Holdings'][asset] -= qty; ports[team]['DailyVolume'][asset] -= qty
            with open(PORTFOLIO_FILE, 'w') as f: json.dump(ports, f, indent=4)
            st.success("Trade Executed!"); st.rerun()
        else: st.error("Ineligible Trade.")

# --- TAB: PORTFOLIO (Clean Summary) ---
with tab_p:
    for t in TEAMS:
        with st.expander(f"🛡️ {t} Summary", expanded=(t=="Team Alpha")):
            c_now = float(ports[t]['Cash']); h_val = 0; h_val_w = 0
            for a, q in ports[t]['Holdings'].items():
                if q > 0:
                    h_val += q * float(curr_p[a])
                    h_val_w += q * float(week_p[a])
            nw = c_now + h_val; nw_w = c_now + h_val_w
            w_diff = nw - nw_w; w_pct = (w_diff/nw_w)*100
            
            c1, c2 = st.columns(2)
            c1.metric("Net Worth", f"${nw:,.0f}")
            c2.metric("Weekly", f"${w_diff:+,.0f}", f"{w_pct:+.1f}%")
            st.write(f"Cash: ${c_now:,.0f}")

# --- TAB: ADMIN ---
with tab_a:
    if st.button("🔔 ADVANCE NEXT DAY", type="primary"):
        advance_market(manual_shocks={s['target']: s['pct'] for s in st.session_state.pending_shocks})
        st.session_state.pending_shocks = []; st.rerun()
    if st.button("🌱 SEED 100 DAYS"):
        with st.spinner("Processing..."): advance_market(days=100); st.rerun()
    st.divider()
    pw = st.text_input("Reset PW", type="password")
    if st.button("HARD RESET") and pw == "fullresetstocks":
        if os.path.exists(MARKET_FILE): os.remove(MARKET_FILE)
        if os.path.exists(PORTFOLIO_FILE): os.remove(PORTFOLIO_FILE)
        st.rerun()