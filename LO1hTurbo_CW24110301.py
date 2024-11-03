import ccxt
import time
import warnings
from datetime import datetime, timedelta

warnings.simplefilter(action='ignore', category=FutureWarning)

# OKX API 키 설정
api_key = 'ef0e145c-9afd-4a02-a5fb-04b8a364a94f'        # 실제 API 키  okx_CW241021
secret_key = 'FAEC20B8FD85B7AFCC99E0E05DB3A123'         # 실제 Secret 키
passphrase = '*Kcw117138'   # 실제 Passphrase
print("Auto-LO1hTurbo_CW241103.py Detected Bot started")

# 전역 변수 설정
MIN_CONTRACT_AMOUNT = 0.1
PNL_TAKE_PROFIT = 100.0  # 손익 이익 기준 (USDT)
PNL_STOP_LOSS_PERCENTAGE = 0.02  # 손실 기준 (2%)
TRAILING_STOP_PERCENTAGE = 0.01  # 트레일링 스톱 기준 (1%)
LEVERAGE = 50
symbol = 'BTC-USDT-SWAP'
SLEEP_INTERVAL = 300

# 하루 손실액 한도
daily_loss_limit = -200.0  # 하루 손실 한도 설정 (예: -200 USDT)
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

            # 손실 기준 체크
            stop_loss_threshold = -PNL_TAKE_PROFIT * PNL_STOP_LOSS_PERCENTAGE
            if pnl < stop_loss_threshold:
                print("손실 기준 초과, 모든 포지션 청산")
                close_all_positions()
                total_daily_pnl += pnl
                time.sleep(3600)  # 1시간 대기
                break

            # 하루 손실 한도 초과 체크
            if total_daily_pnl < daily_loss_limit:
                print("하루 손실 한도 초과, 모든 포지션 청산 후 다음날까지 대기")
                close_all_positions()
                while datetime.now().date() < next_day_reset:
                    time.sleep(3600)  # 1시간마다 체크하며 대기
                total_daily_pnl = 0  # 다음 날 초기화
                next_day_reset = datetime.now().date() + timedelta(days=1)
                break

            # PNL이 양수인 경우 추가 계약 체결
            if pnl > 0:
                print("이익 발생, 추가 계약 체결")
                place_order(symbol, 'buy' if side == 'long' else 'sell', MIN_CONTRACT_AMOUNT)

            # 트레일링 스톱 설정 및 주문 확인
            if (side == 'long' and current_price < trailing_stop_price) or (side == 'short' and current_price > trailing_stop_price):
                print(f"Triggering trailing stop for {side} position at price: {current_price:.3f}")
                place_order(symbol, 'sell' if side == 'long' else 'buy', contracts)  # 현재 계약 청산
                time.sleep(21600)  # 6시간 대기
                break

    else:
        print("No open positions to check.")

    # 남은 시간 출력 및 대기
    for remaining_time in range(10, 0, -1):
        print(f"Next status check in: {remaining_time} seconds", end='\r')
        time.sleep(1)

    time.sleep(30)  # 30초 간격 대기