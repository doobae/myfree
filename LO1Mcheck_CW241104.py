import ccxt
import time
import warnings
from datetime import datetime, timedelta

warnings.simplefilter(action='ignore', category=FutureWarning)

# OKX API 키 설정
api_key = 'ef0e145c-9afd-4a02-a5fb-04b8a364a94f'        # 실제 API 키  okx_CW241021
secret_key = 'FAEC20B8FD85B7AFCC99E0E05DB3A123'         # 실제 Secret 키
passphrase = '*Kcw117138'   # 실제 Passphrase
print("Auto-LO1Mcheck_CW241104.py Detected Bot started")

# 전역 변수 설정
MIN_CONTRACT_AMOUNT = 0.1
PNL_TAKE_PROFIT = 100.0  # 손익 이익 기준 (USDT)
PNL_STOP_LOSS_PERCENTAGE = 0.02  # 손실 기준 (2%)
TRAILING_STOP_PERCENTAGE = 0.01  # 트레일링 스톱 기준 (1%)
LEVERAGE = 50
symbol = 'BTC-USDT-SWAP'
SLEEP_INTERVAL = 60

# PNL 제한 설정
PNL_MINIMUM_ADD_THRESHOLD = 2.0  # 추가 진입 PNL 임계값
PNL_CLEAR_THRESHOLD = 5.0  # 청산 PNL 범위 (-5 ~ +5)
DAILY_PNL_LIMIT = 50.0  # 일일 최대 PNL 제한
daily_loss_limit = -DAILY_PNL_LIMIT  # 일일 손실 한도 (-50)

# 하루 손실액 한도
total_daily_pnl = 0.0
next_day_reset = datetime.now().date() + timedelta(days=1)

# OKX 거래소 객체 생성
exchange = ccxt.okx({
    'apiKey': api_key,
    'secret': secret_key,
    'password': passphrase,
})
exchange.set_sandbox_mode(False)

def fetch_balance_and_positions():
    """잔고와 포지션 정보를 가져오는 함수"""
    balance = exchange.fetch_balance()
    positions = exchange.fetch_positions([symbol])
    return balance, positions

def print_status():
    """현재 시간, 잔고 및 PnL 상태를 출력하는 함수"""
    balance, positions = fetch_balance_and_positions()
    
    # 현재 시간 출력
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"Current Time (UTC+9): {current_time}")

    # 잔고 출력
    print(f"Balance: {balance['total']['USDT']:.3f} USDT")

    # 현재 PnL 출력 및 오픈 포지션 출력
    open_positions = [p for p in positions if p['contracts'] > 0]
    if open_positions:
        for pos in open_positions:
            pnl = pos['unrealizedPnl']
            print(f"Open Position: {pos['contracts']:.3f} contracts, PnL: {pnl:.3f} USDT")
    else:
        print("No open positions.")

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

def close_all_positions():
    """모든 포지션을 시장가로 청산"""
    positions = exchange.fetch_positions([symbol])
    open_positions = [p for p in positions if p['contracts'] > 0]
    for position in open_positions:
        side = 'sell' if position['side'] == 'long' else 'buy'
        amount = position['contracts']
        place_order(symbol, side, amount)
    print("All open positions have been closed.")

# 주요 루프
while True:
    # 상태 출력
    print_status()

    # 손익 기준 검사
    open_positions = [p for p in exchange.fetch_positions([symbol]) if p['contracts'] > 0]
    
    if open_positions:  # 열린 포지션이 있는 경우
        for current_position in open_positions:
            pnl = current_position['unrealizedPnl']
            contracts = current_position['contracts']
            side = current_position['side']  # 'long' 또는 'short' 
            current_price = exchange.fetch_ticker(symbol)['last']  # 현재 가격
            trailing_stop_price = current_price * (1 - TRAILING_STOP_PERCENTAGE)

            # 하루 손실 한도 초과 체크
            if total_daily_pnl < daily_loss_limit or total_daily_pnl > DAILY_PNL_LIMIT:
                print("하루 손실 한도 초과, 모든 포지션 청산 후 다음날까지 대기")
                close_all_positions()
                while datetime.now().date() < next_day_reset:
                    time.sleep(3600)  # 1시간마다 체크하며 대기
                total_daily_pnl = 0  # 다음 날 초기화
                next_day_reset = datetime.now().date() + timedelta(days=1)
                break

            # PNL 청산 범위 확인
            if -PNL_CLEAR_THRESHOLD < pnl < PNL_CLEAR_THRESHOLD:
                print("PNL 청산 범위 도달, 포지션 청산")
                close_all_positions()
                total_daily_pnl += pnl
                break

            # 추가 계약 조건 확인 (수익이 +3 USDT 이상)
            if pnl > PNL_MINIMUM_ADD_THRESHOLD:
                print("이익 발생, 추가 계약 체결")
                place_order(symbol, 'buy' if side == 'long' else 'sell', MIN_CONTRACT_AMOUNT)

    else:
        print("No open positions to check.")

    # 남은 시간 출력 및 대기
    for remaining_time in range(50, 0, -1):
        print(f"Next status check in: {remaining_time} seconds", end='\r')
        time.sleep(1)

    time.sleep(10)  # 30초 간격 대기