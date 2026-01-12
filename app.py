import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
from flask import Flask, render_template
from datetime import datetime
import pytz
import os

app = Flask(__name__)

def analyze_ticker(symbol):
    # Fetching 15-minute data is often more 'predictable' for Nifty futures than 5m
    df = yf.download(symbol, period='10d', interval='5m', multi_level_index=False)
    
    if df.empty or len(df) < 200: 
        return {"error": "Insufficient data for 200 EMA calculation"}

    # --- INDICATORS ---
    df['EMA_200'] = ta.ema(df['Close'], length=200)
    df.ta.supertrend(length=10, multiplier=3, append=True)
    df.ta.rsi(length=14, append=True)
    df.ta.vwap(append=True)
    df.ta.adx(append=True) # Measures trend strength
    df.ta.atr(append=True)

    # --- COLUMN CLEANING ---
    try:
        st_col = [c for c in df.columns if c.startswith('SUPERT_') and not c.endswith('d')][0]
        rsi_col = [c for c in df.columns if c.startswith('RSI')][0]
        vwap_col = [c for c in df.columns if c.startswith('VWAP')][0]
        adx_col = [c for c in df.columns if c.startswith('ADX')][0]
        atr_col = [c for c in df.columns if c.startswith('ATRr')][0]
    except IndexError:
        return {"error": "Indicator sync error"}

    last = df.iloc[-1]
    curr_price = last['Close']
    
    # --- PREDICTIVE LOGIC ENGINE ---
    # 1. Trend Filter (Institutional)
    is_bullish_trend = curr_price > last['EMA_200']
    
    # 2. Strength Filter (Avoid Sideways)
    is_trending = last[adx_col] > 23 
    
    # 3. Momentum & Volume
    is_above_vwap = curr_price > last[vwap_col]
    is_supertrend_green = curr_price > last[st_col]
    
    # --- SCORING SYSTEM (0-100% Probability) ---
    score = 0
    if is_bullish_trend: score += 25
    if is_above_vwap: score += 25
    if is_supertrend_green: score += 25
    if is_trending: score += 25

    # Refine RSI: Don't short just because it's 70. Short if < 70 and dropping.
    rsi_val = last[rsi_col]
    
    # --- SIGNAL DEFINITION ---
    final_signal = "NEUTRAL"
    if score >= 75 and rsi_val > 50:
        final_signal = "STRONG BUY"
    elif score <= 25 and rsi_val < 50:
        final_signal = "STRONG SELL"
    elif not is_trending:
        final_signal = "SIDEWAYS - DO NOT TRADE"

    # ATR Based Risk/Reward
    atr_step = last[atr_col] * 1.5

    return {
        "name": "NIFTY 50" if "NSEI" in symbol else "BANK NIFTY",
        "price": round(curr_price, 2),
        "target": round(curr_price + atr_step if "BUY" in final_signal else curr_price - atr_step, 2),
        "stoploss": round(curr_price - (atr_step * 0.5) if "BUY" in final_signal else curr_price + (atr_step * 0.5), 2),
        "up_prob": score if is_bullish_trend else 100 - score,
        "signal": final_signal,
        "rsi": int(rsi_val),
        "trend_strength": "STRONG" if is_trending else "WEAK/CHOPPY"
    }
