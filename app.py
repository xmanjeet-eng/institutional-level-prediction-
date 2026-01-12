import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
from flask import Flask, render_template
from datetime import datetime
import pytz
import os

app = Flask(__name__)

def get_ist_time():
    """Helper to get current time in IST"""
    return datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')

def analyze_ticker(symbol):
    # Fetch data (5m interval)
    df = yf.download(symbol, period='10d', interval='5m', multi_level_index=False)
    
    if df.empty or len(df) < 200: 
        return None

    # --- INDICATORS ---
    df['EMA_200'] = ta.ema(df['Close'], length=200)
    df.ta.supertrend(length=10, multiplier=3, append=True)
    df.ta.rsi(length=14, append=True)
    df.ta.vwap(append=True)
    df.ta.adx(append=True) 
    df.ta.atr(append=True)

    # --- COLUMN CLEANING ---
    try:
        st_col = [c for c in df.columns if c.startswith('SUPERT_') and not c.endswith('d')][0]
        rsi_col = [c for c in df.columns if c.startswith('RSI')][0]
        vwap_col = [c for c in df.columns if c.startswith('VWAP')][0]
        adx_col = [c for c in df.columns if c.startswith('ADX')][0]
        atr_col = [c for c in df.columns if c.startswith('ATRr')][0]
    except IndexError:
        return None

    last = df.iloc[-1]
    curr_price = last['Close']
    
    # Logic Engine
    is_bullish_trend = curr_price > last['EMA_200']
    is_trending = last[adx_col] > 23 
    is_above_vwap = curr_price > last[vwap_col]
    is_supertrend_green = curr_price > last[st_col]
    
    # Scoring
    score = 0
    if is_bullish_trend: score += 25
    if is_above_vwap: score += 25
    if is_supertrend_green: score += 25
    if is_trending: score += 25

    rsi_val = last[rsi_col]
    
    # Signal Definition
    final_signal = "NEUTRAL / SIDEWAYS"
    if score >= 75 and rsi_val > 50:
        final_signal = "STRONG BUY"
    elif score <= 25 and rsi_val < 50:
        final_signal = "STRONG SELL"
    elif not is_trending:
        final_signal = "SIDEWAYS - NO TRADE"

    atr_step = last[atr_col] * 1.5

    return {
        "name": "NIFTY 50" if "NSEI" in symbol else "BANK NIFTY",
        "price": round(curr_price, 2),
        "target": round(curr_price + atr_step if "BUY" in final_signal else curr_price - atr_step, 2),
        "stoploss": round(curr_price - (atr_step * 0.5) if "BUY" in final_signal else curr_price + (atr_step * 0.5), 2),
        "up_prob": score if is_bullish_trend else (100 - score if score < 50 else 50),
        "signal": final_signal,
        "rsi": int(rsi_val),
        "trend_strength": "STRONG" if is_trending else "WEAK/CHOPPY"
    }

# --- THE MISSING ROUTES THAT CAUSED THE 404 ---
@app.route('/')
def home():
    try:
        nifty = analyze_ticker('^NSEI')
        bank = analyze_ticker('^NSEBANK')
        
        if not nifty or not bank:
            return "<h3>Market Data Loading... Please refresh in 30 seconds.</h3>"
            
        return render_template('index.html', n=nifty, b=bank, time=get_ist_time())
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    # Use port 5000 by default
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
