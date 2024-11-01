import ccxt
import time
import numpy as np
import pandas as pd
from prophet import Prophet
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

# OKX API 키 설정
#api_key = 'your_api_key_here'
#secret_key = 'your_secret_key_here'
#passphrase = 'your_passphrase_here'
api_key = 'ef0e145c-9afd-4a02-a5fb-04b8a364a94f'        # 실제 API 키  okx_CW241021
secret_key = 'FAEC20B8FD85B7AFCC99E0E05DB3A123'         # 실제 Secret 키
passphrase = '*Kcw117138'   # 실제 Passphrase
print("Auto-Liveokx1hPro_CWSuccUp Detected Bot started")
# 전역 변수 설정
MIN_CONTRACT_AMOUNT = 0.1     # 초기 최소 계약량
PNL_TAKE_PROFIT = 0.001       # 익절 비율: 0.1%
PNL_STOP_LOSS = -0.001        # 손절 비율: -0.1%
LEVERAGE = 100                # 레버리지
MAX_MARTINGALE = 3            # 마틴 전략 최대 횟수
TIMEFRAME = '1m'              # 시간 주기
symbol = 'BTC-USDT-SWAP'
SLEEP_INTERVAL = 60           # 반복 주기 (초)

# 마틴 전략 변수
martingale_multiplier = 1     # 주문 배수 (기본: 1)
martingale_count = 0          # 마틴 전략 횟수 추적

# OKX 거래소 객체 생성
exchange = ccxt.okx({
    'apiKey': api_key,
    'secret': secret_key,
    'password': passphrase,
})
exchange.set_sandbox_mode(False)

def fetch_historical_data(symbol):
    """과거 데이터 가져오기"""
    ohlcv = exchange.fetch_ohlcv(symbol, '1m', limit=50)  # 1분 간격으로 50개 데이터
    data = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    data['time'] = pd.to_datetime(data['time'], unit='ms')
    return data[['time', 'close']]

def predict_future_price(data):
    """1분 후 가격 예측"""
    df = data.rename(columns={'time': 'ds', 'close': 'y'})
    model = Prophet()
    model.fit(df)

    future = model.make_future_dataframe(periods=1, freq='min')  # 1분 후 예측
    forecast = model.predict(future)
    return forecast['yhat'].iloc[-1]  # 예측된 값 반환

def place_order(symbol, side, amount):
    """주문 함수 - 시장가로 주문을 생성"""
    try:
        params = {'leverage': LEVERAGE, 'posSide': 'long' if side == 'buy' else 'short'}
        order = exchange.create_market_order(symbol, side, amount, params=params)
        print(f"Order placed - Symbol: {symbol}, Side: {side}, Amount: {amount:.3f}, Order ID: {order['id']}")
        return order
    except Exception as e:
        print(f"Error placing order: {e}")
        return None

def check_pnl_and_close(position):
    """PnL에 따른 포지션 청산 로직"""
    global martingale_multiplier, martingale_count
    pnl = position['unrealizedPnl']
    
    if pnl >= PNL_TAKE_PROFIT:
        print(f"Take Profit Reached: {pnl:.3f}")
        close_position(position)  # 익절 시 포지션 청산
        martingale_multiplier = 1  # 초기화
        martingale_count = 0
    elif pnl <= PNL_STOP_LOSS:
        print(f"Stop Loss Reached: {pnl:.3f}")
        close_position(position)  # 손절 시 포지션 청산
        martingale_count += 1
        if martingale_count <= MAX_MARTINGALE:
            martingale_multiplier *= 2  # 다음 주문에 두 배 증가
        else:
            martingale_multiplier = 1  # 초기화
            martingale_count = 0

def close_position(position):
    """포지션 청산 함수"""
    try:
        side = 'sell' if position['side'] == 'long' else 'buy'
        amount = position['contracts']
        params = {'posSide': position['side']}
        order = exchange.create_market_order(symbol, side, amount, params=params)
        print(f"Closed Position - Symbol: {symbol}, Side: {side}, Amount: {amount:.3f}, Order ID: {order['id']}")
    except Exception as e:
        print(f"Error closing position: {e}")

# 주요 루프
while True:
    # 주문량 설정
    order_amount = MIN_CONTRACT_AMOUNT * martingale_multiplier

    # 과거 데이터 가져오기 및 예측
    historical_data = fetch_historical_data(symbol)
    future_price = predict_future_price(historical_data)

    # 현재 가격 가져오기
    current_price = historical_data['close'].iloc[-1]
    print(f"Current Price: {current_price:.3f}, Predicted Future Price: {future_price:.3f}")

    # 예측 가격에 따른 주문 로직
    if future_price > current_price:  # 상승 예측
        place_order(symbol, 'buy', order_amount)
    elif future_price < current_price:  # 하락 예측
        place_order(symbol, 'sell', order_amount)

    # 오픈 포지션 확인
    positions = exchange.fetch_positions([symbol])
    current_position = None
    for position in positions:
        if position['contracts'] > 0:
            current_position = position
            break

    # 현재 포지션이 있을 때 PnL 확인 후 익절/손절 여부에 따라 청산
    if current_position:
        check_pnl_and_close(current_position)

    # 남은 시간 출력 및 대기
    for remaining_time in range(SLEEP_INTERVAL, 0, -1):
        print(f"Next iteration in: {remaining_time} seconds", end='\r')
        time.sleep(1)