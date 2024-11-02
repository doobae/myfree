import ccxt
import time
import numpy as np
import warnings
from datetime import datetime, timedelta

warnings.simplefilter(action='ignore', category=FutureWarning)

# OKX API 키 설정
# OKX API 키 설정
api_key = 'ef0e145c-9afd-4a02-a5fb-04b8a364a94f'        # 실제 API 키  okx_CW241021
secret_key = 'FAEC20B8FD85B7AFCC99E0E05DB3A123'         # 실제 Secret 키
passphrase = '*Kcw117138'   # 실제 Passphrase
print("Auto-LO1hcheck_CW241102.py Detected Bot started")
# 전역 변수 설정
MIN_CONTRACT_AMOUNT = 0.1
PNL_TAKE_PROFIT = 100.0  # 손익 이익 기준 (USDT)
PNL_STOP_LOSS = -10.0    # 손익 손실 기준 (USDT)
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
    print(f"Balance: {balance['total']['USDT']} USDT")

    # 현재 PnL 출력
    open_positions = [p for p in positions if p['contracts'] > 0]
    if open_positions:
        for pos in open_positions:
            pnl = pos['unrealizedPnl']
            print(f"Current PnL: {pnl} USDT")
    else:
        print("No open positions.")

# 주요 루프
while True:
    # 상태 출력
    print_status()

    # 손익 기준 검사
    open_positions = [p for p in exchange.fetch_positions([symbol]) if p['contracts'] > 0]
    
    if open_positions:  # 열린 포지션이 있는 경우
        for current_position in open_positions:
            pnl = current_position['unrealizedPnl']
            if pnl < PNL_STOP_LOSS or pnl > PNL_TAKE_PROFIT:
                print("거래 범위 초과")
                # 6시간 대기
                time.sleep(3600)  # 1시간 (21600초)
                break  # 포지션 리스트를 검사 후 대기하도록 break
    else:
        print("No open positions to check.")

    # 남은 시간 출력 및 대기
    for remaining_time in range(10, 0, -1):
        print(f"Next status check in: {remaining_time} seconds", end='\r')
        time.sleep(1)

    time.sleep(30)  # 10초 간격 대기