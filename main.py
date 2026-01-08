import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
from flask import Flask, render_template
from xgboost import XGBRegressor
from datetime import datetime
import pytz, gc, threading, time, requests, os

app = Flask(__name__)

# Railway automatic domain variable
APP_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN", "0.0.0.0")

def analyze_market(symbol):
    try:
        # Fetching ONLY 15 days of 5m data (keeps memory under 150MB)
        df = yf.download(symbol, period='15d', interval='5m', multi_level_index=False)
        if df.empty or len(df) < 20: return None

        # Lightweight calculations
        df['RSI'] = ta.rsi(df['Close'], length=14)
        df['VWAP'] = ta.vwap(df['High'], df['Low'], df['Close'], df['Volume'])
        
        # Trim data immediately to save RAM
        df = df.tail(100).copy()
        
        # Simple ML prediction
        df['Target'] = df['Close'].shift(-1)
        train_df = df.dropna()
        features = ['Close', 'RSI', 'VWAP']
        
        # Ultra-light model (Low depth/estimators = Low RAM)
        model = XGBRegressor(n_estimators=20, max_depth=2, learning_rate=0.1)
        model.fit(train_df[features], train_df['Target'])
        
        pred = model.predict(df[features].tail(1))[0]
        curr = df['Close'].iloc[-1]
        diff = ((pred - curr) / curr) * 100

        res = {
            "name": "NIFTY" if "NSEI" in symbol else "BANK NIFTY",
            "price": round(curr, 2),
            "pred": round(pred, 2),
            "sig": "BULLISH" if diff > 0.05 else "BEARISH" if diff < -0.05 else "SIDEWAYS",
            "rsi": int(df['RSI'].iloc[-1]),
            "chg": round(diff, 3)
        }
        # Force garbage collection
        del df, model; gc.collect()
        return res
    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return None

@app.route('/')
def home():
    n = analyze_market('^NSEI')
    b = analyze_market('^NSEBANK')
    now = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')
    return render_template('index.html', n=n, b=b, ts=now)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
