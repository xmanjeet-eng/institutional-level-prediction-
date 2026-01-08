import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
from flask import Flask, render_template
from xgboost import XGBRegressor
from datetime import datetime
import pytz, gc, threading, time, requests

app = Flask(__name__)

# --- CONFIGURATION ---
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"
# Replace with your actual Render URL after deployment
APP_URL = "https://your-app-name.onrender.com/" 

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"})
    except: pass

def get_ist_time():
    return datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')

def analyze_market(symbol):
    # Small period (30d) to prevent SIGKILL/Memory errors
    df = yf.download(symbol, period='30d', interval='5m', multi_level_index=False)
    if df.empty or len(df) < 30: return None

    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['VWAP'] = ta.vwap(df['High'], df['Low'], df['Close'], df['Volume'])
    
    # ML Prediction Logic
    df['Target'] = df['Close'].shift(-1)
    train_df = df.dropna().tail(150)
    features = ['Close', 'RSI', 'VWAP']
    
    model = XGBRegressor(n_estimators=40, max_depth=3, learning_rate=0.1)
    model.fit(train_df[features], train_df['Target'])
    
    latest = df[features].tail(1)
    pred = model.predict(latest)[0]
    curr = df['Close'].iloc[-1]
    diff = ((pred - curr) / curr) * 100

    signal = "NEUTRAL"
    if diff > 0.08: signal = "BULLISH"
    elif diff < -0.08: signal = "BEARISH"

    # Alert on Strong Signals
    if abs(diff) > 0.15:
        send_telegram(f"🚨 *STRENGTH ALERT*: {symbol}\nSignal: {signal}\nTarget: ₹{round(pred,2)}")

    res = {"name": symbol, "price": round(curr, 2), "pred": round(pred, 2), 
           "sig": signal, "rsi": int(df['RSI'].iloc[-1]), "chg": round(diff, 2)}
    del df; gc.collect()
    return res

def heartbeat():
    """Keeps Render awake during NSE hours (9:15 AM - 3:30 PM IST)"""
    while True:
        now = datetime.now(pytz.timezone('Asia/Kolkata'))
        if 9 <= now.hour <= 16:
            try: requests.get(APP_URL)
            except: pass
        time.sleep(600) # Ping every 10 mins

threading.Thread(target=heartbeat, daemon=True).start()

@app.route('/')
def home():
    n = analyze_market('^NSEI')
    b = analyze_market('^NSEBANK')
    return render_template('index.html', n=n, b=b, ts=get_ist_time())

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
