#1 Liveokx1hdual_YHSTMA241010-> Succ후 one way mode 로 2024.10.17
import ccxt  # CCXT 라이브러리를 이용해 거래소 API를 제어
import pandas as pd  # 데이터를 다루기 위한 판다스 라이브러리
import numpy as np  # 수학적 연산을 위한 넘파이
import time  # 시간 제어를 위한 라이브러리
from datetime import datetime, timedelta  # 날짜와 시간을 다루기 위한 라이브러리
from prophet import Prophet  # 시계열 예측을 위한 Prophet 라이브러리 추가
import warnings  # 경고를 무시하기 위한 라이브러리
warnings.simplefilter(action='ignore', category=FutureWarning)

# 전역 변수 설정
api_key = '6e7e839f-207b-4a09-8993-03c0ceb73028'        # 실제 API 키
secret_key = 'A055683D48D5BC36A3AD9E3E8727281F'  # 실제 Secret 키
passphrase = 'K1b2k3b/'   # 실제 Passphrase
print("Auto-Liveokx1hdual_YHSTMA241010 Detected Bot started")

# 거래할 계약 수량을 0.1로 설정

entry_price = None  # 진입가를 저장할 변수
sell_order_executed = False  # 매도 주문 실행 여부를 추적
buy_orders_active = True  # 매수 주문 활성화 여부
leverage = 50  # 레버리지를 50배로 설정
contract_amount = 0.1  #1 거래할 계약 수량을 0.1로 설정
symbol = 'BTC-USDT-SWAP'  #2 OKX BTC 선물 상품 선택
leverage = 50  #3 레버리지를 50배로 설정
timeframe = '1h'  #4 1시간 타임프레임 설정
exchange = None  #5 CCXT 거래소 객체 초기화

# OKX API 초기화 함수
def initialize_api():
    global exchange
    # CCXT를 이용해 OKX 거래소 객체 생성
    exchange = ccxt.okx({
        'apiKey': api_key,
        'secret': secret_key,
        'password': passphrase,
    })
    exchange.set_sandbox_mode(False)  # 실거래 모드 설정
    print("OKX 실거래 API가 초기화되었습니다.")

    # 기존 포지션 및 주문 청산
    cancel_open_orders()
    close_all_positions()

    # 포지션 모드를 One-way 모드로 변경
    try:
        exchange.set_position_mode(False)  # One-way 모드로 설정
        print("One-way 모드로 전환되었습니다.")
    except Exception as e:
        print(f"포지션 모드를 설정하는 중 오류 발생: {e}")

    # 레버리지 설정
    markets = exchange.load_markets()
    exchange.set_leverage(leverage, symbol)
    print(f"{symbol}에 레버리지 {leverage}배 설정 완료")

# 열린 주문을 취소하는 함수
def cancel_open_orders():
    try:
        open_orders = exchange.fetch_open_orders(symbol)
        for order in open_orders:
            exchange.cancel_order(order['id'], symbol)
        print("열린 주문이 모두 취소되었습니다.")
    except Exception as e:
        print(f"열린 주문을 취소하는 중 오류 발생: {e}")

# 모든 포지션을 종료하는 함수
def close_all_positions():
    try:
        positions = exchange.fetch_positions()
        for position in positions:
            if position['symbol'] == symbol and position['contracts'] > 0:
                if position['side'] == 'long':
                    exchange.create_order(symbol, 'market', 'sell', position['contracts'])
                elif position['side'] == 'short':
                    exchange.create_order(symbol, 'market', 'buy', position['contracts'])
        print("모든 포지션이 종료되었습니다.")
    except Exception as e:
        print(f"포지션을 종료하는 중 오류 발생: {e}")

initialize_api()  # API 초기화

# 시장 데이터를 수집하는 함수
def get_market_data(symbol=symbol, timeframe=timeframe, limit=100):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['close'] = df['close'].astype(float)
    return df

# Prophet을 사용해 1시간 후 가격을 예측하는 함수
def predict_price(df):
    df_prophet = df[['timestamp', 'close']].rename(columns={'timestamp': 'ds', 'close': 'y'})
    model = Prophet()
    model.fit(df_prophet)
    
    future = model.make_future_dataframe(periods=1, freq='H')
    forecast = model.predict(future)
    
    predicted_price = forecast['yhat'].iloc[-1]
    current_price = df['close'].iloc[-1]
    
    return predicted_price, current_price

# 기술적 지표를 계산하는 함수 (스토캐스틱 및 MACD)
def calculate_indicators(df):
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    close = df['close'].astype(float)

    low_min = low.rolling(window=14).min()
    high_max = high.rolling(window=14).max()
    df['slowk'] = 100 * (close - low_min) / (high_max - low_min)
    df['slowd'] = df['slowk'].rolling(window=3).mean()

    short_ema = close.ewm(span=15, adjust=False).mean()
    long_ema = close.ewm(span=30, adjust=False).mean()
    df['macd'] = short_ema - long_ema
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    return df

# 시그널을 감지하는 함수
def check_signals(df):
    last_row = df.iloc[-1]

    if last_row['slowk'] > last_row['slowd']:
        return 'stochastic_cross_up'

    if last_row['macd'] < last_row['macd_signal']:
        return 'macd_cross_down'

    return None

# 거래 주문을 실행하는 함수
def place_order(side='buy', size=contract_amount):
    try:
        if side == 'buy':
            exchange.create_order(symbol, 'market', 'buy', size)
        elif side == 'sell':
            exchange.create_order(symbol, 'market', 'sell', size)
        print(f"{side.upper()} 주문 실행, 수량: {size}")
    except Exception as e:
        print(f"주문 실행 중 오류 발생: {e}")

# 트레일링 스탑을 이용한 수익 및 손실 관리 함수
def manage_trailing_stop(entry_price, current_price, trailing_stop_percent=0.01):
    stop_loss_price = entry_price * (1 - trailing_stop_percent)
    if current_price <= stop_loss_price:
        return 'trailing_stop'
    return None

# 메인 트레이딩 루프
def trading_bot():
    entry_price = None
    sell_order_executed = False
    buy_orders_active = True
    
    while True:
        df = get_market_data()
        df = calculate_indicators(df)
        predicted_price, current_price = predict_price(df)

        signal = check_signals(df)
        
        if signal == 'stochastic_cross_up' and buy_orders_active:
            place_order('buy', contract_amount)
            entry_price = current_price
            buy_orders_active = False

        elif signal == 'macd_cross_down' and entry_price and not sell_order_executed:
            place_order('sell', contract_amount)
            sell_order_executed = True

        if entry_price:
            trailing_stop_signal = manage_trailing_stop(entry_price, current_price)
            if trailing_stop_signal == 'trailing_stop':
                place_order('sell', contract_amount)
                entry_price = None
                sell_order_executed = False
                buy_orders_active = True

        time.sleep(60 * 60)  # 1시간마다 반복

# 트레이딩 봇 시작
trading_bot()