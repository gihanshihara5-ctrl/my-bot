import ccxt
import requests
import time

TELEGRAM_TOKEN = '9267375532:AAH1J6hZGJhlJN6cZiHn8ur-rRUHi7HE-LA'
TELEGRAM_CHAT_ID = '270071978'
API_KEY = 'uP46cbi6kUNxEBfTnhbmyacZOA7lXkGMVgW9ZyqS7YGazkX68nrGNN6HJSufPVjE'
API_SECRET = 'NClZHFXbA1OvsYElpg4LUoTEG7OM9vRaKAHVZmTl3pXfpBt2hiIKHZm1N0gjRV4Q'

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': msg})
    except Exception as e:
        print(e)

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'options': {'defaultType': 'future'},
})
exchange.set_sandbox_mode(True)

print("BOT STARTED")
send_telegram("🔥 ULTIMATE 5M BOT ON - Testnet Connected")

while True:
    try:
        ticker = exchange.fetch_ticker('BTC/USDT')
        print(f"BTC Price: {ticker['last']}")
        time.sleep(60)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(10)
