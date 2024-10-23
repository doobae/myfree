import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime
from prophet import Prophet
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)

# 전역 변수 설정
#api_key = ''        # 실제 API 키
#secret_key = ''     # 실제 Secret 키
#passphrase = ''     # 실제 Passphrase
api_key = 'ef0e145c-9afd-4a02-a5fb-04b8a364a94f'        # 실제 API 키  okx_CW241021
secret_key = 'FAEC20B8FD85B7AFCC99E0E05DB3A123'         # 실제 Secret 키
passphrase = '*Kcw117138'   # 실제 Passphrase
print("Auto-Liveokx4hduMAr_CWSTMA241024 Detected Bot started")
contract_amount = 0.5  # 기본 계약 수량
leverage = 100
symbol = 'BTC-USDT-SWAP'
max_martingale_retries = 3  # 마틴 전략 최대 반복 횟수
martingale_multiplier = 1.5  # 마틴 전략에서 계약 수량을 늘릴 비율
martingale_attempts = 0  # 현재 마틴 전략 반복 횟수
profit_threshold = 2  # 익절 기준
stop_loss_threshold = 1  # 손절 기준
timeframe = '4h'
check_interval = 300  # 5분(300초)마다 잔고를 확인

entry_price = None
sell_order_executed = False
buy_orders_active = True
exchange = None

def initialize_api():
    global exchange
    exchange = ccxt.okx({
        'apiKey': api_key,
        'secret': secret_key,
        'password': passphrase,
    })
    exchange.set_sandbox_mode(False)
    print("OKX 실거래 API가 초기화되었습니다.")
    markets = exchange.load_markets()
    exchange.set_leverage(leverage, symbol)
    print(f"{symbol}에 레버리지 {leverage}배 설정 완료")

initialize_api()

def get_market_data(symbol=symbol, timeframe=timeframe, limit=100):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['close'] = df['close'].astype(float)
    return df

def get_balance():
    balance = exchange.fetch_balance()
    if 'USDT' in balance['total']:
        return balance['total']['USDT']
    else:
        print("잔고 없음")
        return 0

def predict_price(df):
    df_prophet = df[['timestamp', 'close']].rename(columns={'timestamp': 'ds', 'close': 'y'})
    model = Prophet()
    model.fit(df_prophet)
    
    future = model.make_future_dataframe(periods=1, freq='H')
    forecast = model.predict(future)
    
    predicted_price = forecast['yhat'].iloc[-1]
    current_price = df['close'].iloc[-1]
    
    return predicted_price, current_price

def calculate_indicators(df):
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    close = df['close'].astype(float)

    low_min = low.rolling(window=14).min()
    high_max = high.rolling(window=14).max()
    df['slowk'] = 100 * (close - low_min) / (high_max - low_min)
    df['slowd'] = df['slowk'].rolling(window=3).mean()

    short_ema = close.ewm(span=12, adjust=False).mean()
    long_ema = close.ewm(span=26, adjust=False).mean()
    df['macd'] = short_ema - long_ema
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    return df

def check_signals(df):
    last_row = df.iloc[-1]

    if last_row['slowk'] < last_row['slowd']:
        return 'stochastic_cross_down'

    if last_row['macd'] > last_row['macd_signal']:
        return 'macd_cross_up'

    return None

def place_order(side='buy', size=contract_amount):
    try:
        if side == 'buy':
            exchange.create_order(symbol, 'market', 'buy', size, params={"posSide": "long"})
        elif side == 'sell':
            exchange.create_order(symbol, 'market', 'sell', size, params={"posSide": "short"})
        print(f"{side.upper()} 주문 실행, 수량: {size}")
    except Exception as e:
        print(f"주문 실행 중 오류 발생: {e}")

def manage_trailing_stop(entry_price, current_price, trailing_stop_percent=0.01):
    stop_loss_price = entry_price * (1 - trailing_stop_percent)
    if current_price <= stop_loss_price:
        return 'trailing_stop'
    return None

def manage_risk(current_price, entry_price):
    global martingale_attempts, contract_amount
    
    if current_price >= entry_price * (1 + profit_threshold / 100):
        print("수익 발생, 익절 주문 실행")
        place_order(side='sell')
        martingale_attempts = 0  # 마틴 전략 초기화
        contract_amount = 0.5  # 기본 계약량으로 복귀
        return 'take_profit'

    if current_price <= entry_price * (1 - stop_loss_threshold / 100):
        print("손실 발생, 손절 주문 실행")
        place_order(side='sell')
        martingale_attempts += 1
        
        if martingale_attempts <= max_martingale_retries:
            contract_amount *= martingale_multiplier
            print(f"마틴 전략 실행, 새로운 계약 수량: {contract_amount}")
            place_order(side='buy')
        else:
            print("마틴 전략 최대 반복 횟수 도달, 거래 종료")
            contract_amount = 0.5  # 다시 기본 계약량으로 복귀
        return 'stop_loss'

    return None

def trading_bot():
    global entry_price, sell_order_executed, buy_orders_active, martingale_attempts
    last_print_time = time.time()

    while True:
        df = get_market_data()
        df = calculate_indicators(df)

        signal = check_signals(df)

        if signal == 'macd_cross_up' and entry_price is None and buy_orders_active:
            predicted_price, current_price = predict_price(df)
            print(f"예측된 가격: {predicted_price}, 현재 가격: {current_price}")
            
            if predicted_price > current_price:
                place_order(side='buy')
                entry_price = df['close'].iloc[-1]
                print(f"매수 주문 체결, 진입가: {entry_price}")

        elif signal == 'stochastic_cross_down' and entry_price is not None and not sell_order_executed:
            predicted_price, current_price = predict_price(df)
            print(f"예측된 가격: {predicted_price}, 현재 가격: {current_price}")
            
            if predicted_price < current_price:
                place_order(side='sell')
                print(f"매도 주문 체결, 매도가: {df['close'].iloc[-1]}")
                entry_price = df['close'].iloc[-1]
                sell_order_executed = True

        elif sell_order_executed and entry_price is not None:
            current_price = df['close'].iloc[-1]
            action = manage_risk(current_price, entry_price)
            if action == 'take_profit' or action == 'stop_loss':
                entry_price = None
                sell_order_executed = False
                buy_orders_active = True

        if time.time() - last_print_time >= check_interval:
            current_balance = get_balance()
            current_price = df['close'].iloc[-1]
            position_size = contract_amount if entry_price is not None else 0
            print(f"[상황 출력] 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, 잔고(USDT): {current_balance:.2f}, "
                  f"현재 가격(BTC-USDT): {current_price:.2f}, 진입 상태(계약 수량): {position_size}")

            last_print_time = time.time()

        time.sleep(300)

if __name__ == "__main__":
    trading_bot()