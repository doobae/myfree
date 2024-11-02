import ccxt
import time
import numpy as np
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

# OKX API 키 설정
#api_key = 'your_api_key_here'
#secret_key = 'your_secret_key_here'
#passphrase = 'your_passphrase_here'#
api_key = 'ef0e145c-9afd-4a02-a5fb-04b8a364a94f'        # 실제 API 키  okx_CW241021
secret_key = 'FAEC20B8FD85B7AFCC99E0E05DB3A123'         # 실제 Secret 키
passphrase = '*Kcw117138'   # 실제 Passphrase
# 전역 변수 설정
MIN_CONTRACT_AMOUNT = 0.2     # 초기 최소 계약량
PNL_TAKE_PROFIT = 0.001       # 익절 비율: 0.1%
PNL_STOP_LOSS = -0.001        # 손절 비율: -0.1%
LEVERAGE = 100                # 레버리지
MAX_MARTINGALE = 4           # 마틴 전략 최대 횟수
TIMEFRAME = '1h'              # 시간 주기
symbol = 'BTC-USDT-SWAP'
SLEEP_INTERVAL = 300           # 반복 주기 (초)

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

def calculate_stochastic(high, low, close, period=14):
    """스토캐스틱 계산"""
    lowest_low = np.min(low[-period:])
    highest_high = np.max(high[-period:])
    
    if highest_high - lowest_low == 0:
        k = 0
    else:
        k = 100 * (close[-1] - lowest_low) / (highest_high - lowest_low)
    
    d = np.mean([100 * (close[i] - np.min(low[-period:])) / (np.max(high[-period:]) - np.min(low[-period:])) for i in range(-3, 0)])  # D값 계산
    
    return k, d

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

    # 시세 데이터 가져오기
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=50)
        data = np.array(ohlcv)
        if len(data) < 14:
            time.sleep(SLEEP_INTERVAL)
            continue
        
        high = data[:, 2]  # 고가
        low = data[:, 3]   # 저가
        close = data[:, 4] # 종가
        k, d = calculate_stochastic(high, low, close, period=15)

    except Exception as e:
        print(f"Error fetching OHLCV data: {e}")
        time.sleep(SLEEP_INTERVAL)
        continue

    # 오픈 포지션 확인
    positions = exchange.fetch_positions([symbol])
    current_position = None
    for position in positions:
        if position['contracts'] > 0:
            current_position = position
            break

    # 스토캐스틱 크로스 상태에 따른 주문 로직
    if current_position is None:  # 포지션이 없을 때
        if k > d:  # 크로스업 시 매수
            place_order(symbol, 'buy', order_amount)
        elif k < d:  # 크로스다운 시 매도
            place_order(symbol, 'sell', order_amount)
    else:
        # 현재 포지션이 있을 때 PnL 확인 후 익절/손절 여부에 따라 청산
        check_pnl_and_close(current_position)

    # 남은 시간 출력 및 대기
    for remaining_time in range(SLEEP_INTERVAL, 0, -1):
        print(f"Next iteration in: {remaining_time} seconds", end='\r')
        time.sleep(1)