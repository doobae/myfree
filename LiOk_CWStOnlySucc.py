#LiOk_CWStOnlySucc.py   Ver.1031
import ccxt
import time
import numpy as np
import warnings  # 경고를 무시하기 위한 라이브러리
warnings.simplefilter(action='ignore', category=FutureWarning)
# OKX API 키 설정
api_key = 'ef0e145c-9afd-4a02-a5fb-04b8a364a94f'        # 실제 API 키  okx_CW241021
secret_key = 'FAEC20B8FD85B7AFCC99E0E05DB3A123'         # 실제 Secret 키
passphrase = '*Kcw117138'   # 실제 Passphrase

print("Auto-LiOk_CWStOnlySucc.py bot started")
#---------
# 전역 변수 설정
PNL_LOWER_BOUND = 0
PNL_UPPER_BOUND = 0
MIN_CONTRACT_AMOUNT = 0.01
LEVERAGE = 100  # 레버리지 설정
symbol = 'BTC-USDT-SWAP'
# PNL_LOWER_BOUND = usdt_balance * -0.3  # 잔고의 -30%  150usdt 기준 70usdt
# PNL_UPPER_BOUND = usdt_balance * 0.01  # 잔고의 1%    150usdt 기준 2.36usdt
# place_order(symbol, 'buy', usdt_balance * 0.0015) # 크로스업 메수계약비율
# 상승 방향일 때만 주문 place_order(symbol, 'buy', usdt_balance * 0.0015)
# 크로스다운 place_order(symbol, 'sell', usdt_balance * 0.0015)
# OKX 거래소 객체 생성
try:
    exchange = ccxt.okx({
        'apiKey': api_key,
        'secret': secret_key,
        'password': passphrase,
    })
    exchange.set_sandbox_mode(False)  # 실거래 모드 설정
except Exception as e:
    print(f"Error creating exchange instance: {e}")
    exit()

# 스토캐스틱 크로스 상태 체크 함수
def calculate_stochastic(high, low, close, period=14):
    lowest_low = np.min(low[-period:])
    highest_high = np.max(high[-period:])
    
    if highest_high - lowest_low == 0:
        k = 0
    else:
        k = 100 * (close[-1] - lowest_low) / (highest_high - lowest_low)
    
    d = np.mean([100 * (close[i] - np.min(low[-period:])) / (np.max(high[-period:]) - np.min(low[-period:])) for i in range(-3, 0)])  # D값 계산 (이동평균)
    
    return k, d

# 잔고 확인 함수 및 PnL 하한값과 상한값 동적 설정
def check_balance():
    global PNL_LOWER_BOUND, PNL_UPPER_BOUND
    try:
        balance = exchange.fetch_balance()
        usdt_balance = balance['total'].get('USDT', 0)
        PNL_LOWER_BOUND = usdt_balance * -0.3  # 잔고의 1%
        PNL_UPPER_BOUND = usdt_balance * 0.01  # 잔고의 5%
        print(f"Current Balance (USDT): {usdt_balance}")
        print(f"PNL Lower Bound: {PNL_LOWER_BOUND}, PNL Upper Bound: {PNL_UPPER_BOUND}")
        return usdt_balance
    except Exception as e:
        print(f"Error fetching balance: {e}")
        return 0

# 주문 함수
def place_order(symbol, side, amount):
    try:
        # 잔고가 부족할 경우 최소 계약량으로 주문
        if amount < MIN_CONTRACT_AMOUNT:
            amount = MIN_CONTRACT_AMOUNT

        params = {'leverage': LEVERAGE, 'posSide': 'long' if side == 'buy' else 'short'}  # 헷지 모드 설정
        order = exchange.create_market_order(symbol, side, amount, params=params)
        print(f"Order placed - Symbol: {symbol}, Side: {side}, Amount: {amount}, Order ID: {order['id']}")
    except Exception as e:
        print(f"Error placing order: {e}")

# 오픈 포지션 내역 확인 및 청산 조건
def fetch_open_positions():
    try:
        positions = exchange.fetch_positions([symbol])
        total_pnl = sum(position['unrealizedPnl'] for position in positions if position['contracts'] > 0)  # 오픈 포지션 PnL 합산
        print(f"Total Open Position PNL: {total_pnl}")
        
        for position in positions:
            if position['contracts'] > 0:  # 포지션이 열려 있는 경우
                pnl = position['unrealizedPnl']
                print(f"Current Position PNL: {pnl}")
                if pnl < PNL_LOWER_BOUND or pnl > PNL_UPPER_BOUND:
                    close_position(position)
    except Exception as e:
        print(f"Error fetching open positions: {e}")

# 포지션 청산 함수
def close_position(position):
    try:
        side = 'sell' if position['side'] == 'long' else 'buy'
        amount = position['contracts']
        params = {'posSide': position['side']}  # 헷지 모드 설정
        order = exchange.create_market_order(symbol, side, amount, params=params)
        print(f"Closed Position - Symbol: {symbol}, Side: {side}, Amount: {amount}, Order ID: {order['id']}")
    except Exception as e:
        print(f"Error closing position: {e}")

# 주요 루프
while True:
    usdt_balance = check_balance()
    if usdt_balance < MIN_CONTRACT_AMOUNT:
        print("Insufficient balance for trading.")
        time.sleep(60)
        continue

    # 시세 데이터 가져오기
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=50)
        data = np.array(ohlcv)  # OHLCV 데이터를 NumPy 배열로 변환
        
        if len(data) < 14:  # 최소 14개의 데이터 필요
            print("Not enough data to calculate stochastic.")
            time.sleep(60)
            continue
        
        high = data[:, 2]  # 고가
        low = data[:, 3]   # 저가
        close = data[:, 4] # 종가

        # 스토캐스틱 계산
        k, d = calculate_stochastic(high, low, close, period=14)

    except Exception as e:
        print(f"Error fetching OHLCV data: {e}")
        time.sleep(60)
        continue

    # 오픈 포지션 확인
    positions = exchange.fetch_positions([symbol])
    current_position = None
    for position in positions:
        if position['contracts'] > 0:  # 열린 포지션 확인
            current_position = position
            break

    # 스토캐스틱 크로스 상태 확인
    if current_position is None:  # 현재 포지션이 없을 때
        if k > d:  # 크로스업
            place_order(symbol, 'buy', usdt_balance * 0.0015)
    elif current_position:  # 현재 포지션이 있을 때
        if current_position['side'] == 'long':
            # 상승 방향일 때만 주문
            if k > d:  
                place_order(symbol, 'buy', usdt_balance * 0.0015)
        elif current_position['side'] == 'short':
            # 감소 방향일 때는 더 이상 주문하지 않음
            if k < d:  # 크로스다운
                place_order(symbol, 'sell', usdt_balance * 0.0015)

    # 오픈 포지션 내역 확인 및 필요 시 청산
    fetch_open_positions()

    # 1분 대기 후 반복
    time.sleep(60)