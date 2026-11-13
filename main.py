import time
import requests

TELEGRAM_TOKEN = '9267375532:AAH1J6hZGJhlJN6cZiHn8ur-rRUHi7HE-LA'
TELEGRAM_CHAT_ID = '8633386457'


def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        print("Telegram Sent")
    except Exception as e:
        print("Telegram Error:", e)

print("BOT STARTED")
send_telegram("🔥 ULTIMATE 5M BOT ON - Testnet Connected")

while True:
    try:
        # Binance Futures Testnet - US Block නැති Link එක
        r = requests.get("https://testnet.binancefuture.com/fapi/v1/ticker/price?symbol=BTCUSDT", timeout=10)
        price = r.json()['price']
        print(f"BTC Price: {price}")
        time.sleep(60)
    except Exception as e:
        print("Error:", e)
        time.sleep(10)
