import time, requests

TELEGRAM_TOKEN = '9267375532:AAH1J6hZGJhlJN6cZiHn8ur-rRUHi7HE-LA'
TELEGRAM_CHAT_ID = '8633386457'

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=15)
        print(f"TG Status: {r.status_code} Reply: {r.text[:200]}", flush=True)
        return r.status_code
    except Exception as e:
        print(f"TG Error: {e}", flush=True)
        return None

print("TEST BOT STARTED", flush=True)
send_telegram("🔥 TEST 1 - Bot eka ON\nMeka awoth Token + Railway hari.")

count = 0
while True:
    try:
        count += 1
        # Bybit එකෙන් Price එක විතරක් ගන්නවා
        r = requests.get("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT", timeout=10)
        data = r.json()
        print(f"Bybit Reply: {data}", flush=True)
        if data.get('retCode') == 0:
            price = data['result']['list'][0]['lastPrice']
            send_telegram(f"✅ TEST {count} - WEDA KARANAWA\nBTC Price: {price}\nBybit Data enawa. Railway + Telegram hari.")
        else:
            send_telegram(f"❌ TEST {count} - Bybit Error\n{data}")
        time.sleep(60)
    except Exception as e:
        print(f"LOOP Error: {e}", flush=True)
        send_telegram(f"❌ LOOP ERROR\n{e}")
        time.sleep(20)
