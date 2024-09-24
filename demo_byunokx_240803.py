import ccxt
import time
import datetime

# OKX API 설정
api_key = "bd4b7464-a29d-4198-8250-feb0437932b1"
secret = "48439933EA13976CEA62147DC9228441"
password = "K1b2k3b/"

exchange = ccxt.okx({
    'apiKey': api_key,
    'secret': secret,
    'password': password,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
    },
})

# 테스트 환경 설정
exchange.set_sandbox_mode(True)

symbol = 'BTC/USDT'
leverage = 1
initial_investment = 1  # 초기 계약수
investment = initial_investment
martingale_count = 0
buy_price = None

def get_target_price(symbol, k):
    """변동성 돌파 전략으로 매수 목표가 조회"""
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=2)
    previous_candle = ohlcv[-2]
    target_price = previous_candle[4] + (previous_candle[2] - previous_candle[3]) * k
    return target_price

def get_balance():
    """잔고 조회"""
    balance = exchange.fetch_balance()
    return balance['total']['USDT']

def get_current_price(symbol):
    """현재가 조회"""
    ticker = exchange.fetch_ticker(symbol)
    return ticker['ask']

# 초기 설정
print("autotrade start")

# 자동매매 시작
while True:
    try:
        now = datetime.datetime.now()
        start_time = now.replace(minute=0, second=0, microsecond=0)
        end_time = start_time + datetime.timedelta(hours=1)

        if start_time < now < end_time - datetime.timedelta(seconds=10):
            target_price = get_target_price(symbol, 0.5)
            current_price = get_current_price(symbol)
            if target_price < current_price:
                usdt_balance = get_balance()
                if usdt_balance > investment * current_price:
                    order = exchange.create_market_buy_order(symbol, investment)
                    buy_price = current_price
                    print(f"{now} - 매수: {buy_price} USDT")
        else:
            positions = exchange.fetch_positions([symbol])
            for position in positions:
                if position['symbol'] == symbol and float(position['positionAmt']) > 0:
                    current_price = get_current_price(symbol)
                    if buy_price is not None:
                        if current_price >= buy_price * 1.05:  # 익절 조건
                            exchange.create_market_sell_order(symbol, investment)
                            print(f"{now} - 익절: {current_price} USDT")
                            buy_price = None
                            investment = initial_investment
                            martingale_count = 0
                        elif current_price <= buy_price * 0.95:  # 손절 조건
                            exchange.create_market_sell_order(symbol, investment)
                            print(f"{now} - 손절: {current_price} USDT")
                            buy_price = None
                            martingale_count += 1
                            if martingale_count <= 3:
                                investment *= 2
                            else:
                                investment = initial_investment
                                martingale_count = 0

        # 1시간마다 출력
        if now.minute == 0 and now.second == 0:
            usdt_balance = get_balance()
            current_btc_price = get_current_price(symbol)
            print(f"{now} - USDT 잔고: {usdt_balance}, BTC 현재가: {current_btc_price}")

        time.sleep(1)
    except Exception as e:
        print(e)
        time.sleep(1)