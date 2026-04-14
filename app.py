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

# --- 3. DATA RECOVERY LOGIC (FOR CLOUD SURVIVAL) ---
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
    df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
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
        new_row = {"Date": (last_date + pd.Timedelta(days=1)).strftime('%Y-%m-%d'), "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
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

st.sidebar.title("Wolf Brokerage")
tab_m, tab_b, tab_p, tab_a = st.tabs(["🌎 Market", "💹 Trade", "💼 Portfolio", "⚙️ Admin"])

# --- TAB: MARKET ---
with tab_m:
    st.header(curr_p['Date'])
    m1, m2 = st.columns(2)
    btc_chg = ((float(curr_p['Bitcoin']) - float(prev_p['Bitcoin']))/float(prev_p['Bitcoin']))*100
    m1.metric("BITCOIN", f"${float(curr_p['Bitcoin']):,.0f}", f"{btc_chg:+.1f}%")
    m2.metric("WORLD", f"${float(curr_p['ETF_WORLD']):,.1f}")
    df_f = df.tail(30)
    st.plotly_chart(px.line(df_f, x="Date", y=['ETF_USA', 'ETF_EU', 'ETF_WORLD'], template="plotly_dark").update_layout(height=300, margin=dict(l=0,r=0,t=10,b=0)), use_container_width=True)

# --- TAB: TRADE ---
with tab_b:
    team = st.selectbox("Team Account:", TEAMS)
    asset = st.selectbox("Stock/ETF:", ALL_ASSETS)
    p_now = float(curr_p[asset]); cash = float(ports[team]['Cash']); owned = ports[team]['Holdings'][asset]
    st.write(f"💰 Cash: **${cash:,.0f}** | 📦 Owned: **{owned}**")
    side = st.radio("Action", ["Buy", "Sell"], horizontal=True)
    qty = st.number_input("Shares:", min_value=1, step=1)
    if st.button(f"EXECUTE {side.upper()} (${qty * p_now:,.2f})", type="primary"):
        if side == "Buy" and cash >= (qty * p_now):
            ports[team]['Cash'] -= (qty * p_now); ports[team]['Holdings'][asset] += qty; ports[team]['DailyVolume'][asset] += qty
            with open(PORTFOLIO_FILE, 'w') as f: json.dump(ports, f, indent=4); st.rerun()
        elif side == "Sell" and owned >= qty:
            ports[team]['Cash'] += (qty * p_now); ports[team]['Holdings'][asset] -= qty; ports[team]['DailyVolume'][asset] -= qty
            with open(PORTFOLIO_FILE, 'w') as f: json.dump(ports, f, indent=4); st.rerun()

# --- TAB: PORTFOLIO ---
with tab_p:
    for t in TEAMS:
        with st.expander(f"🛡️ {t}"):
            c_now = float(ports[t]['Cash']); h_val = sum([ports[t]['Holdings'][a] * float(curr_p[a]) for a in ALL_ASSETS])
            st.metric("Net Worth", f"${(c_now + h_val):,.0f}")
            st.write(f"Cash: ${c_now:,.0f}")

# --- TAB: ADMIN (WITH CLOUD RECOVERY) ---
with tab_a:
    st.subheader("Day Management")
    if st.button("🔔 ADVANCE NEXT DAY", type="primary"):
        advance_market(); st.rerun()
    if st.button("🌱 SEED 100 DAYS"):
        advance_market(days=100); st.rerun()
    
    st.divider()
    st.subheader("💾 Cloud Recovery (DO THIS EVERY NIGHT)")
    st.write("Because the cloud resets, copy these texts and save them in your phone's Notes app.")
    
    st.text_area("Market CSV Data (Copy this)", df.to_csv(index=False), height=100)
    st.text_area("Portfolio JSON Data (Copy this)", json.dumps(ports), height=100)
    
    st.divider()
    st.write("Restore from backup:")
    m_input = st.text_area("Paste Market CSV here to Restore")
    p_input = st.text_area("Paste Portfolio JSON here to Restore")
    if st.button("Restore Backup"):
        if m_input: 
            with open(MARKET_FILE, "w") as f: f.write(m_input)
        if p_input: 
            with open(PORTFOLIO_FILE, "w") as f: f.write(p_input)
        st.success("Data Restored!"); st.rerun()