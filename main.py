# V21 - Railway Version - NO PANDAS
import requests
import time
import os
from datetime import datetime

# Railway eke Variables walin gannawa - Code eke token danna one na
COIN = os.getenv("COIN", "BTCUSDT")
TIMEFRAME = "5m"
OBI_THRESHOLD = 0.70
TELEGRAM_TOKEN = os.getenv("9267375532:AAFe8pS5bvsRrDAA8_4soTzetvD1uN6HJ0g", "")
TELEGRAM_CHAT_ID = os.getenv("8633386457", "")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

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
    candles = []
    for c in r:
        candles.append({'open': float(c[1]), 'high': float(c[2]), 'low': float(c[3]), 'close': float(c[4]), 'volume': float(c[5])})
    return candles

def calc_vwap_bands(candles):
    pv_sum = 0
    v_sum = 0
    for c in candles:
        typical = (c['high'] + c['low'] + c['close']) / 3
        pv_sum += typical * c['volume']
        v_sum += c['volume']
    vwap = pv_sum / v_sum if v_sum != 0 else candles[-1]['close']
    last50 = [c['close'] for c in candles[-50:]]
    mean = sum(last50) / len(last50)
    std = (sum([(x-mean)**2 for x in last50]) / len(last50)) ** 0.5
    return vwap, vwap+std, vwap+std*2, vwap+std*3, vwap-std, vwap-std*2, vwap-std*3

def get_lvn(candles):
    low = min([c['low'] for c in candles])
    high = max([c['high'] for c in candles])
    bins = [low + (high-low)*i/50 for i in range(51)]
    volumes = [0]*50
    for c in candles:
        for i in range(50):
            if bins[i] <= c['close'] < bins[i+1]:
                volumes[i] += c['volume']
                break
    min_idx = volumes.index(min(volumes))
    return (bins[min_idx] + bins[min_idx+1]) / 2

def get_cvd(candles):
    cvd = []
    cum = 0
    for c in candles:
        cum += c['volume'] if c['close'] > c['open'] else -c['volume']
        cvd.append(cum)
    last10_low = min([c['low'] for c in candles[-10:]])
    prev10_low = min([c['low'] for c in candles[-20:-10]])
    if last10_low < prev10_low and min(cvd[-10:]) > min(cvd[-20:-10]):
        return True, "BUY"
    last10_high = max([c['high'] for c in candles[-10:]])
    prev10_high = max([c['high'] for c in candles[-20:-10]])
    if last10_high > prev10_high and max(cvd[-10:]) < max(cvd[-20:-10]):
        return True, "SELL"
    return False, ""

def get_obi():
    url = f"https://api.binance.com/api/v3/depth?symbol={COIN}&limit=50"
    ob = requests.get(url).json()
    bids = sum([float(b[1]) for b in ob['bids']])
    asks = sum([float(a[1]) for a in ob['asks']])
    return bids/(bids+asks), asks/(bids+asks)

def check_pa(candles):
    last = candles[-1]
    prev = candles[-2]
    body = abs(last['close'] - last['open'])
    lower_wick = min(last['close'], last['open']) - last['low']
    upper_wick = last['high'] - max(last['close'], last['open'])
    if lower_wick > body * 1.5 and last['close'] > prev['close']:
        return True, "BUY"
    if upper_wick > body * 1.5 and last['close'] < prev['close']:
        return True, "SELL"
    return False, ""

def main():
    log(f"V21 Bot Start - {COIN} - Railway")
    send_telegram(f"✅ *V21 Bot Start - Railway*\nCoin: {COIN}\nTimeframe: 5min\nFilter: VWAP + LVN + CVD + PA + OBI 70/30")
    while True:
        try:
            candles = get_data()
            vwap, u1, u2, u3, l1, l2, l3 = calc_vwap_bands(candles)
            lvn = get_lvn(candles)
            price = candles[-1]['close']
            log(f"Price: {price:.2f} | VWAP: {vwap:.2f} | LVN: {lvn:.2f}")
            if abs(price - lvn) / lvn < 0.001:
                log("LVN Retest Awa!")
                has_div, div_type = get_cvd(candles)
                if not has_div:
                    time.sleep(30)
                    continue
                has_pa, pa_type = check_pa(candles)
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
                msg = f"""{emoji} *V21 SIGNAL - {pa_type}*\nCoin: {COIN}\nEntry: `{price:.2f}`\nTP: `{tp:.2f}`\nSL: `{sl:.2f}` (LVN)\n\nCVD: {div_type} ✅\nPA: Wick + 2 Candle ✅\nOBI: Bid {bid_r*100:.0f}% / Ask {ask_r*100:.0f}% ✅\n\nBinance eke manual gahanna!"""
                send_telegram(msg)
                print(msg, flush=True)
                time.sleep(300)
            time.sleep(30)
        except Exception as e:
            log(f"Error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
