import random
import csv
import os
import math
from datetime import datetime

# --- 1. INITIAL MARKET STATE ---
BASE_PRICES = {
    "TotalEnergies": {"price": 100.0, "sector": "Energy", "region": "EU"},
    "ExxonMobil": {"price": 100.0, "sector": "Energy", "region": "USA"},
    "CNOOC": {"price": 100.0, "sector": "Energy", "region": "WORLD"},
    
    "Siemens": {"price": 100.0, "sector": "Industry", "region": "EU"},
    "Caterpillar": {"price": 100.0, "sector": "Industry", "region": "USA"},
    "Toyota": {"price": 100.0, "sector": "Industry", "region": "WORLD"},
    
    "Nvidia": {"price": 100.0, "sector": "Tech", "region": "USA"},
    "ASML": {"price": 100.0, "sector": "Tech", "region": "EU"},
    "Samsung": {"price": 100.0, "sector": "Tech", "region": "WORLD"},
    
    "Rheinmetall": {"price": 100.0, "sector": "Defense", "region": "EU"},
    "Lockheed_Martin": {"price": 100.0, "sector": "Defense", "region": "USA"},
    "Elbit_Systems": {"price": 100.0, "sector": "Defense", "region": "WORLD"},
    
    "Novartis": {"price": 100.0, "sector": "Health", "region": "EU"},
    "United_Health": {"price": 100.0, "sector": "Health", "region": "USA"},
    "AstraZeneca": {"price": 100.0, "sector": "Health", "region": "EU"},
    
    "Lotus_Bakeries": {"price": 100.0, "sector": "Consumer", "region": "EU"},
    "Nike": {"price": 100.0, "sector": "Consumer", "region": "USA"},
    "AB_Inbev": {"price": 100.0, "sector": "Consumer", "region": "EU"}
}

market_data = {k: v.copy() for k, v in BASE_PRICES.items()}
bitcoin_price = 50000.0
day_counter = 1
daily_volume = {ticker: 0 for ticker in market_data.keys()}
daily_volume["Bitcoin"] = 0

FILENAME = "market_history.csv"

# --- CORE FUNCTIONS ---

def load_save_state():
    global bitcoin_price, day_counter
    if not os.path.isfile(FILENAME):
        save_to_csv()
        return

    with open(FILENAME, mode='r') as csvfile:
        reader = list(csv.DictReader(csvfile))
        if reader:
            last_row = reader[-1]
            day_counter = int(last_row["Day"].replace("Day ", ""))
            for ticker in market_data.keys():
                market_data[ticker]["price"] = float(last_row[ticker])
            bitcoin_price = float(last_row["Bitcoin"])
            print(f"[*] Save state loaded. Resuming at Day {day_counter}.")

def calculate_etfs():
    etfs = {}
    sectors = ["Energy", "Industry", "Tech", "Defense", "Health", "Consumer"]
    for sector in sectors:
        stocks = [data["price"] for t, data in market_data.items() if data["sector"] == sector]
        etfs[f"ETF_{sector}"] = sum(stocks) / len(stocks)

    all_stocks = [data["price"] for t, data in market_data.items()]
    etfs["ETF_WORLD"] = sum(all_stocks) / len(all_stocks)
    
    eu_stocks = [data["price"] for t, data in market_data.items() if data["region"] == "EU"]
    usa_stocks = [data["price"] for t, data in market_data.items() if data["region"] == "USA"]
    etfs["ETF_EU"] = sum(eu_stocks) / len(eu_stocks)
    etfs["ETF_USA"] = sum(usa_stocks) / len(usa_stocks)
    
    return etfs

def save_to_csv():
    file_exists = os.path.isfile(FILENAME)
    etfs = calculate_etfs()
    row_data = {"Day": f"Day {day_counter}", "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    for ticker, data in market_data.items(): row_data[ticker] = round(data["price"], 2)
    row_data["Bitcoin"] = round(bitcoin_price, 2)
    for etf_name, etf_price in etfs.items(): row_data[etf_name] = round(etf_price, 2)
        
    headers = list(row_data.keys())
    with open(FILENAME, mode='a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        if not file_exists: writer.writeheader()
        writer.writerow(row_data)

def simulate_day(manual_shocks):
    global bitcoin_price
    for ticker, data in market_data.items():
        random_swing = random.uniform(-0.05, 0.05)
        
        # Anti-Pump Math: Influence caps at 20% regardless of volume size
        net_vol = daily_volume[ticker]
        volume_swing = (net_vol / (abs(net_vol) + 100.0)) * 0.20 
        
        shock = 1.0 + (manual_shocks.get(ticker, 0) / 100.0)
        shock += (manual_shocks.get(data["sector"], 0) / 100.0)
        shock += (manual_shocks.get(data["region"], 0) / 100.0)

        market_data[ticker]["price"] *= (1 + random_swing + volume_swing) * shock
        if market_data[ticker]["price"] < 1.0: market_data[ticker]["price"] = 1.0

    btc_random = random.uniform(-0.25, 0.25)
    btc_vol = (daily_volume["Bitcoin"] / (abs(daily_volume["Bitcoin"]) + 50.0)) * 0.40
    btc_shock = 1.0 + (manual_shocks.get("Bitcoin", 0) / 100.0)
    
    bitcoin_price *= (1 + btc_random + btc_vol) * btc_shock
    if bitcoin_price < 100: bitcoin_price = 100
    
    for key in daily_volume.keys(): daily_volume[key] = 0

def seed_market(days):
    global day_counter
    print(f"Seeding {days} days of history...")
    for _ in range(days):
        simulate_day({})
        save_to_csv()
        day_counter += 1
    print("Seeding complete.")

# --- INTERACTIVE LOOP ---
print("-" * 30)
print("MARKET ENGINE STARTING")
print("-" * 30)
load_save_state()

while True:
    cmd = input(f"[Day {day_counter}] > ").strip().split()
    if not cmd: continue
    action = cmd[0].lower()
    
    if action == "help":
        print("Commands: trade [t] [qty], shock [target] [%], next, status, seed [days], reset, exit")
        
    elif action == "trade":
        try:
            t, q = cmd[1], int(cmd[2])
            if t in daily_volume:
                daily_volume[t] += q
                print(f"Logged {q} for {t}")
            else: print("Ticker not found")
        except: print("Format: trade [ticker] [qty]")

    elif action == "next":
        shocks = {}
        s_input = input("Final shocks? (Target % / none) > ").strip().split()
        if s_input and s_input[0].lower() != "none":
            try: shocks[s_input[0]] = float(s_input[1])
            except: print("Invalid shock")
        
        day_counter += 1
        simulate_day(shocks)
        save_to_csv()
        print(f"Market closed. Day {day_counter} saved.")

    elif action == "status":
        etfs = calculate_etfs()
        print("\n--- INDICES ---")
        print(f"WORLD: {etfs['ETF_WORLD']:.2f} | USA: {etfs['ETF_USA']:.2f} | EU: {etfs['ETF_EU']:.2f}")
        print("\n--- STOCKS ---")
        for t, d in market_data.items(): print(f"{t:<15}: {d['price']:.2f}")
        print(f"Bitcoin        : {bitcoin_price:.2f}")

    elif action == "seed":
        try:
            days = int(cmd[1]) if len(cmd) > 1 else 100
            seed_market(days)
        except: print("Usage: seed [days]")

    elif action == "reset":
        if input("Password: ") == "fullresetstocks":
            market_data = {k: v.copy() for k, v in BASE_PRICES.items()}
            bitcoin_price = 50000.0
            day_counter = 1
            if os.path.exists(FILENAME): os.remove(FILENAME)
            save_to_csv()
            print("Market Reset.")
        else: print("Denied.")

    elif action == "exit":
        break