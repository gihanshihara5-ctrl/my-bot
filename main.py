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

# ===== 1. FRVP - LOW VOLUME NODES =====
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

# ===== 6. VWAP + BANDS 1,2,3 =====
def get_vwap_bands(klines):
    # VWAP = Sum( Typical Price * Volume ) / Sum(Volume)
    # Band = VWAP +/- Std * 1,2,3
    closes = [float(k[4]) for k in klines]; highs=[float(k[2]) for k in klines]; lows=[float(k[3]) for k in klines]; vols=[float(k[5]) for k in klines]
    # අන්තිම 50 Candle වලින් VWAP
    k = klines[-50:]
    tp = [(float(x[2])+float(x[3])+float(x[4]))/3 for x in k]
    v = [float(x[5]) for x in k]
    vwap = sum([p*vol for p,vol in zip(tp,v)]) / sum(v)
    # Std Dev
    var = sum([vol * ((p - vwap)**2) for p,vol in zip(tp,v)]) / sum(v)
    std = math.sqrt(var)
    return vwap, vwap+std, vwap-std, vwap+2*std, vwap-2*std, vwap+3*std, vwap-3*std, std

# ===== 3. PRICE ACTION =====
def get_price_action(klines):
    # අන්තිම Candle 2න් බලනවා
    prev = klines[-2]; curr = klines[-1]
    p_o, p_c, p_h, p_l = float(prev[1]), float(prev[4]), float(prev[2]), float(prev[3])
    c_o, c_c, c_h, c_l = float(curr[1]), float(curr[4]), float(curr[2]), float(curr[3])
    body_prev = abs(p_c - p_o); body_curr = abs(c_c - c_o)
    # Bullish Engulfing: කලින් Red Candle එක, දැන් Green Candle එක ඒක සම්පූර්ණයෙන්ම ගිලලා
    bull_engulf = (p_c < p_o) and (c_c > c_o) and (c_o <= p_c) and (c_c >= p_o) and (body_curr > body_prev)
    # Bearish Engulfing
    bear_engulf = (p_c > p_o) and (c_c < c_o) and (c_o >= p_c) and (c_c <= p_o) and (body_curr > body_prev)
    # Pin Bar / Hammer: පහල Wick එක Body එකට වඩා 2x වැඩි, උඩ Wick එක පොඩියි
    lower_wick = min(c_o, c_c) - c_l
    upper_wick = c_h - max(c_o, c_c)
    bull_pin = (c_c > c_o) and (lower_wick > body_curr*2) and (upper_wick < body_curr*0.5)
    bear_pin = (c_c < c_o) and (upper_wick > body_curr*2) and (lower_wick < body_curr*0.5)
    # Bullish PA = Engulfing හෝ Pin Bar
    bull_pa = bull_engulf or bull_pin
    bear_pa = bear_engulf or bear_pin
    pa_name = ""
    if bull_engulf: pa_name = "Bullish Engulfing"
    elif bull_pin: pa_name = "Bullish Pin Bar / Hammer"
    elif bear_engulf: pa_name = "Bearish Engulfing"
    elif bear_pin: pa_name = "Bearish Pin Bar / Shooting Star"
    return bull_pa, bear_pa, pa_name

# ===== 4 + 5. DELTA + ABSORPTION + CVD =====
def get_orderflow(trades):
    buy_vol = sum([float(t['q']) for t in trades if not t['m']])
    sell_vol = sum([float(t['q']) for t in trades if t['m']])
    total = buy_vol + sell_vol
    delta = buy_vol - sell_vol
    delta_pct = (delta/total*100) if total>0 else 0
    # CVD Slope
    half = len(trades)//2
    cvd_first = sum([float(t['q']) if not t['m'] else -float(t['q']) for t in trades[:half]])
    cvd_last = sum([float(t['q']) if not t['m'] else -float(t['q']) for t in trades[half:]])
    cvd_rising = cvd_last > cvd_first
    cvd_slope = cvd_last - cvd_first
    # --- ABSORPTION Logic ---
    # අන්තිම Trades 300න් Price එකේ Change එක බලනවා
    # Sell Delta වැඩි (-), ඒත් Price එක වැටෙන්නෙ නැත්නම් = Sellers Absorb වෙලා = Bullish Absorption
    # Buy Delta වැඩි (+), ඒත් Price එක උඩට යන්නෙ නැත්නම් = Buyers Absorb වෙලා = Bearish Absorption
    recent = trades[-300:]
    r_buy = sum([float(t['q']) for t in recent if not t['m']])
    r_sell = sum([float(t['q']) for t in recent if t['m']])
    r_delta = r_buy - r_sell
    # Price Change in recent trades
    price_start = float(trades[-300]['p']); price_end = float(trades[-1]['p'])
    price_change_pct = (price_end - price_start)/price_start*100
    # Absorption: Delta එක ලොකුයි (-2 BTC ට වැඩි) ඒත් Price Change එක පොඩියි (0.05% ට අඩු)
    bull_absorption = (r_delta < -1.0) and (abs(price_change_pct) < 0.05) and (price_end >= price_start) # Sell ආවත් Price වැටුනෙ නෑ
    bear_absorption = (r_delta > 1.0) and (abs(price_change_pct) < 0.05) and (price_end <= price_start) # Buy ආවත් Price උඩ ගියෙ නෑ
    return delta_pct, cvd_rising, cvd_slope, bull_absorption, bear_absorption, r_delta, price_change_pct

print("BOT STARTED - ULTIMATE 6-IN-1")
send_telegram("🔥 ULTIMATE BOT ON - 6 IN 1\n1. FRVP LVN\n2. Break + Retest\n3. Price Action\n4. Delta Absorption\n5. CVD\n6. VWAP Bands 1-2-3\nBTCUSDT 5M Testnet")

last_candle = 0
in_position = False
pending_break = None

while True:
    try:
        klines = get_klines(100)
        closes = [float(k[4]) for k in klines]
        price = closes[-1]
        candle_time = klines[-1][0]
        if candle_time == last_candle:
            time.sleep(20); continue
        last_candle = candle_time

        # 1. FRVP
        poc, lvn_list = get_volume_profile(klines)
        # 6. VWAP Bands
        vwap, v1u, v1d, v2u, v2d, v3u, v3d, std = get_vwap_bands(klines)
        # 3. Price Action
        bull_pa, bear_pa, pa_name = get_price_action(klines)
        # 4+5. Orderflow
        trades = get_agg_trades(1500)
        delta_pct, cvd_rising, cvd_slope, bull_abs, bear_abs, r_delta, p_change = get_orderflow(trades)
        ema9 = ema(closes,9); ema21 = ema(closes,21)
        funding = get_funding()

        print(f"Price:{price:.0f} POC:{poc:.0f} LVN:{[f'{x:.0f}' for x in lvn_list]} VWAP:{vwap:.0f} +2:{v2u:.0f} -2:{v2d:.0f} PA:{pa_name} Delta:{delta_pct:.1f}% CVD_Rising:{cvd_rising} BullAbs:{bull_abs} BearAbs:{bear_abs} Pending:{pending_break}")

        if in_position:
            time.sleep(60); in_position=False; continue

        # ===== STEP 1: BREAK =====
        if pending_break is None:
            for lvl in lvn_list:
                if closes[-2] < lvl < price:
                    pending_break = {"level": lvl, "dir": "UP", "candles": 0}
                    send_telegram(f"👀 LVN BREAK UP\nLevel: {lvl:.0f}\nPrice: {price:.0f}\nVWAP: {vwap:.0f} | Band2 Up: {v2u:.0f}\nWaiting for Retest + PA + Absorption...")
                elif closes[-2] > lvl > price:
                    pending_break = {"level": lvl, "dir": "DOWN", "candles": 0}
                    send_telegram(f"👀 LVN BREAK DOWN\nLevel: {lvl:.0f}\nPrice: {price:.0f}\nVWAP: {vwap:.0f} | Band2 Down: {v2d:.0f}\nWaiting for Retest + PA + Absorption...")
            time.sleep(10); continue

        # ===== STEP 2: RETEST + ALL CONFIRM =====
        pending_break["candles"] += 1
        if pending_break["candles"] > 6:
            pending_break = None; continue
        lvl = pending_break["level"]
        is_retest = abs(price - lvl) / lvl < 0.0015
        if not is_retest:
            time.sleep(10); continue

        # VWAP Band Filter: LONG එකක් නම් Price එක VWAP එකට උඩින් හෝ Band 2 Down එකේදි Reversal එකක් වෙන්න ඕන
        vwap_ok_long = price > vwap or (abs(price - v2d) < 150) or (abs(price - v3d) < 150)
        vwap_ok_short = price < vwap or (abs(price - v2u) < 150) or (abs(price - v3u) < 150)

        # ===== LONG - ඔක්කොම එකට =====
        # Break UP + Retest + Bull PA + (Bull Absorption OR CVD Rising + Delta +) + VWAP OK + EMA UP
        if pending_break["dir"]=="UP" and is_retest:
            orderflow_ok = (bull_abs or (cvd_rising and delta_pct > 1.0))
            if price > lvl and bull_pa and orderflow_ok and vwap_ok_long and ema9 > ema21:
                sl = lvl - 80
                tp = price + (price - sl)*2.5
                msg = f"🟢 ULTIMATE LONG\n\nEntry: {price:.1f} (Retest LVN {lvl:.0f})\nTP: {tp:.1f} | SL: {sl:.1f} | RR 1:2.5\n\n✅ 1. FRVP LVN Break + Retest\n✅ 2. Price Action: {pa_name}\n✅ 3. Delta Absorption: {'YES 🔥 Sellers Absorbed' if bull_abs else 'No, CVD Confirm'}\n✅ 4. CVD: {'RISING' if cvd_rising else 'FALLING'} Slope {cvd_slope:.2f} | Delta +{delta_pct:.1f}%\n✅ 5. VWAP: {vwap:.0f} | Band2U {v2u:.0f} Band2D {v2d:.0f}\n✅ 6. POC: {poc:.0f} | EMA9>EMA21"
                send_telegram(msg); place_order("BUY", QTY, tp, sl)
                in_position=True; pending_break=None
            else:
                print(f"Retest UP but not all confirm - PA:{bull_pa} {pa_name} Abs:{bull_abs} CVD:{cvd_rising} Delta:{delta_pct:.1f} VWAP_OK:{vwap_ok_long} -> Skip")

        # ===== SHORT =====
        elif pending_break["dir"]=="DOWN" and is_retest:
            orderflow_ok = (bear_abs or (not cvd_rising and delta_pct < -1.0))
            if price < lvl and bear_pa and orderflow_ok and vwap_ok_short and ema9 < ema21:
                sl = lvl + 80
                tp = price - (sl - price)*2.5
                msg = f"🔴 ULTIMATE SHORT\n\nEntry: {price:.1f} (Retest LVN {lvl:.0f})\nTP: {tp:.1f} | SL: {sl:.1f} | RR 1:2.5\n\n✅ 1. FRVP LVN Break + Retest\n✅ 2. Price Action: {pa_name}\n✅ 3. Delta Absorption: {'YES 🔥 Buyers Absorbed' if bear_abs else 'No, CVD Confirm'}\n✅ 4. CVD: {'FALLING' if not cvd_rising else 'RISING'} Slope {cvd_slope:.2f} | Delta {delta_pct:.1f}%\n✅ 5. VWAP: {vwap:.0f} | Band2U {v2u:.0f} Band2D {v2d:.0f}\n✅ 6. POC: {poc:.0f} | EMA9<EMA21"
                send_telegram(msg); place_order("SELL", QTY, tp, sl)
                in_position=True; pending_break=None
            else:
                print(f"Retest DOWN but not all confirm - PA:{bear_pa} {pa_name} Abs:{bear_abs} CVD:{cvd_rising} Delta:{delta_pct:.1f} VWAP_OK:{vwap_ok_short} -> Skip")

        time.sleep(10)
    except Exception as e:
        print("Error:", e); time.sleep(20)
