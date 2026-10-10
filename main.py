import os
import http.server
import socketserver
import threading
import ccxt
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime

# 1. BIND PORT INSTANTLY FOR RENDER WEB SERVICE
PORT = int(os.environ.get("PORT", 10000))
class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Crypto Paper Trading Bot is Running!")

def run_server():
    with socketserver.TCPServer(("0.0.0.0", PORT), HealthCheckHandler) as httpd:
        httpd.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# 2. BOT CONFIGURATION & TELEGRAM (Testing with 1 Coin: SOL/USDT on 1h)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8434369768:AAGQQp9IXaRw4CkqwSYRk0ZC_NJx1cuLciY')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '6141102520')

PORTFOLIO = {
    'SOL/USDT': {'strategy': 'ORDER_FLOW', 'paper_capital': 1000.0, 'position': 0, 'buy_price': 0}
}

exchange = ccxt.binanceus({'enableRateLimit': True})

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram Alert Error: {e}")

print("🚀 1H PAPER TRADING BOT STARTED...")
send_telegram_alert("🚀 1H PAPER TRADING BOT ACTIVE\n\nMonitoring SOL/USDT on 1-Hour Timeframe!")

def check_signals_and_trade():
    for symbol, config in PORTFOLIO.items():
        try:
            # Changed timeframe from 4h to 1h
            ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            cp = df['close'].iloc[-1]
            hp = df['high'].iloc[-1]
            lp = df['low'].iloc[-1]
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if config['strategy'] == 'ORDER_FLOW':
                vpip = (df['high'] + df['low'] + df['close']) / 3
                df['VWAP'] = (vpip * df['volume']).rolling(20).sum() / df['volume'].rolling(20).sum()
                df['Vol_SMA'] = df['volume'].rolling(20).mean()
                df['Vol_Ratio'] = df['volume'] / df['Vol_SMA']
                df['Bar_Range'] = df['high'] - df['low']
                df['Close_Position'] = np.where(df['Bar_Range'] > 0, (df['close'] - df['low']) / df['Bar_Range'], 0.5)

                vwap = df['VWAP'].iloc[-1]
                vol_ratio = df['Vol_Ratio'].iloc[-1]
                close_pos = df['Close_Position'].iloc[-1]

                if config['position'] > 0:
                    bp = config['buy_price']
                    if lp <= bp * 0.98:
                        config['paper_capital'] = config['position'] * (bp * 0.98)
                        send_telegram_alert(f"🛑 STOP LOSS HIT ({symbol})\nExit Price: ${bp*0.98:.2f}\nPnL: -2.0%\nNew Balance: ${config['paper_capital']:.2f}")
                        config['position'] = 0
                    elif hp >= bp * 1.05:
                        config['paper_capital'] = config['position'] * (bp * 1.05)
                        send_telegram_alert(f"🎯 TAKE PROFIT HIT ({symbol})\nExit Price: ${bp*1.05:.2f}\nPnL: +5.0%\nNew Balance: ${config['paper_capital']:.2f}")
                        config['position'] = 0

                elif (cp > vwap) and (vol_ratio > 1.5) and (close_pos > 0.7) and config['position'] == 0:
                    config['position'] = config['paper_capital'] / cp
                    config['buy_price'] = cp
                    send_telegram_alert(f"🟢 PAPER BUY SIGNAL ({symbol})\nStrategy: Order Flow (1H)\nPrice: ${cp:.2f}\nBought: {config['position']:.4f}\nTime: {now}")

        except Exception as e:
            print(f"Error scanning {symbol}: {e}")

while True:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Scanning 1H Market...")
    check_signals_and_trade()
    time.sleep(300)
                        
