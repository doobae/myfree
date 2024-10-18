import ccxt
import time
import datetime

# OKX API 설정
api_key = "6e7e839f-207b-4a09-8993-03c0ceb73028"
secret = "A055683D48D5BC36A3AD9E3E8727281F"
password = "K1b2k3b/"
# 프로그램 시작 메시지 출력
print("autotrade Liveokx_Byun241018 start")
exchange = ccxt.okx({
    'apiKey': api_key,
    'secret': secret,
    'password': password,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',  # 선물 거래 설정
    },
})

# 테스트 환경 설정 (실제 거래는 False)
exchange.set_sandbox_mode(False)

symbol = 'BTC-USDT-SWAP'  # OKX 선물 거래 심볼 (BTC/USDT 무기한 스왑)
leverage = 100  # 레버리지 설정
initial_investment = 0.1  # 초기 계약수 (0.1 계약)
investment = initial_investment
martingale_count = 0
sell_price = None

# 레버리지 설정 함수
def set_leverage(symbol, leverage):
    exchange.futures_set_leverage(symbol, leverage)

def get_target_price(symbol, k):
    """변동성 돌파 전략으로 매도 목표가 조회"""
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=2)  # 15분 간격의 OHLCV 데이터 가져오기
    previous_candle = ohlcv[-2]
    target_price = previous_candle[4] - (previous_candle[2] - previous_candle[3]) * k  # 하락 목표가 계산
    return target_price

def get_balance():
    """잔고 조회"""
    balance = exchange.fetch_balance()
    return balance['total']['USDT']  # 총 USDT 잔고 반환

def get_current_price(symbol):
    """현재가 조회"""
    ticker = exchange.fetch_ticker(symbol)
    return ticker['bid']  # 매도 호가(현재가)를 반환

# 자동 매매 시작
while True:
    try:
        now = datetime.datetime.now()
        start_time = now.replace(minute=0, second=0, microsecond=0)
        end_time = start_time + datetime.timedelta(minutes=15)  # 15분 간격으로 실행

        if start_time < now < end_time - datetime.timedelta(seconds=10):
            target_price = get_target_price(symbol, 0.5)  # 매도 목표가 설정
            current_price = get_current_price(symbol)
            if current_price < target_price:  # 현재가가 목표가 이하일 때 매도
                usdt_balance = get_balance()
                if usdt_balance > investment * current_price * 0.01:  # 잔고가 최소 계약수 이상일 때
                    order = exchange.create_market_sell_order(symbol, investment)  # 시장가 매도 (Short)
                    sell_price = current_price
                    print(f"{now} - 매도(Short): {sell_price} USDT")
        
        # 현재 포지션을 확인하여 익절 또는 손절 처리
        positions = exchange.fetch_positions([symbol])
        for position in positions:
            if position['symbol'] == symbol and float(position['positionAmt']) < 0:  # 포지션이 Short일 때
                current_price = get_current_price(symbol)
                if sell_price is not None:
                    if current_price <= sell_price * 0.95:  # 5% 하락 시 익절
                        exchange.create_market_buy_order(symbol, investment)  # 시장가로 포지션 정리
                        print(f"{now} - 익절: {current_price} USDT")
                        sell_price = None
                        investment = initial_investment
                        martingale_count = 0
                    elif current_price >= sell_price * 1.05:  # 5% 상승 시 손절
                        exchange.create_market_buy_order(symbol, investment)  # 시장가로 포지션 정리
                        print(f"{now} - 손절: {current_price} USDT")
                        sell_price = None
                        martingale_count += 1
                        if martingale_count <= 3:  # 마틴게일 전략 적용
                            investment *= 2
                        else:
                            investment = initial_investment
                            martingale_count = 0

        # 15분마다 잔고, 현재가, 주문 계약수 출력
        if now.minute % 15 == 0 and now.second == 0:
            usdt_balance = get_balance()
            current_btc_price = get_current_price(symbol)
            print(f"{now} - USDT 잔고: {usdt_balance}, BTC 현재가: {current_btc_price}, 계약수: {investment}")

        time.sleep(1)
    except Exception as e:
        print(e)
        time.sleep(1)