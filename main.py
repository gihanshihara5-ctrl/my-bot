import time, requests, hmac, hashlib, urllib.parse, math

# ========= CONFIG =========
TELEGRAM_TOKEN = '9267375532:AAH1J6hZGJhlJN6cZiHn8ur-rRUHi7HE-LA'
TELEGRAM_CHAT_ID = '8633386457'
API_KEY = 'ඔයාගෙ TESTNET API KEY'
API_SECRET = 'ඔයාගෙ TESTNET SECRET'
BASE = "https://testnet.binancefuture.com"
SYMBOL = "BTCUSDT"
QTY = 0.001
# ==========================

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
        print("TG:", r.json().get('ok'))
    except Exception as e: print("TG Error:", e)

def get_klines(limit=100):
    r = requests.get(f"{BASE}/fapi/v1/klines?symbol={SYMBOL}&interval=5m&limit={limit}", timeout=10)
    return r.json()

def get_agg_trades(limit=1500):
    r = requests.get(f"{BASE}/fapi/v1/aggTrades?symbol={SYMBOL}&limit={limit}", timeout=10)
    return r.json()

def get_funding():
    r = requests.get(f"{BASE}/fapi/v1/premiumIndex?symbol={SYMBOL}", timeout=10)
    return float(r.json()['lastFundingRate'])

def sign(params):
    qs = urllib.parse.urlencode(params)
    sig = hmac.new(API_SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()
    return qs + f"&signature={sig}"

def place_order(side, qty, tp, sl):
    try:
        headers = {"X-MBX-APIKEY": API_KEY}
        p = {"symbol": SYMBOL, "side": side, "type": "MARKET", "quantity": qty, "timestamp": int(time.time()*1000), "recvWindow": 5000}
        r = requests.post(f"{BASE}/fapi/v1/order?{sign(p)}", headers=headers, timeout=10)
        print("ORDER:", r.json())
        side2 = "SELL" if side=="BUY" else "BUY"
        for typ, price in [("TAKE_PROFIT_MARKET", tp), ("STOP_MARKET", sl)]:
            p2 = {"symbol": SYMBOL, "side": side2, "type": typ, "stopPrice": round(price,1), "closePosition": "true", "timestamp": int(time.time()*1000), "recvWindow": 5000}
            requests.post(f"{BASE}/fapi/v1/order?{sign(p2)}", headers=headers, timeout=10)
        return True
    except Exception as e: print("Order Error:", e); return False

def ema(data, period):
    k = 2/(period+1); e = data[0]
    for v in data[1:]: e = v*k + e*(1-k)
    return e

def get_volume_profile(klines, bins=30):
    highs = [float(k[2]) for k in klines]; lows = [float(k[3]) for k in klines]
    lo = min(lows); hi = max(highs); step = (hi-lo)/bins
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
    return vwap, vwap+2*std, vwap-2*std

def get_price_action(klines):
    prev = klines[-2]; curr = klines[-1]
    p_o, p_c = float(prev[1]), float(prev[4]); c_o, c_c, c_h, c_l = float(curr[1]), float(curr[4]), float(curr[2]), float(curr[3])
    body_prev = abs(p_c - p_o); body_curr = abs(c_c - c_o)
    bull_engulf = (p_c < p_o) and (c_c > c_o) and (c_o <= p_c) and (c_c >= p_o)
    bear_engulf = (p_c > p_o) and (c_c < c_o) and (c_o >= p_c) and (c_c <= p_o)
    lower_wick = min(c_o, c_c) - c_l; upper_wick = c_h - max(c_o, c_c)
    bull_pin = (c_c > c_o) and (lower_wick > body_curr*1.5)
    bear_pin = (c_c < c_o) and (upper_wick > body_curr*1.5)
    bull_pa = bull_engulf or bull_pin; bear_pa = bear_engulf or bear_pin
    pa_name = "Bullish Engulfing" if bull_engulf else "Bullish Pin" if bull_pin else "Bearish Engulfing" if bear_engulf else "Bearish Pin" if bear_pin else "No PA"
    return bull_pa, bear_pa, pa_name

def get_orderflow(trades):
    buy_vol = sum([float(t['q']) for t in trades if not t['m']]); sell_vol = sum([float(t['q']) for t in trades if t['m']])
    total = buy_vol + sell_vol; delta_pct = ((buy_vol-sell_vol)/total*100) if total>0 else 0
    half = len(trades)//2
    cvd_first = sum([float(t['q']) if not t['m'] else -float(t['q']) for t in trades[:half]])
    cvd_last = sum([float(t['q']) if not t['m'] else -float(t['q']) for t in trades[half:]])
    cvd_rising = cvd_last > cvd_first; cvd_slope = cvd_last - cvd_first
    recent = trades[-300:]
    r_buy = sum([float(t['q']) for t in recent if not t['m']]); r_sell = sum([float(t['q']) for t in recent if t['m']])
    r_delta = r_buy - r_sell
    price_start = float(trades[-300]['p']); price_end = float(trades[-1]['p'])
    price_change_pct = (price_end - price_start)/price_start*100
    bull_abs = (r_delta < -0.5) and (abs(price_change_pct) < 0.08) and (price_end >= price_start)
    bear_abs = (r_delta > 0.5) and (abs(price_change_pct) < 0.08) and (price_end <= price_start)
    return delta_pct, cvd_rising, cvd_slope, bull_abs, bear_abs

print("BOT STARTED - ULTIMATE FIXED")
send_telegram("🔥 ULTIMATE BOT ON - FIXED VERSION\nScore System: 4/6 = Trade\nHama 5M ekema Status eka enawa\nBTCUSDT 5M Testnet")

last_candle = 0
in_position = False
pending_break = None

while True:
    try:
        klines = get_klines(100)
        closes = [float(k[4]) for k in klines]
        price = closes[-1]; candle_time = klines[-1][0]
        if candle_time == last_candle:
            time.sleep(20); continue
        last_candle = candle_time

        poc, lvn_list = get_volume_profile(klines)
        vwap, v2u, v2d = get_vwap_bands(klines)
        bull_pa, bear_pa, pa_name = get_price_action(klines)
        trades = get_agg_trades(1500)
        delta_pct, cvd_rising, cvd_slope, bull_abs, bear_abs = get_orderflow(trades)
        ema9 = ema(closes,9); ema21 = ema(closes,21)
        funding = get_funding()

        print(f"Price:{price:.0f} POC:{poc:.0f} LVN:{[f'{x:.0f}' for x in lvn_list]} VWAP:{vwap:.0f} PA:{pa_name} Delta:{delta_pct:.1f} CVD:{cvd_rising} BullAbs:{bull_abs} BearAbs:{bear_abs} Pending:{pending_break}")

        if in_position:
            time.sleep(60); in_position=False; continue

        # ===== STEP 1: BREAK - LVN එක කැඩුනද? =====
        if pending_break is None:
            found = False
            for lvl in lvn_list:
                if closes[-2] < lvl < price:
                    pending_break = {"level": lvl, "dir": "UP", "candles": 0}; found=True
                    send_telegram(f"👀 BREAK UP - LVN {lvl:.0f}\nPrice: {price:.0f}\nRetest enakan inna... (10 Candle athulata)")
                elif closes[-2] > lvl > price:
                    pending_break = {"level": lvl, "dir": "DOWN", "candles": 0}; found=True
                    send_telegram(f"👀 BREAK DOWN - LVN {lvl:.0f}\nPrice: {price:.0f}\nRetest enakan inna... (10 Candle athulata)")
            if not found:
                # Break එකක් නැත්නම්, ඇයි Signal නැත්තෙ කියලා Status එකක් යවනවා - Bot එක වැඩ කරනවා කියලා පේන්න
                send_telegram(f"📊 SCAN 5M\nPrice: {price:.0f}\nPOC: {poc:.0f} | Nearest LVN: {min(lvn_list, key=lambda x: abs(x-price)):.0f}\nVWAP: {vwap:.0f} | V2U: {v2u:.0f} V2D: {v2d:.0f}\nPA: {pa_name} | Delta: {delta_pct:.1f}% | CVD: {'UP' if cvd_rising else 'DOWN'}\nAbsorption: Bull {bull_abs} Bear {bear_abs}\n⏳ LVN Break ekak na. Break ekak enakan wait.")
            time.sleep(10); continue

        # ===== STEP 2: RETEST + SCORE =====
        pending_break["candles"] += 1
        if pending_break["candles"] > 10:
            send_telegram(f"❌ Break Cancel - Retest awe na\nLevel: {pending_break['level']:.0f}")
            pending_break = None; continue
        lvl = pending_break["level"]
        # Retest එක ටිකක් ලිහිල් කලා - 0.3% ඇතුලට ආවම ඇති
        is_retest = abs(price - lvl) / lvl < 0.003
        if not is_retest:
            # Retest එක එන්නෙ නැත්නම් ඒකත් කියනවා
            send_telegram(f"⏳ Waiting Retest...\nLevel: {lvl:.0f} | Price: {price:.0f} | Gap: {abs(price-lvl):.0f}\nPA: {pa_name} | CVD: {'UP' if cvd_rising else 'DOWN'}")
            time.sleep(10); continue

        # SCORE SYSTEM - 6න් කීයක් හරිද?
        if pending_break["dir"]=="UP":
            score = 0; reasons=[]
            if price > lvl: score+=1; reasons.append("✅ Retest Hold")
            if bull_pa: score+=1; reasons.append(f"✅ PA: {pa_name}")
            if bull_abs: score+=1; reasons.append("✅ Bull Absorption 🔥")
            if cvd_rising and delta_pct > 0.5: score+=1; reasons.append(f"✅ CVD UP Delta +{delta_pct:.1f}%")
            if price > vwap or abs(price-v2d)<200: score+=1; reasons.append("✅ VWAP OK")
            if ema9 > ema21: score+=1; reasons.append("✅ EMA UP")
            else: reasons.append(f"❌ EMA DOWN")

            # 4ක් හරි ගියොත් Trade එක ගන්නවා!
            if score >= 4:
                sl = lvl - 80; tp = price + (price - sl)*2.5
                msg = f"🟢 LONG SIGNAL - SCORE {score}/6\n\nEntry: {price:.1f}\nTP: {tp:.1f} (Take Profit)\nSL: {sl:.1f} (Stop Loss)\nRR: 1:2.5\n\n" + "\n".join(reasons) + f"\nPOC: {poc:.0f} | VWAP: {vwap:.0f}"
                send_telegram(msg); place_order("BUY", QTY, tp, sl)
                in_position=True; pending_break=None
            else:
                send_telegram(f"⚠️ Retest awa, eth Score madi: {score}/6\nLevel: {lvl:.0f} Price: {price:.0f}\n" + "\n".join(reasons) + "\nTrade gatte na. 4k ona.")

        elif pending_break["dir"]=="DOWN":
            score = 0; reasons=[]
            if price < lvl: score+=1; reasons.append("✅ Retest Reject")
            if bear_pa: score+=1; reasons.append(f"✅ PA: {pa_name}")
            if bear_abs: score+=1; reasons.append("✅ Bear Absorption 🔥")
            if not cvd_rising and delta_pct < -0.5: score+=1; reasons.append(f"✅ CVD DOWN Delta {delta_pct:.1f}%")
            if price < vwap or abs(price-v2u)<200: score+=1; reasons.append("✅ VWAP OK")
            if ema9 < ema21: score+=1; reasons.append("✅ EMA DOWN")
            if score >= 4:
                sl = lvl + 80; tp = price - (sl - price)*2.5
                msg = f"🔴 SHORT SIGNAL - SCORE {score}/6\n\nEntry: {price:.1f}\nTP: {tp:.1f} (Take Profit)\nSL: {sl:.1f} (Stop Loss)\nRR: 1:2.5\n\n" + "\n".join(reasons) + f"\nPOC: {poc:.0f} | VWAP: {vwap:.0f}"
                send_telegram(msg); place_order("SELL", QTY, tp, sl)
                in_position=True; pending_break=None
            else:
                send_telegram(f"⚠️ Retest awa, eth Score madi: {score}/6\nLevel: {lvl:.0f} Price: {price:.0f}\n" + "\n".join(reasons) + "\nTrade gatte na. 4k ona.")
        time.sleep(10)
    except Exception as e:
        print("Error:", e); time.sleep(20)
