import time
import requests
from binance.client import Client

# --- KEYS ---
TELEGRAM_TOKEN = '9267375532:AAH1J6hZGJhlJN6cZiHn8ur-rRUHi7HE-LA'
TELEGRAM_CHAT_ID = '270071978'
API_KEY = 'uP46cbi6kUNxEBfTnhbmyacZOA7lXkGMVgW9ZyqS7YGazkX68nrGNN6HJSufPVjE'
API_SECRET = 'NClZHFXbA1OvsYElpg4LUoTEG7OM9vRaKAHVZmTl3pXfpBt2hiIKHZm1N0gjRV4Q'

# Binance Futures Testnet - US Block නැති Link එක
client = Client(API_KEY, API_SECRET, testnet=True)
client.FUTURES_URL = 'https://testnet.binancefuture.com'

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
        price = float(client.futures_symbol_ticker(symbol="BTCUSDT")['price'])
        print(f"BTC Price: {price}")
        time.sleep(60)
    except Exception as e:
        print("Error:", e)
        time.sleep(10)
