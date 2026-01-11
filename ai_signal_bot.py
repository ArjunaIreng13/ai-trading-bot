import os
import logging
import asyncio
import ccxt
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import mplfinance as mpf
from telegram import Bot
from telegram.constants import ParseMode
from datetime import datetime
import pytz

# --- KONFIGURASI ---
TELEGRAM_TOKEN = os.getenv('8590140504:AAEzIICakLj3XH1TzvKQFjBbMYQUy3-2WKA')
CHAT_ID = os.getenv('5967294220')

# Daftar Aset
ASSETS = {
    'CRYPTO': {'symbol': 'BTC/USDT', 'source': 'ccxt', 'leverage': '50x', 'market': 'crypto'},
    'LQ45':   {'symbol': 'BBRI.JK',  'source': 'yfinance', 'leverage': '1x', 'market': 'idx'},
    'US_STOCK':{'symbol': 'AAPL',    'source': 'yfinance', 'leverage': '1x', 'market': 'us'},
    'FOREX':  {'symbol': 'EURUSD=X', 'source': 'yfinance', 'leverage': '100x', 'market': 'forex'}
}

# --- FUNGSI CEK JAM OPERASIONAL ---
def is_market_open(market_type):
    now_utc = datetime.now(pytz.utc)
    
    if market_type == 'crypto':
        return True  # Crypto buka 24/7
    
    if market_type == 'idx': # Saham Indonesia (WIB)
        jkt_time = now_utc.astimezone(pytz.timezone('Asia/Jakarta'))
        if jkt_time.weekday() >= 5: return False # Sabtu-Minggu tutup
        # Jam bursa: 09:00 - 16:00 WIB
        return 9 <= jkt_time.hour < 16

    if market_type == 'us': # Saham Amerika (EST)
        us_time = now_utc.astimezone(pytz.timezone('US/Eastern'))
        if us_time.weekday() >= 5: return False
        # Jam bursa: 09:30 - 16:00 EST
        return (us_time.hour == 9 and us_time.minute >= 30) or (10 <= us_time.hour < 16)

    if market_type == 'forex':
        # Forex tutup Sabtu dini hari sampai Senin dini hari
        if now_utc.weekday() == 5: return False # Sabtu tutup
        if now_utc.weekday() == 6 and now_utc.hour < 22: return False # Minggu buka jam 22 UTC
        return True

    return False

# --- LOGIKA TRAILING STOP ---
def calculate_trailing_stop(price, side, distance_pct=0.02):
    # Jarak trailing stop (contoh 2% dari harga entry)
    if side == 'LONG':
        return price * (1 - distance_pct)
    else:
        return price * (1 + distance_pct)

# --- FUNGSI ANALISIS (MODIFIED) ---
def analyze_market(df, side_bias):
    if df is None or len(df) < 30: return None
    
    last_price = df['close'].iloc[-1]
    atr = ta.atr(df['high'], df['low'], df['close'], length=14).iloc[-1]
    
    # Contoh Sinyal Sederhana (RSI)
    df['RSI'] = ta.rsi(df['close'], length=14)
    rsi = df['RSI'].iloc[-1]
    
    signal = None
    if rsi < 30: signal = 'LONG'
    elif rsi > 70: signal = 'SHORT'
    
    if not signal: return None

    # Kalkulasi Target & Trailing
    ts = calculate_trailing_stop(last_price, signal, 0.015) # 1.5% Trailing
    
    return {
        'signal': signal,
        'price': last_price,
        'ts': ts,
        'tp1': last_price + (atr * 2) if signal == 'LONG' else last_price - (atr * 2),
        'score': 85,
        'pattern': "RSI Mean Reversion"
    }

# ... (Gunakan fungsi generate_chart_image dari pesan sebelumnya) ...

async def send_signal():
    bot = Bot(token=TELEGRAM_TOKEN)
    for name, info in ASSETS.items():
        # Cek Jam Operasional
        if not is_market_open(info['market']):
            print(f"Pasar {name} sedang tutup. Skip.")
            continue
            
        df = get_data(info['symbol'], info['source'])
        analysis = analyze_market(df, info['market'])

        if analysis:
            chart_file = generate_chart_image(df, info['symbol'])
            msg = (
                f"🤖 <b>AI AGENT SIGNAL: {name}</b>\n\n"
                f"🎒 <b>Symbol:</b> {info['symbol']}\n"
                f"📈 <b>Action:</b> {analysis['signal']}\n"
                f"💰 <b>Entry:</b> {analysis['price']:.5f}\n"
                f"🏃 <b>Trailing Stop:</b> {analysis['ts']:.5f}\n"
                f"🎯 <b>TP Target:</b> {analysis['tp1']:.5f}\n\n"
                f"🧠 <b>Confidence:</b> {analysis['score']}%\n"
                f"⏰ <i>Server Time: {datetime.now().strftime('%H:%M')}</i>"
            )
            with open(chart_file, 'rb') as photo:
                await bot.send_photo(chat_id=CHAT_ID, photo=photo, caption=msg, parse_mode=ParseMode.HTML)
            os.remove(chart_file)

if __name__ == '__main__':
    asyncio.run(send_signal())
