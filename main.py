import time, requests, math, traceback

TELEGRAM_TOKEN = '9267375532:AAH1J6hZGJhlJN6cZiHn8ur-rRUHi7HE-LA'
TELEGRAM_CHAT_ID = '8633386457'
# Bybit - Binance වගේ US Block නෑ, Railway එකේ වැඩ
BASE = "https://api.bybit.com"
SYMBOL = "BTCUSDT"
# ==========================

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=15)
        print("TG Sent", flush=True)
    except Exception as e:
        print("TG Error:", e, flush=True)

def get_klines(limit=100):
    # Bybit Kline: [start, open, high, low, close, volume, turnover]
    try:
        r = requests.get(f"{BASE}/v5/market/kline?category=linear&symbol={SYMBOL}&interval=5&limit={limit}", timeout=10)
        data = r.json()
        print(f"Bybit Kline: {data.get('retMsg')} code: {data.get('retCode')}", flush=True)
        if data.get('retCode') != 0:
            print("Bybit Error:", data, flush=True)
            return None
        lst = data['result']['list']  # Bybit එක අලුත් එක උඩින් එවනවා, අපි පරණ එක යටට දානවා
        lst = lst[::-1]  # Reverse කරලා පරණ -> අලුත් කරනවා
        # අපේ Code එකට ගැලපෙන්න Binance Format එකට හරවනවා: [time, open, high, low, close, volume]
        klines = []
        for k in lst:
            klines.append([int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])])
        return klines
    except Exception as e:
        print("Klines Error:", e, flush=True)
        return None

def get_agg_trades(limit=1000):
    # Bybit Recent Trades: side = Buy / Sell
    # Buy = Aggressive Buy, Sell = Aggressive Sell
    try:
        r = requests.get(f"{BASE}/v5/market/recent-trade?category=linear&symbol={SYMBOL}&limit={limit}", timeout=10)
        data = r.json()
        if data.get('retCode') != 0:
            print("Trades Error:", data, flush=True)
            return None
        trades = []
        for t in data['result']['list']:
            # අපේ Code එකට ගැලපෙන්න: q = size, m = False නම් Buy, True නම් Sell, p = price
            is_buy = (t['side'] == 'Buy')
            trades.append({'q': float(t['size']), 'm': not is_buy, 'p': float(t['price'])})
        trades = trades[::-1]  # පරණ -> අලුත්
        return trades
    except Exception as e:
        print("Trades Error:", e, flush=True)
        return None

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

print("BOT STARTED - V10 BYBIT", flush=True)
send_telegram("🔥 BOT ON - V10 BYBIT\nBinance Block eka fix kala.\nDan Bybit Data (US Block ne)\nAPI Key ne. Signal witharai.\n\n1. FRVP LVN\n2. Break + Retest\n3. Price Action\n4. Delta Absorption\n5. CVD\n6. VWAP Bands")

last_candle = 0
pending_break = None

while True:
    try:
        klines = get_klines(100)
        if klines is None:
            print("Klines None, retry 20s", flush=True)
            time.sleep(20); continue
        closes = [float(k[4]) for k in klines]
        price = closes[-1]; candle_time = klines[-1][0]
        if candle_time == last_candle:
            time.sleep(20); continue
        last_candle = candle_time
        poc, lvn_list = get_volume_profile(klines)
        vwap, v1u, v1d, v2u, v2d, v3u, v3d = get_vwap_bands(klines)
        bull_pa, bear_pa, pa_name = get_price_action(klines)
        trades = get_agg_trades(1000)
        if trades is None:
            time.sleep(20); continue
        delta_pct, cvd_rising, cvd_slope, bull_abs, bear_abs = get_orderflow(trades)
        ema9 = ema(closes,9); ema21 = ema(closes,21)
        print(f"Price:{price:.0f} POC:{poc:.0f} LVN:{[f'{x:.0f}' for x in lvn_list]} VWAP:{vwap:.0f} PA:{pa_name} Delta:{delta_pct:.1f} CVD:{cvd_rising} BullAbs:{bull_abs} BearAbs:{bear_abs} Pending:{pending_break}", flush=True)
        if pending_break is None:
            found = False
            for lvl in lvn_list:
                if closes[-2] < lvl < price:
                    pending_break = {"level": lvl, "dir": "UP", "candles": 0}; found=True
                    send_telegram(f"👀 BREAK UP - LVN {lvl:.0f}\nPrice: {price:.0f}\nVWAP: {vwap:.0f}\nRetest enakan inna... (Bybit)")
                elif closes[-2] > lvl > price:
                    pending_break = {"level": lvl, "dir": "DOWN", "candles": 0}; found=True
                    send_telegram(f"👀 BREAK DOWN - LVN {lvl:.0f}\nPrice: {price:.0f}\nVWAP: {vwap:.0f}\nRetest enakan inna... (Bybit)")
            if not found:
                send_telegram(f"📊 SCAN 5M - Bybit\nPrice: {price:.0f}\nPOC: {poc:.0f} | Nearest LVN: {min(lvn_list, key=lambda x: abs(x-price)):.0f}\nVWAP: {vwap:.0f} | V2U: {v2u:.0f} V2D: {v2d:.0f}\nPA: {pa_name} | Delta: {delta_pct:.1f}% | CVD: {'UP 🟢' if cvd_rising else 'DOWN 🔴'}\nAbsorption: Bull {bull_abs} Bear {bear_abs}\n⏳ LVN Break ekak na.")
            time.sleep(10); continue
        pending_break["candles"] += 1
        if pending_break["candles"] > 10:
            send_telegram(f"❌ Break Cancel - Retest awe na\nLevel: {pending_break['level']:.0f}")
            pending_break = None; continue
        lvl = pending_break["level"]
        is_retest = abs(price - lvl) / lvl < 0.003
        if not is_retest:
            send_telegram(f"⏳ Waiting Retest...\nLevel: {lvl:.0f} | Price: {price:.0f} | Gap: {abs(price-lvl):.0f}\nPA: {pa_name} | CVD: {'UP' if cvd_rising else 'DOWN'}")
            time.sleep(10); continue
        if pending_break["dir"]=="UP":
            score=0; reasons=[]
            if price > lvl: score+=1; reasons.append("✅ Retest Hold")
            if bull_pa: score+=1; reasons.append(f"✅ PA: {pa_name}")
            if bull_abs: score+=1; reasons.append("✅ Bull Absorption 🔥")
            if cvd_rising and delta_pct > 0.5: score+=1; reasons.append(f"✅ CVD UP Delta +{delta_pct:.1f}%")
            if price > vwap or abs(price-v2d)<200: score+=1; reasons.append("✅ VWAP OK")
            if ema9 > ema21: score+=1; reasons.append("✅ EMA UP")
            if score >= 4:
                sl = lvl - 80; tp = price + (price - sl)*2.5; tp2 = price + (price - sl)*4
                send_telegram(f"🟢 LONG SIGNAL - SCORE {score}/6 - Bybit\n\nPair: BTCUSDT 5M\nEntry: {price:.1f}\n🎯 TP1: {tp:.1f}\n🎯 TP2: {tp2:.1f}\n🛑 SL: {sl:.1f}\nRR: 1:2.5\n\n" + "\n".join(reasons) + f"\nPOC: {poc:.0f} | VWAP: {vwap:.0f}")
                pending_break=None
            else:
                send_telegram(f"⚠️ Retest awa, eth Score madi: {score}/6\nLevel: {lvl:.0f} Price: {price:.0f}\n" + "\n".join(reasons))
        elif pending_break["dir"]=="DOWN":
            score=0; reasons=[]
            if price < lvl: score+=1; reasons.append("✅ Retest Reject")
            if bear_pa: score+=1; reasons.append(f"✅ PA: {pa_name}")
            if bear_abs: score+=1; reasons.append("✅ Bear Absorption 🔥")
            if not cvd_rising and delta_pct < -0.5: score+=1; reasons.append(f"✅ CVD DOWN Delta {delta_pct:.1f}%")
            if price < vwap or abs(price-v2u)<200: score+=1; reasons.append("✅ VWAP OK")
            if ema9 < ema21: score+=1; reasons.append("✅ EMA DOWN")
            if score >= 4:
                sl = lvl + 80; tp = price - (sl - price)*2.5; tp2 = price - (sl - price)*4
                send_telegram(f"🔴 SHORT SIGNAL - SCORE {score}/6 - Bybit\n\nPair: BTCUSDT 5M\nEntry: {price:.1f}\n🎯 TP1: {tp:.1f}\n🎯 TP2: {tp2:.1f}\n🛑 SL: {sl:.1f}\nRR: 1:2.5\n\n" + "\n".join(reasons) + f"\nPOC: {poc:.0f} | VWAP: {vwap:.0f}")
                pending_break=None
            else:
                send_telegram(f"⚠️ Retest awa, eth Score madi: {score}/6\nLevel: {lvl:.0f} Price: {price:.0f}\n" + "\n".join(reasons))
        time.sleep(10)
    except Exception as e:
        print("ERROR:", traceback.format_exc(), flush=True)
        send_telegram(f"❌ ERROR\n{str(e)[:300]}")
        time.sleep(20)
