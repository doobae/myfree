import ccxt  # CCXT 라이브러리를 이용해 거래소 API를 제어
import pandas as pd  # 데이터를 다루기 위한 판다스 라이브러리
import numpy as np  # 수학적 연산을 위한 넘파이
import time  # 시간 제어를 위한 라이브러리
from datetime import datetime, timedelta  # 날짜와 시간을 다루기 위한 라이브러리
from prophet import Prophet  # 시계열 예측을 위한 Prophet 라이브러리 추가
import warnings  # 경고를 무시하기 위한 라이브러리
warnings.simplefilter(action='ignore', category=FutureWarning)

# 전역 변수 설정
#api_key = '6e7e839f-207b-4a09-8993-03c0ceb73028'        # 실제 API 키
#secret_key = 'A055683D48D5BC36A3AD9E3E8727281F'  # 실제 Secret 키
#passphrase = 'K1b2k3b/'   # 실제 Passphrase
api_key = 'ef0e145c-9afd-4a02-a5fb-04b8a364a94f'        # 실제 API 키  okx_CW241021
secret_key = 'FAEC20B8FD85B7AFCC99E0E05DB3A123'         # 실제 Secret 키
passphrase = '*Kcw117138'   # 실제 Passphrase
print("Auto-Liveokx4hdual_CWSTMA241023 Detected Bot started")
#--------------------
contract_amount = 1  
demo_mode = False
entry_price = None
sell_order_executed = False
buy_orders_active = True
symbol = 'BTC-USDT-SWAP'
exchange = None
leverage = 100
timeframe = '4h'

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

    # 기존 지표 계산
    low_min = low.rolling(window=14).min()
    high_max = high.rolling(window=14).max()
    df['slowk'] = 100 * (close - low_min) / (high_max - low_min)
    df['slowd'] = df['slowk'].rolling(window=3).mean()

    short_ema = close.ewm(span=12, adjust=False).mean()
    long_ema = close.ewm(span=26, adjust=False).mean()
    df['macd'] = short_ema - long_ema
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()

    # 새로운 지표 추가: RSI, 볼린저 밴드
    df['rsi'] = 100 - (100 / (1 + close.diff().rolling(window=14).apply(lambda x: (x[x > 0].sum()) / (-x[x < 0].sum()), raw=True)))
    df['upper_band'], df['middle_band'], df['lower_band'] = bollinger_bands(close)

    return df

def bollinger_bands(close, window=20, no_of_std=2):
    rolling_mean = close.rolling(window).mean()
    rolling_std = close.rolling(window).std()
    upper_band = rolling_mean + (rolling_std * no_of_std)
    lower_band = rolling_mean - (rolling_std * no_of_std)
    return upper_band, rolling_mean, lower_band

def manage_risk(current_price, entry_price, stop_loss=0.01, take_profit=0.02):
    """동적 손절 및 익절 관리"""
    if entry_price is not None:
        # 손절/익절 기준 가격 계산
        stop_loss_price = entry_price * (1 - stop_loss)
        take_profit_price = entry_price * (1 + take_profit)

        if current_price <= stop_loss_price:
            return 'stop_loss'
        elif current_price >= take_profit_price:
            return 'take_profit'
    return None

def check_signals(df):
    last_row = df.iloc[-1]

    if last_row['slowk'] < last_row['slowd'] and last_row['rsi'] < 30:
        return 'stochastic_cross_down'

    if last_row['macd'] > last_row['macd_signal'] and last_row['rsi'] > 70:
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

def trading_bot():
    global entry_price, sell_order_executed, buy_orders_active
    last_print_time = time.time()

    while True:
        df = get_market_data()
        df = calculate_indicators(df)

        signal = check_signals(df)

        # 기존 전략 + 리스크 관리 적용
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

        # 리스크 관리 추가
        elif sell_order_executed and entry_price is not None:
            current_price = df['close'].iloc[-1]
            action = manage_risk(current_price, entry_price)
            if action == 'stop_loss':
                place_order(side='sell')
                print("손절 실행!")
                entry_price = None
                sell_order_executed = False
                buy_orders_active = True
            elif action == 'take_profit':
                place_order(side='sell')
                print("익절 실행!")
                entry_price = None
                sell_order_executed = False
                buy_orders_active = True

        if time.time() - last_print_time >= 300:
            current_balance = get_balance()
            current_price = df['close'].iloc[-1]
            position_size = contract_amount if entry_price is not None else 0
            print(f"[상황 출력] 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, 잔고(USDT): {current_balance:.2f}, "
                  f"현재 가격(BTC-USDT): {current_price:.2f}, 진입 상태(계약 수량): {position_size}")

            last_print_time = time.time()

        time.sleep(600)

if __name__ == "__main__":
    trading_bot()