import pandas as pd
import yfinance as yf
import numpy as np
import requests
import time
from datetime import datetime

# --- CONFIGURATION (24/7 CLOUD SCANNER — SCHLÄFT NIEMALS) ---
# Tragen Sie hier alle Assets ein, die Sie gleichzeitig überwachen wollen!
ASSETS = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "NQ=F"] 
INTERVAL = "1m"
NTFY_URL = "https://ntfy.sh"

# Speicher im RAM des Cloud-Servers für das Trade-Gedächtnis
trade_states = {asset: {"in_long": False, "in_short": False} for asset in ASSETS}

def scan_all_assets():
    global trade_states
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starte globalen Markt-Scan...")
    
    for asset in ASSETS:
        try:
            # Echte Live-Kursdaten von Yahoo Finance laden
            df = yf.download(asset, interval=INTERVAL, period="1d", multi_level_index=False, auto_adjust=True, progress=False)
            if df.empty or len(df) < 30: continue
            
            # 1. MACD (12, 26, 9)
            exp1 = df['Close'].ewm(span=12, adjust=False).mean()
            exp2 = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
            df['Hist'] = df['MACD'] - df['Signal_Line']
            
            # 2. ATR (10)
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift())
            low_close = np.abs(df['Low'] - df['Close'].shift())
            df['TR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df['ATR'] = df['TR'].rolling(10).mean()
            
            # 3. ADX (14)
            plus_dm = df['High'].diff()
            minus_dm = df['Low'].diff()
            plus_dm[plus_dm < 0] = 0
            minus_dm[minus_dm > 0] = 0
            df['ADX'] = 100 * (np.abs(plus_dm - minus_dm) / (plus_dm + minus_dm + 1e-5)).rolling(14).mean()
            
            # Die letzte vollständig geschlossene Minute analysieren
            last_hist = df['Hist'].iloc[-2]
            prev_hist = df['Hist'].iloc[-3]
            current_adx = df['ADX'].iloc[-2]
            current_atr = df['ATR'].iloc[-2]
            
            bullish_fuel = (current_adx > 20) and (last_hist > 0)
            bearish_fuel = (current_adx > 20) and (last_hist < 0)
            
            long_cond = (prev_hist <= 0 and last_hist > 0) and bullish_fuel
            short_cond = (prev_hist >= 0 and last_hist < 0) and bearish_fuel
            
            states = trade_states[asset]
            long_signal = long_cond and not states["in_long"]
            short_signal = short_cond and not states["in_short"]
            
            if long_signal or short_signal:
                sig_type = "BUY" if long_signal else "SELL"
                
                # Zustand im Speicher updaten
                trade_states[asset]["in_long"] = long_signal
                trade_states[asset]["in_short"] = short_signal
                
                message = f"⚡ {asset} [{INTERVAL}] {sig_type}!\nADX: {round(current_adx, 1)} | MACD: {round(last_hist, 3)} | ATR: {round(current_atr, 2)}"
                
                # Push-Signal an Ihr iPhone feuern
                requests.post(NTFY_URL, data=message.encode('utf-8'))
                print(f"   🚀 SIGNAL GEFEUERT: {message}")
                
        except Exception as e:
            print(f"Fehler bei {asset}: {e}")

# Endlosschleife läuft permanent auf dem Render-Server (Prüft alle 20 Sekunden)
while True:
    scan_all_assets()
    time.sleep(20)
