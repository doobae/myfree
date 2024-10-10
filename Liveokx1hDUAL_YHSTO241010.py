import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
from prophet import Prophet  # Prophet 모델 추가
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
#model = Prophet(stan_backend='pystan')

# 전역 변수 설정
api_key = '6e7e839f-207b-4a09-8993-03c0ceb73028'        # 실제 API 키
secret_key = 'A055683D48D5BC36A3AD9E3E8727281F'  # 실제 Secret 키
passphrase = 'K1b2k3b/'   # 실제 Passphrase
print("Auto-Liveokx1h_YHSTO241010 Detected Bot started")
contract_amount = 0.1  # 거래 계약 수량
demo_mode = False  # 실거래 모드 (False)
entry_price = None  # 진입가
sell_order_executed = False  # 매도 주문이 실행되었는지 여부
buy_orders_active = True  # 매수 주문이 활성화되어 있는지 여부
symbol = 'BTC-USDT-SWAP'  # 거래할 상품 (OKX BTC 선물)
exchange = None  # CCXT 거래소 객체 초기화
leverage = 100  # 레버리지 설정
timeframe = '1h'  # 타임프레임을 1시간으로 설정

# OKX API 설정 (실거래)
def initialize_api():
    global exchange
    exchange = ccxt.okx({
        'apiKey': api_key,
        'secret': secret_key,
        'password': passphrase,
    })
    exchange.set_sandbox_mode(False)  # 실거래 모드 설정
    print("OKX 실거래 API가 초기화되었습니다.")

    # 레버리지 설정 (시장가 주문 전 설정 필요)
    markets = exchange.load_markets()
    exchange.set_leverage(leverage, symbol)
    print(f"{symbol}에 레버리지 {leverage}배 설정 완료")

initialize_api()  # API 초기화

# 시장 데이터 수집 (실제 시장 데이터를 받아옵니다)
def get_market_data(symbol=symbol, timeframe=timeframe, limit=100):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')  # 타임스탬프를 날짜 형식으로 변환
    df['close'] = df['close'].astype(float)
    return df

# 잔고 조회 (USDT 잔고)
def get_balance():
    balance = exchange.fetch_balance()
    if 'USDT' in balance['total']:
        return balance['total']['USDT']  # USDT 잔고 반환
    else:
        print("잔고 없음")  # USDT 잔고가 없을 경우 출력
        return 0

# Prophet을 이용해 1시간 후 가격 예측
def predict_price(df):
    df_prophet = df[['timestamp', 'close']].rename(columns={'timestamp': 'ds', 'close': 'y'})  # Prophet 모델 입력 형식 맞추기

    model = Prophet()  # Prophet 모델 초기화
    model.fit(df_prophet)  # 모델 학습
    
    future = model.make_future_dataframe(periods=1, freq='H')  # 1시간 후 예측
    forecast = model.predict(future)
    
    predicted_price = forecast['yhat'].iloc[-1]  # 예측된 마지막 값 (1시간 후 가격)
    current_price = df['close'].iloc[-1]  # 현재 가격
    
    return predicted_price, current_price

# 기술적 지표 계산 (스토캐스틱 및 MACD)
def calculate_indicators(df):
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    close = df['close'].astype(float)

    # 스토캐스틱 계산
    low_min = low.rolling(window=14).min()
    high_max = high.rolling(window=14).max()
    df['slowk'] = 100 * (close - low_min) / (high_max - low_min)
    df['slowd'] = df['slowk'].rolling(window=3).mean()

    # MACD 계산
    short_ema = close.ewm(span=12, adjust=False).mean()
    long_ema = close.ewm(span=26, adjust=False).mean()
    df['macd'] = short_ema - long_ema
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    return df

# 시그널 감지
def check_signals(df):
    last_row = df.iloc[-1]

    # 스토캐스틱 크로스업 확인
    if last_row['slowk'] > last_row['slowd']:
        return 'stochastic_cross_up'

    # 스토캐스틱 크로스다운 확인
    if last_row['slowk'] < last_row['slowd']:
        return 'stochastic_cross_down'

    return None

# 거래 주문 실행 (시장가 주문)
def place_order(side='buy', size=contract_amount):
    try:
        if side == 'buy':
            # 롱 포지션 (매수)
            exchange.create_order(symbol, 'market', 'buy', size, params={"posSide": "long"})
        elif side == 'sell':
            # 숏 포지션 (매도)
            exchange.create_order(symbol, 'market', 'sell', size, params={"posSide": "short"})
        print(f"{side.upper()} 주문 실행, 수량: {size}")
    except Exception as e:
        print(f"주문 실행 중 오류 발생: {e}")

# 수익 및 손실 관리
def manage_profit_and_loss(entry_price, current_price):
    if current_price >= entry_price * 1.02:
        return 'take_profit'
    elif current_price <= entry_price * 0.99:
        return 'stop_loss'
    return None

# 메인 트레이딩 루프
def trading_bot():
    global entry_price, sell_order_executed, buy_orders_active
    last_print_time = time.time()

    while True:
        df = get_market_data()
        df = calculate_indicators(df)

        signal = check_signals(df)

        # 스토캐스틱 크로스업에서 매수 주문 (Prophet 예측 결과 상승 시)
        if signal == 'stochastic_cross_up' and entry_price is None and buy_orders_active:
            predicted_price, current_price = predict_price(df)
            print(f"예측된 가격: {predicted_price}, 현재 가격: {current_price}")
            
            if predicted_price > current_price:
                place_order(side='buy')
                entry_price = df['close'].iloc[-1]
                print(f"매수 주문 체결, 진입가: {entry_price}")

        # 스토캐스틱 크로스다운에서 매도 주문 (Prophet 예측 결과 하락 시)
        elif signal == 'stochastic_cross_down' and entry_price is not None and not sell_order_executed:
            predicted_price, current_price = predict_price(df)
            print(f"예측된 가격: {predicted_price}, 현재 가격: {current_price}")
            
            if predicted_price < current_price:
                place_order(side='sell')
                print(f"매도 주문 체결, 매도가: {df['close'].iloc[-1]}")
                entry_price = df['close'].iloc[-1]  # 매도가를 새로운 진입가로 설정
                sell_order_executed = True  # 매도 주문이 실행되었음을 표시

        # 수익 및 손실 관리
        elif sell_order_executed and entry_price is not None:
            current_price = df['close'].iloc[-1]
            action = manage_profit_and_loss(entry_price, current_price)
            if action == 'take_profit':
                place_order(side='sell')
                print("익절!")
                entry_price = None
                sell_order_executed = False
                buy_orders_active = True  # 다시 매수 주문 활성화
            elif action == 'stop_loss':
                place_order(side='sell')
                print("손절!")
                entry_price = None
                sell_order_executed = False
                buy_orders_active = True  # 다시 매수 주문 활성화

        # 5분마다 상황 출력
        if time.time() - last_print_time >= 300:  # 300초 = 5분
            current_balance = get_balance()
            current_price = df['close'].iloc[-1]
            position_size = contract_amount if entry_price is not None else 0  # 진입 상태 (계약 수량)
            print(f"[상황 출력] 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, 잔고(USDT): {current_balance:.2f}, "
                  f"현재 가격(BTC-USDT): {current_price:.2f}, 진입 상태(계약 수량): {position_size}")

            last_print_time = time.time()  # 마지막 출력 시간 갱신

        time.sleep(300)  # 1분마다 실행

# 트레이딩 봇 실행
if __name__ == "__main__":
    trading_bot()