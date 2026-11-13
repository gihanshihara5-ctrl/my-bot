TELEGRAM_TOKEN = '9267375532:AAFhhcRPjl1aIyhRyThfKufiR3BOwNZOQOI'
TELEGRAM_CHAT_ID = '270071978'
'apiKey': 'Nuc5RSejHCRKp7rCiOjKUeI4IKFvGrOM18wyl93J44T7xYaOLu2kicmPJMHcoe2R'
'secret': 'oizNPD7yuvVCHGnB3nfkX0T2IqlKZnBa2iw0tV6ERJ25yHwOJN6Hxa0c5WUeWne6'
import ccxt
import requests
import time

TELEGRAM_TOKEN = '9267375532:AAFhhcRPjl1aIyhRyThfKufiR3BOwNZOQOI'
TELEGRAM_CHAT_ID = '270071978'
API_KEY = 'PASTE_NEW_API_KEY_HERE'
API_SECRET = 'PASTE_NEW_SECRET_HERE'

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
