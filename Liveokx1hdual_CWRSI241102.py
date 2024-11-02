import ccxt
import time
import numpy as np
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)

# OKX API 키 설정
api_key = 'ef0e145c-9afd-4a02-a5fb-04b8a364a94f'        # 실제 API 키  okx_CW241021
secret_key = 'FAEC20B8FD85B7AFCC99E0E05DB3A123'         # 실제 Secret 키
passphrase = '*Kcw117138'   # 실제 Passphrase
print("Auto-Liveokx1hdual_CWRSI241102 Detected Bot started")

# 전역 변수 설정
MIN_CONTRACT_AMOUNT = 0.1
PNL_TAKE_PROFIT = 0.01
PNL_STOP_LOSS = -0.01
LEVERAGE = 50
MAX_MARTINGALE = 3
TIMEFRAME = '1h'
symbol = 'BTC-USDT-SWAP'
SLEEP_INTERVAL = 300

martingale_multiplier = 1
martingale_count = 0

# OKX 거래소 객체 생성
exchange = ccxt.okx({
    'apiKey': api_key,
    'secret': secret_key,
    'password': passphrase,
})
exchange.set_sandbox_mode(False)

def calculate_macd(close, short_period=12, long_period=26, signal_period=9):
    """MACD 계산"""
    short_ema = np.convolve(close, np.ones(short_period)/short_period, mode='valid')
    long_ema = np.convolve(close, np.ones(long_period)/long_period, mode='valid')

    macd_line = short_ema[-len(long_ema):] - long_ema
    signal_line = np.convolve(macd_line, np.ones(signal_period)/signal_period, mode='valid')

    return macd_line[-1], signal_line[-1]

def calculate_rsi(close, period=14):
    """RSI 계산"""
    deltas = np.diff(close)
    gain = np.sum(deltas[deltas > 0]) / period
    loss = -np.sum(deltas[deltas < 0]) / period
    rs = gain / loss if loss != 0 else float('inf')  # ZeroDivisionError 방지
    rsi = 100 - (100 / (1 + rs))
    return rsi

def place_order(symbol, side, amount):
    """시장가로 주문을 생성"""
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
    order_amount = MIN_CONTRACT_AMOUNT * martingale_multiplier

    # 시세 데이터 가져오기
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=50)
        data = np.array(ohlcv)
        close = data[:, 4]

        if len(close) < 26:
            print("Not enough data to calculate MACD and RSI")
            time.sleep(SLEEP_INTERVAL)
            continue

        # MACD와 RSI 계산
        macd_line, signal_line = calculate_macd(close)
        rsi = calculate_rsi(close)
        print(f"MACD Line: {macd_line:.2f}, Signal Line: {signal_line:.2f}, RSI: {rsi:.2f}")

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

    # MACD와 RSI 조건에 따른 주문 로직
    if current_position is None:
        if macd_line > signal_line and rsi < 70:  # 매수 조건
            place_order(symbol, 'buy', order_amount)
        elif macd_line < signal_line and rsi > 30:  # 매도 조건
            place_order(symbol, 'sell', order_amount)
    else:
        # 포지션이 있을 때 PnL 확인 후 청산
        check_pnl_and_close(current_position)

    # 남은 시간 출력 및 대기
    for remaining_time in range(SLEEP_INTERVAL, 0, -1):
        print(f"Next iteration in: {remaining_time} seconds", end='\r')
        time.sleep(1)