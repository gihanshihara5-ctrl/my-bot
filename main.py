# V21 FINAL - Telegram Signal - NO Binance API Key
import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime

# ===== MEWA WENAS KARANNA =====
COIN = "BTCUSDT"  # ETHUSDT, SOLUSDT wage
TIMEFRAME = "5m"
OBI_THRESHOLD = 0.70

TELEGRAM_TOKEN = "9267375532:AAFe8pS5bvsRrDAA8_4soTzetvD1uN6HJ0g"
TELEGRAM_CHAT_ID = "8633386457"  # 123456789 wage
# ==============================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        requests.post(url, data=data, timeout=10)
        log("Telegram Signal Yawwa!")
    except Exception as e:
        log(f"Telegram Error: {e}")

def get_data():
    url = f"https://api.binance.com/api/v3/klines?symbol={COIN}&interval={TIMEFRAME}&limit=200"
    r = requests.get(url).json()
    df = pd.DataFrame(r, columns=['time','open','high','low','close','volume','a','b','c','d','e','f'])
    for c in ['open','high','low','close','volume']:
        df[c] = df[c].astype(float)
    return df

def calc_vwap_bands(df):
    typical = (df['high'] + df['low'] + df['close']) / 3
    vwap = (typical * df['volume']).cumsum() / df['volume'].cumsum()
    std = df['close'].rolling(50).std()
    return vwap.iloc[-1], (vwap + std).iloc[-1], (vwap + std*2).iloc[-1], (vwap + std*3).iloc[-1], (vwap - std).iloc[-1], (vwap - std*2).iloc[-1], (vwap - std*3).iloc[-1]

def get_lvn(df):
    low = df['low'].min()
    high = df['high'].max()
    bins = np.linspace(low, high, 50)
    volumes = np.zeros(len(bins)-1)
    for i in range(len(df)):
        idx = np.digitize(df['close'].iloc[i], bins) - 1
        if 0 <= idx < len(volumes):
            volumes[idx] += df['volume'].iloc[i]
    lvn_idx = np.argmin(volumes)
    return (bins[lvn_idx] + bins[lvn_idx+1]) / 2

def get_cvd(df):
    cum = 0
    cvd = []
    for i in range(len(df)):
        cum += df['volume'].iloc[i] if df['close'].iloc[i] > df['open'].iloc[i] else -df['volume'].iloc[i]
        cvd.append(cum)
    price_low = df['low'].tail(10).min()
    price_low_prev = df['low'].tail(20).head(10).min()
    if price_low < price_low_prev and min(cvd[-10:]) > min(cvd[-20:-10]):
        return True, "BUY"
    price_high = df['high'].tail(10).max()
    price_high_prev = df['high'].tail(20).head(10).max()
    if price_high > price_high_prev and max(cvd[-10:]) < max(cvd[-20:-10]):
        return True, "SELL"
    return False, ""

def get_obi():
    url = f"https://api.binance.com/api/v3/depth?symbol={COIN}&limit=50"
    ob = requests.get(url).json()
    bids = sum([float(b[1]) for b in ob['bids']])
    asks = sum([float(a[1]) for a in ob['asks']])
    return bids/(bids+asks), asks/(bids+asks)

def check_pa(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    body = abs(last['close'] - last['open'])
    lower_wick = min(last['close'], last['open']) - last['low']
    upper_wick = last['high'] - max(last['close'], last['open'])
    if lower_wick > body * 1.5 and last['close'] > prev['close']:
        return True, "BUY"
    if upper_wick > body * 1.5 and last['close'] < prev['close']:
        return True, "SELL"
    return False, ""

def main():
    log(f"V21 Telegram Bot Start - {COIN}")
    send_telegram(f"✅ *V21 Bot Start*\nCoin: {COIN}\nTimeframe: 5min\nFilter: VWAP + LVN + CVD + PA + OBI 70/30\nSignal eka mekata enawa.")
    while True:
        try:
            df = get_data()
            vwap, u1, u2, u3, l1, l2, l3 = calc_vwap_bands(df)
            lvn = get_lvn(df)
            price = df['close'].iloc[-1]
            log(f"Price: {price:.2f} | VWAP: {vwap:.2f} | LVN: {lvn:.2f}")

            if abs(price - lvn) / lvn < 0.001:
                log("LVN Retest Awa! Checking...")
                has_div, div_type = get_cvd(df)
                if not has_div:
                    time.sleep(30)
                    continue
                has_pa, pa_type = check_pa(df)
                if not has_pa or pa_type != div_type:
                    time.sleep(30)
                    continue
                bid_r, ask_r = get_obi()
                log(f"OBI - Bid: {bid_r*100:.1f}% Ask: {ask_r*100:.1f}%")
                obi_ok = (pa_type == "BUY" and bid_r >= OBI_THRESHOLD) or (pa_type == "SELL" and ask_r >= OBI_THRESHOLD)
                if not obi_ok:
                    time.sleep(30)
                    continue

                if pa_type == "BUY":
                    sl = lvn * 0.999
                    tp = u2 if price < u1 else u3 if price < u2 else vwap
                    emoji = "🟢"
                else:
                    sl = lvn * 1.001
                    tp = l2 if price > l1 else l3 if price > l2 else vwap
                    emoji = "🔴"

                msg = f"""{emoji} *V21 SIGNAL - {pa_type}*
Coin: {COIN}
Entry: `{price:.2f}`
TP: `{tp:.2f}`
SL: `{sl:.2f}` (LVN)

CVD: {div_type} ✅
PA: Wick + 2 Candle ✅
OBI: Bid {bid_r*100:.0f}% / Ask {ask_r*100:.0f}% ✅

Binance eke manual gahanna!"""
                send_telegram(msg)
                print(msg)
                time.sleep(300) # 5min inna, ekama signal eka deparak enna epa

            time.sleep(30)
        except Exception as e:
            log(f"Error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
