import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
from prophet import Prophet
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

# Global settings
api_key = '6e7e839f-207b-4a09-8993-03c0ceb73028'        # 실제 API 키
secret_key = 'A055683D48D5BC36A3AD9E3E8727281F'  # 실제 Secret 키
passphrase = 'K1b2k3b/'   # 실제 Passphrase
print("Auto-Liveokx1hAI_YHMA241018 Detected Bot started")
contract_amount = 0.1  # Starting contract size
martingale_factor = 1.5  # Multiplier for Martingale strategy
max_martingale_attempts = 3  # Max Martingale steps
trailing_stop_multiplier = 1.5  # Trailing stop adjustment factor based on volatility (ATR)
symbol = 'BTC-USDT-SWAP'
leverage = 100
timeframe = '1h'  # 1-hour timeframe

# Initialize API
def initialize_api():
    global exchange
    exchange = ccxt.okx({
        'apiKey': api_key,
        'secret': secret_key,
        'password': passphrase,
    })
    exchange.set_sandbox_mode(False)  # Enable for live trading
    exchange.load_markets()
    exchange.set_leverage(leverage, symbol)
    print(f"Leverage set to {leverage}x on {symbol}")

initialize_api()

# Fetch market data
def get_market_data(symbol=symbol, timeframe=timeframe, limit=100):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

# Calculate indicators
def calculate_indicators(df):
    close = df['close'].astype(float)
    
    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD
    short_ema = close.ewm(span=12, adjust=False).mean()
    long_ema = close.ewm(span=26, adjust=False).mean()
    df['macd'] = short_ema - long_ema
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    # ADX (trend strength indicator)
    df['adx'] = calculate_adx(df)
    
    # ATR for volatility-based trailing stop
    df['atr'] = calculate_atr(df)

    return df

# ADX Calculation
def calculate_adx(df):
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    close = df['close'].astype(float)

    plus_dm = high.diff()
    minus_dm = low.diff()
    tr = np.maximum(high - low, np.maximum(abs(high - close.shift(1)), abs(low - close.shift(1))))
    
    atr = tr.rolling(window=14).mean()
    plus_di = 100 * plus_dm.ewm(span=14, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(span=14, adjust=False).mean() / atr
    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
    adx = dx.ewm(span=14, adjust=False).mean()
    
    return adx

# ATR Calculation
def calculate_atr(df):
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    close = df['close'].astype(float)
    
    tr = np.maximum(high - low, np.maximum(abs(high - close.shift(1)), abs(low - close.shift(1))))
    atr = tr.rolling(window=14).mean()
    return atr

# Place order
def place_order(side, size):
    try:
        order = exchange.create_order(symbol, 'market', side, size)
        print(f"Order placed: {side}, Size: {size}")
        return order
    except Exception as e:
        print(f"Order failed: {e}")

# Implement trailing stop
def trailing_stop(entry_price, current_price, atr):
    stop_price = entry_price + (atr * trailing_stop_multiplier)
    if current_price <= stop_price:
        place_order('sell', contract_amount)
        print(f"Trailing stop triggered: Selling at {current_price}")
        return True
    return False

# Main trading bot logic
def trading_bot():
    global contract_amount
    martingale_attempts = 0
    entry_price = None
    trailing_stop_active = False

    while True:
        df = get_market_data()
        df = calculate_indicators(df)
        last_row = df.iloc[-1]
        
        # Check buy signal (RSI < 30, MACD crossover, ADX > 25 for strong trend)
        if last_row['rsi'] < 30 and last_row['macd'] > last_row['macd_signal'] and last_row['adx'] > 25:
            if entry_price is None:  # If no position is active
                place_order('buy', contract_amount)
                entry_price = last_row['close']
                print(f"Buy executed at {entry_price}")
        
        # Check trailing stop
        if entry_price and trailing_stop_active:
            current_price = last_row['close']
            atr = last_row['atr']
            if trailing_stop(entry_price, current_price, atr):
                entry_price = None
                trailing_stop_active = False
                continue  # Skip rest of the loop

        # Martingale strategy: If loss > 10%, double position size
        if entry_price and last_row['close'] < entry_price * 0.9:
            if martingale_attempts < max_martingale_attempts:
                contract_amount *= martingale_factor
                martingale_attempts += 1
                place_order('buy', contract_amount)
                entry_price = last_row['close']
                print(f"Martingale buy executed, new size: {contract_amount}")
            else:
                print("Max martingale attempts reached. Exiting trade.")
                place_order('sell', contract_amount)
                entry_price = None
                contract_amount = 0.1
                martingale_attempts = 0

        time.sleep(3600)  # 1-hour interval

# Start the bot
if __name__ == "__main__":
    trading_bot()