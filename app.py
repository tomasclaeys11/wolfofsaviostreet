import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import random
from datetime import datetime, timedelta

# --- 1. CONFIGURATION & STYLING ---
st.set_page_config(page_title="Wolf Brokerage Platform", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: white; }
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; border-bottom: 1px solid #333; }
    .stTabs [data-baseweb="tab"] { font-size: 1.2rem; font-weight: bold; }
    div[data-testid="stRadio"] > div { flex-direction: row; } 
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

if 'pending_shocks' not in st.session_state:
    st.session_state.pending_shocks = []

# --- 3. CORE FUNCTIONS ---
def get_constituents(asset_name):
    if asset_name.startswith("ETF_"):
        cat = asset_name.replace("ETF_", "")
        if cat in SECTORS: return [s for s, d in BASE_STOCKS.items() if d["sector"] == cat]
        if cat in REGIONS: 
            if cat == "WORLD": return list(BASE_STOCKS.keys())
            return [s for s, d in BASE_STOCKS.items() if d["region"] == cat]
    return [asset_name]

def init_data():
    if not os.path.exists(MARKET_FILE):
        init_row = {"Date": START_DATE, "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Bitcoin": 50000.0}
        for s in BASE_STOCKS: init_row[s] = 100.0
        df = pd.DataFrame([init_row])
        df = calculate_etfs(df)
        df.to_csv(MARKET_FILE, index=False)
        
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

def load_portfolios():
    with open(PORTFOLIO_FILE, 'r') as f: return json.load(f)

def save_portfolios(data):
    with open(PORTFOLIO_FILE, 'w') as f: json.dump(data, f, indent=4)

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
    df = load_market()
    ports = load_portfolios()
    
    effective_shocks = {}
    if manual_shocks:
        for target, pct in manual_shocks.items():
            for c in get_constituents(target):
                effective_shocks[c] = effective_shocks.get(c, 0) + (pct / 100.0)
    
    for _ in range(days):
        last_date = pd.to_datetime(df.iloc[-1]['Date'])
        last_prices = df.iloc[-1]
        new_date = last_date + pd.Timedelta(days=1)
        new_row = {"Date": new_date.strftime('%Y-%m-%d'), "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        
        total_volume = {a: 0 for a in list(BASE_STOCKS.keys()) + ["Bitcoin"]}
        for team in TEAMS:
            for asset, vol in ports[team]["DailyVolume"].items():
                if vol != 0:
                    for c in get_constituents(asset):
                        total_volume[c] += vol
            ports[team]["DailyVolume"] = {a: 0 for a in ALL_ASSETS}

        for asset in list(BASE_STOCKS.keys()) + ["Bitcoin"]:
            old_p = float(last_prices[asset])
            if asset == "Bitcoin":
                rand = random.uniform(-0.12, 0.12)
                if old_p > 150000: rand -= 0.03
                if old_p < 25000: rand += 0.03
            else:
                rand = random.uniform(-0.035, 0.035)

            vol_impact = (total_volume[asset] / (abs(total_volume[asset]) + 100)) * 0.12
            shock = 1.0 + effective_shocks.get(asset, 0)
            
            new_p = old_p * (1 + rand + vol_impact) * shock
            new_row[asset] = max(1.0, new_p)
            
        new_df = pd.DataFrame([new_row])
        df = pd.concat([df, new_df], ignore_index=True)
    
    df = calculate_etfs(df)
    df.to_csv(MARKET_FILE, index=False)
    save_portfolios(ports)

# --- 4. APP STARTUP ---
init_data()
df = load_market()
ports = load_portfolios()
current_prices = df.iloc[-1]
prev_prices = df.iloc[-2] if len(df) > 1 else current_prices
# Get price from 7 days ago (or first available)
weekly_prices = df.iloc[-7] if len(df) >= 7 else df.iloc[0]

current_date = current_prices['Date']

st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/NYSE_Euronext_logo.svg/1024px-NYSE_Euronext_logo.svg.png", width=200)
st.sidebar.title("Wolf Brokerage")
st.sidebar.write(f"**Date:** {current_date}")

tab_market, tab_brokerage, tab_portfolio, tab_admin = st.tabs([
    "🌍 Market Overview", "💹 Trading Desk", "💼 Portfolios", "⚙️ Engine/Admin"
])

# ==========================================
# TAB 1: MARKET OVERVIEW
# ==========================================
with tab_market:
    c_head1, c_head2 = st.columns([2, 1])
    with c_head1: st.header(f"Live Market Feed - {current_date}")
    with c_head2: timeframe = st.radio("Chart View", ["7D", "30D", "YTD", "MAX"], index=1)
    
    days_to_show = {"7D": 7, "30D": 30, "YTD": 365, "MAX": len(df)}
    df_filtered = df.tail(days_to_show[timeframe])
    
    changes = []
    for asset in ALL_ASSETS:
        p_now, p_prev = float(current_prices[asset]), float(prev_prices[asset])
        pct = ((p_now - p_prev) / p_prev) * 100 if p_prev != 0 else 0
        changes.append({"Asset": asset, "Price": p_now, "Change %": pct})
    
    change_df = pd.DataFrame(changes).sort_values("Change %", ascending=False)
    stocks_only_df = change_df[~change_df['Asset'].str.contains("ETF_")]
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("BITCOIN", f"${float(current_prices['Bitcoin']):,.0f}")
    m2.metric("WORLD INDEX", f"${float(current_prices['ETF_WORLD']):,.2f}")
    m3.metric("🔥 TOP GAINER", f"{stocks_only_df.iloc[0]['Asset']}", f"{float(stocks_only_df.iloc[0]['Change %']):+.2f}%")
    m4.metric("🩸 BIGGEST DROP", f"{stocks_only_df.iloc[-1]['Asset']}", f"{float(stocks_only_df.iloc[-1]['Change %']):+.2f}%")

    st.divider()
    
    c1, c2, c3 = st.columns(3)
    with c1: st.plotly_chart(px.line(df_filtered, x="Date", y=[f"ETF_{r}" for r in REGIONS], title="Regions", template="plotly_dark"), use_container_width=True)
    with c2: st.plotly_chart(px.line(df_filtered, x="Date", y=[f"ETF_{s}" for s in SECTORS], title="Sectors", template="plotly_dark"), use_container_width=True)
    with c3:
        def color_change(val): return 'color: green' if val > 0 else 'color: red'
        st.write("**Asset List**")
        st.dataframe(change_df.style.format({"Price": "${:.2f}", "Change %": "{:+.2f}%"}).map(color_change, subset=['Change %']), use_container_width=True, height=350, hide_index=True)

# ==========================================
# TAB 2: TRADING DESK
# ==========================================
with tab_brokerage:
    st.header("Brokerage Trading Desk")
    
    col_t, col_a, col_tf = st.columns([2, 2, 1])
    with col_t: selected_team = st.selectbox("Team Account:", TEAMS)
    with col_a: selected_asset = st.selectbox("Asset:", ALL_ASSETS)
    with col_tf: tf_trade = st.radio("History:", ["30D", "MAX"], index=1)

    df_trade = df.tail(30) if tf_trade == "30D" else df
    st.plotly_chart(go.Figure(go.Scatter(x=df_trade["Date"], y=df_trade[selected_asset], fill='tozeroy', mode='lines', line=dict(color='#00CC96'))).update_layout(template="plotly_dark", height=300), use_container_width=True)

    current_p = float(current_prices[selected_asset])
    team_cash = float(ports[selected_team]['Cash'])
    team_shares = int(ports[selected_team]['Holdings'][selected_asset])

    st.write(f"**Price:** ${current_p:,.2f} | **Cash:** ${team_cash:,.2f} | **Owned:** {team_shares}")

    c_act, c_qty = st.columns(2)
    with c_act: trade_type = st.radio("Action", ["Buy", "Sell"])
    with c_qty: qty = st.number_input("Shares", min_value=1, step=1)
        
    total_cost = qty * current_p
    st.info(f"**Estimated Order Value:** ${total_cost:,.2f}")
    
    if st.button("EXECUTE TRADE", type="primary", use_container_width=True):
        if trade_type == "Buy" and team_cash >= total_cost:
            ports[selected_team]['Cash'] -= total_cost
            ports[selected_team]['Holdings'][selected_asset] += qty
            ports[selected_team]['DailyVolume'][selected_asset] += qty
            save_portfolios(ports); st.success("Order Filled."); st.rerun()
        elif trade_type == "Sell" and team_shares >= qty:
            ports[selected_team]['Cash'] += total_cost
            ports[selected_team]['Holdings'][selected_asset] -= qty
            ports[selected_team]['DailyVolume'][selected_asset] -= qty
            save_portfolios(ports); st.success("Order Filled."); st.rerun()
        else: st.error("Invalid Order: Check funds/shares.")

# ==========================================
# TAB 3: PORTFOLIOS
# ==========================================
with tab_portfolio:
    st.header("Active Portfolios")
    col1, col2 = st.columns(2)
    for idx, team in enumerate(TEAMS):
        with col1 if idx == 0 else col2:
            st.subheader(team)
            cash = float(ports[team]['Cash'])
            h_data = []
            h_val_now = 0
            h_val_weekly = 0
            
            for a, q in ports[team]['Holdings'].items():
                if q > 0:
                    # Current value
                    p_now = float(current_prices[a])
                    v_now = q * p_now
                    h_val_now += v_now
                    
                    # Weekly value (what these shares were worth 7 days ago)
                    p_week = float(weekly_prices[a])
                    h_val_weekly += (q * p_week)
                    
                    chg = ((p_now - float(prev_prices[a]))/float(prev_prices[a]))*100 if float(prev_prices[a]) != 0 else 0
                    h_data.append({"Asset": a, "Shares": q, "Value": v_now, "Day %": chg})
            
            net_worth_now = cash + h_val_now
            # Note: We assume cash hasn't changed for the week calculation to isolate stock performance
            net_worth_weekly = cash + h_val_weekly
            
            weekly_diff = net_worth_now - net_worth_weekly
            weekly_pct = (weekly_diff / net_worth_weekly) * 100 if net_worth_weekly != 0 else 0
            
            # --- PORTFOLIO METRICS ---
            m_nw, m_weekly = st.columns(2)
            m_nw.metric("Net Worth", f"${net_worth_now:,.2f}")
            m_weekly.metric("7-Day Performance", f"${weekly_diff:+,.2f}", f"{weekly_pct:+.2f}%")
            
            st.write(f"**Purchasing Power (Cash):** ${cash:,.2f}")
            
            if h_data:
                st.dataframe(pd.DataFrame(h_data).style.format({"Value": "${:,.2f}", "Day %": "{:+.2f}%"}), use_container_width=True, hide_index=True)
            else: st.info("Portfolio Empty.")

# ==========================================
# TAB 4: ENGINE & ADMIN
# ==========================================
with tab_admin:
    st.header("Admin Controls")
    if st.button("🔔 ADVANCE CALENDAR (NEXT DAY)", type="primary", use_container_width=True):
        advance_market(days=1, manual_shocks={s['target']: s['pct'] for s in st.session_state.pending_shocks})
        st.session_state.pending_shocks = []; st.rerun()
    
    st.divider()
    st.subheader("⚡ Queue Shocks")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: target = st.selectbox("Shock Target", ALL_ASSETS)
    with c2: shock_pct = st.number_input("Shock %", value=0.0)
    if c3.button("Add to Queue"):
        st.session_state.pending_shocks.append({'target': target, 'pct': shock_pct}); st.rerun()
    if st.session_state.pending_shocks:
        st.warning("Queued: " + ", ".join([f"{s['target']} ({s['pct']}%)" for s in st.session_state.pending_shocks]))
        if st.button("Clear Shocks"): st.session_state.pending_shocks = []; st.rerun()

    st.divider()
    
    # --- ADDED: CLOUD BACKUP & RECOVERY ---
    st.subheader("💾 Cloud Recovery")
    st.write("Before leaving camp or going to sleep, copy these and save them in your phone's Notes app.")
    st.text_area("Market CSV Backup (Copy this)", df.to_csv(index=False), height=100)
    st.text_area("Portfolio JSON Backup (Copy this)", json.dumps(ports), height=100)

    st.write("Restore from your phone's notes:")
    m_in = st.text_area("Paste Market CSV here to Restore")
    p_in = st.text_area("Paste Portfolio JSON here to Restore")

    if st.button("Restore Backup"):
        if m_in and p_in:
            with open(MARKET_FILE, "w") as f: f.write(m_in)
            with open(PORTFOLIO_FILE, "w") as f: f.write(p_in)
            st.success("Data Restored!")
            st.rerun()
        else:
            st.error("Please paste both the CSV and JSON texts to restore.")
    
    st.divider()
    # --------------------------------------

    st.subheader("🌱 Simulation")
    s_days = st.number_input("Days to Simulate", min_value=1, value=100)
    if st.button(f"Run {s_days}-Day Simulation"):
        with st.spinner("Processing..."): advance_market(days=s_days); st.rerun()
        
    st.divider()
    pw = st.text_input("Reset Password", type="password")
    if st.button("HARD RESET GAME"):
        if pw == "fullresetstocks":
            for f in [MARKET_FILE, PORTFOLIO_FILE]: 
                if os.path.exists(f): os.remove(f)
            init_data(); st.rerun()