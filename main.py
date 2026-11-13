import time, requests, math, traceback, json, os, uuid, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

INSTANCE_ID = str(uuid.uuid4())[:6]
TELEGRAM_TOKEN = '9267375532:AAFe8pS5bvsRrDAA8_4soTzetvD1uN6HJ0g'
TELEGRAM_CHAT_ID = '8633386457'

def keep_alive():
    try:
        port = int(os.environ.get("PORT", 8080))
        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
            def log_message(self, *a): pass
        HTTPServer(("0.0.0.0", port), H).serve_forever()
    except Exception as e:
        print("KeepAlive Error:", e, flush=True)
threading.Thread(target=keep_alive, daemon=True).start()

# ===== BYBIT PERP - Binance Block eka nathi karanna =====
SYMBOLS = ["ONTUSDT", "DOTUSDT", "PUMPUSDT"]

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=15)
        print(f"TG Sent: {r.status_code}", flush=True)
    except Exception as e:
        print("TG Error:", e, flush=True)

def get_klines(symbol, limit=100):
    # Bybit: list eka aluthen parana ta enawa, api parana idan aluthata hadanawa
    try:
        r = requests.get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval=5&limit={limit}", timeout=15)
        j = r.json()
        lst = j.get("result", {}).get("list", [])
        if not lst or len(lst) < 10: return None
        lst = lst[::-1] # parana -> aluth
        # Binance format ekata convert karanawa: [time, open, high, low, close, volume]
        klines = []
        for x in lst:
            klines.append([int(x[0]), x[1], x[2], x[3], x[4], x[5]])
        print(f"KLINES OK Bybit {symbol} len {len(klines)}", flush=True)
        return klines
    except Exception as e:
        print(f"Klines fail Bybit {symbol} {e}", flush=True)
        return None

def get_agg_trades(symbol, limit=1000):
    # Bybit Public Trades - Buy/Sell flow eka ganna
    try:
        r = requests.get(f"https://api.bybit.com/v5/market/recent-trade?category=linear&symbol={symbol}&limit=1000", timeout=15)
        j = r.json()
        lst = j.get("result", {}).get("list", [])
        if not lst: return None
        # Binance format ekata: q = size, m = True nam Sell, p = price
        trades = []
        for x in lst[::-1]:
            # Bybit side: Buy = buyer active, Sell = seller active
            trades.append({"q": x["size"], "m": True if x["side"] == "Sell" else False, "p": x["price"]})
        return trades
    except Exception as e:
        print(f"Trades fail {e}", flush=True)
        return None

def ema(data, period):
    k = 2/(period+1); e = data[0]
    for v in data[1:]: e = v*k + e*(1-k)
    return e

def get_volume_profile(klines, bins=30):
    highs = [float(k[2]) for k in klines]; lows = [float(k[3]) for k in klines]
    lo = min(lows); hi = max(highs); step = (hi-lo)/bins if hi>lo else 1
    profile = []
    for i in range(bins):
        p_low = lo + i*step; p_high = p_low + step; v=0
        for k in klines:
            mid = (float(k[2])+float(k[3]))/2
            if p_low <= mid < p_high: v += float(k[5])
        profile.append([p_low + step/2, v])
    profile.sort(key=lambda x: x[1], reverse=True)
    poc = profile[0][0]
    lvn_list = sorted([x[0] for x in sorted(profile, key=lambda x: x[1])[:4]])
    return poc, lvn_list

def get_vwap_bands(klines):
    k = klines[-50:]
    tp = [(float(x[2])+float(x[3])+float(x[4]))/3 for x in k]
    v = [float(x[5]) for x in k]
    vwap = sum([p*vol for p,vol in zip(tp,v)]) / sum(v)
    var = sum([vol * ((p - vwap)**2) for p,vol in zip(tp,v)]) / sum(v)
    std = math.sqrt(var)
    return vwap, vwap+std, vwap-std, vwap+2*std, vwap-2*std, vwap+3*std, vwap-3*std

def get_price_action(klines):
    prev = klines[-2]; curr = klines[-1]
    p_o, p_c = float(prev[1]), float(prev[4])
    c_o, c_c, c_h, c_l = float(curr[1]), float(curr[4]), float(curr[2]), float(curr[3])
    body_curr = abs(c_c - c_o)
    bull_engulf = (p_c < p_o) and (c_c > c_o) and (c_o <= p_c) and (c_c >= p_o)
    bear_engulf = (p_c > p_o) and (c_c < c_o) and (c_o >= p_c) and (c_c <= p_o)
    lower_wick = min(c_o, c_c) - c_l; upper_wick = c_h - max(c_o, c_c)
    bull_pin = (c_c > c_o) and (lower_wick > body_curr*1.5) if body_curr>0 else False
    bear_pin = (c_c < c_o) and (upper_wick > body_curr*1.5) if body_curr>0 else False
    bull_pa = bull_engulf or bull_pin; bear_pa = bear_engulf or bear_pin
    pa_name = "Bullish Engulfing" if bull_engulf else "Bullish Pin" if bull_pin else "Bearish Engulfing" if bear_engulf else "Bearish Pin" if bear_pin else "No PA"
    return bull_pa, bear_pa, pa_name

def get_orderflow(trades):
    if not trades: return 0, True, False, False
    buy_vol = sum([float(t['q']) for t in trades if not t['m']]); sell_vol = sum([float(t['q']) for t in trades if t['m']])
    total = buy_vol + sell_vol; delta_pct = ((buy_vol-sell_vol)/total*100) if total>0 else 0
    half = len(trades)//2
    cvd_first = sum([float(t['q']) if not t['m'] else -float(t['q']) for t in trades[:half]])
    cvd_last = sum([float(t['q']) if not t['m'] else -float(t['q']) for t in trades[half:]])
    cvd_rising = cvd_last > cvd_first
    recent = trades[-300:]
    r_buy = sum([float(t['q']) for t in recent if not t['m']]); r_sell = sum([float(t['q']) for t in recent if t['m']])
    r_delta = r_buy - r_sell
    price_start = float(trades[-300]['p']); price_end = float(trades[-1]['p'])
    price_change_pct = (price_end - price_start)/price_start*100 if price_start!=0 else 0
    bull_abs = (r_delta < -0.5) and (abs(price_change_pct) < 0.08) and (price_end >= price_start)
    bear_abs = (r_delta > 0.5) and (abs(price_change_pct) < 0.08) and (price_end <= price_start)
    return delta_pct, cvd_rising, bull_abs, bear_abs

def get_risk_limits(price):
    if price > 1000: return 30, 8
    elif price > 100: return 3, 0.8
    elif price > 10: return 0.3, 0.08
    elif price > 1: return 0.03, 0.008
    elif price > 0.1: return price*0.03, price*0.008
    else: return price*0.03, price*0.008

def calc_trade(price, direction, klines, nearest_lvn):
    max_risk, min_risk = get_risk_limits(price)
    last3_lows = [float(k[3]) for k in klines[-3:]]
    last3_highs = [float(k[2]) for k in klines[-3:]]
    swing_low = min(last3_lows); swing_high = max(last3_highs)
    if direction == "BUY":
        sl = max(swing_low - max_risk*0.1, nearest_lvn - max_risk*0.1)
        if price - sl > max_risk: sl = price - max_risk
        if price - sl < min_risk: sl = price - min_risk
        risk = price - sl
        return sl, price + risk*2, price + risk*3, risk, swing_low
    else:
        sl = min(swing_high + max_risk*0.1, nearest_lvn + max_risk*0.1)
        if sl - price > max_risk: sl = price + max_risk
        if sl - price < min_risk: sl = price + min_risk
        risk = sl - price
        return sl, price - risk*2, price - risk*3, risk, swing_high

print(f"BOT STARTED - V20 BYBIT PERP - ID:{INSTANCE_ID}", flush=True)
send_telegram(f"🔥 BOT ON - V20 BYBIT PERP - ID:{INSTANCE_ID}\nCoin 3i:\n1. ONTUSDT.P\n2. DOTUSDT.P\n3. PUMPUSDT.P\n\nDan Bybit Perp Data walin - Binance Block na!")

while True:
    try:
        for symbol in SYMBOLS:
            try:
                print(f"Checking {symbol}...", flush=True)
                klines = get_klines(symbol, 100)
                if klines is None:
                    send_telegram(f"❌ DATA FAIL - {symbol}.P\nBybit ekenuth Data enne na.\nID:{INSTANCE_ID}")
                    continue
                closes = [float(k[4]) for k in klines]
                price = closes[-1]
                poc, lvn_list = get_volume_profile(klines)
                vwap, v1u, v1d, v2u, v2d, v3u, v3d = get_vwap_bands(klines)
                bull_pa, bear_pa, pa_name = get_price_action(klines)
                trades = get_agg_trades(symbol, 1000)
                delta_pct, cvd_rising, bull_abs, bear_abs = get_orderflow(trades if trades else [])
                ema9 = ema(closes,9); ema21 = ema(closes,21)
                nearest_lvn = min(lvn_list, key=lambda x: abs(x-price))
                buy_score = 0
                if price > nearest_lvn: buy_score+=1
                if price > vwap: buy_score+=1
                if ema9 > ema21: buy_score+=1
                if cvd_rising and delta_pct > 0: buy_score+=1
                if bull_pa or bull_abs: buy_score+=1
                sell_score = 0
                if price < nearest_lvn: sell_score+=1
                if price < vwap: sell_score+=1
                if ema9 < ema21: sell_score+=1
                if not cvd_rising and delta_pct < 0: sell_score+=1
                if bear_pa or bear_abs: sell_score+=1
                if price > 100: dec = 1
                elif price > 10: dec = 2
                elif price > 1: dec = 3
                elif price > 0.1: dec = 4
                elif price > 0.01: dec = 5
                else: dec = 6
                if buy_score >= 3 and buy_score > sell_score:
                    direction = "🟢 BUY"; side_text = "BUY / LONG"; action = "BUY ගන්න"
                    sl, tp1, tp2, risk, swing = calc_trade(price, "BUY", klines, nearest_lvn)
                    entry = price
                elif sell_score >= 3 and sell_score > buy_score:
                    direction = "🔴 SELL"; side_text = "SELL / SHORT"; action = "SELL ගන්න"
                    sl, tp1, tp2, risk, swing = calc_trade(price, "SELL", klines, nearest_lvn)
                    entry = price
                else:
                    direction = "⏳ WAIT"; side_text = "WAIT"; action = "Trade ගන්න එපා, Break එකක් එනකන් ඉන්න"
                    entry = price; sl = nearest_lvn; tp1 = entry; tp2 = entry; risk = 0; swing = 0
                plan_text = f"{direction}\nSide: {side_text}\nEntry: {entry:.{dec}f}\n🛑 Stop Loss: {sl:.{dec}f}\n🎯 Take Profit 1: {tp1:.{dec}f}\n🎯 Take Profit 2: {tp2:.{dec}f}\nRisk: {risk:.{dec}f} | RR: 1:2\nBuy: {buy_score}/5 | Sell: {sell_score}/5\nBase LVN: {nearest_lvn:.{dec}f}"
                print(f"{symbol} Price:{price:.{dec}f} Dir:{direction} Buy:{buy_score} Sell:{sell_score}", flush=True)
                send_telegram(f"📊 SCAN 5M - V20 BYBIT PERP - {symbol}.P\nPrice: {price:.{dec}f}\nPOC: {poc:.{dec}f} | Nearest LVN: {nearest_lvn:.{dec}f}\nVWAP: {vwap:.{dec}f} | V2U: {v2u:.{dec}f} V2D: {v2d:.{dec}f}\nPA: {pa_name} | Delta: {delta_pct:.1f}% | CVD: {'UP 🟢' if cvd_rising else 'DOWN 🔴'}\nAbsorption: Bull {bull_abs} Bear {bear_abs}\n\n--- TRADE DECISION ---\n{plan_text}\n\n{action}")
            except Exception as e:
                print(f"Error {symbol}: {e}", flush=True)
                continue
        print("Sleep 5 min...", flush=True)
        time.sleep(300)
    except Exception as e:
        print("ERROR:", traceback.format_exc(), flush=True)
        send_telegram(f"❌ ERROR\n{str(e)[:300]}")
        time.sleep(20)
