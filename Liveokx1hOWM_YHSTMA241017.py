#1 Liveokx1hdual_YHSTMA241010-> Succ후 one way mode 로 2024.10.17
import ccxt  # CCXT 라이브러리를 이용해 거래소 API를 제어
import pandas as pd  # 데이터를 다루기 위한 판다스 라이브러리
import numpy as np  # 수학적 연산을 위한 넘파이
import time  # 시간 제어를 위한 라이브러리
from datetime import datetime, timedelta  # 날짜와 시간을 다루기 위한 라이브러리
from prophet import Prophet  # 시계열 예측을 위한 Prophet 라이브러리 추가
import warnings  # 경고를 무시하기 위한 라이브러리
warnings.simplefilter(action='ignore', category=FutureWarning)

# 전역 변수 설정
api_key = '6e7e839f-207b-4a09-8993-03c0ceb73028'        # 실제 API 키
secret_key = 'A055683D48D5BC36A3AD9E3E8727281F'  # 실제 Secret 키
passphrase = 'K1b2k3b/'   # 실제 Passphrase
print("Auto-Liveokx1hOWM_YHSTMA241017 Detected Bot started")
# 거래할 계약 수량을 0.1로 설정
contract_amount = 0.1 
demo_mode = False  # 실거래 모드 설정 (False)
entry_price = None  # 진입가를 저장할 변수
sell_order_executed = False  # 매도 주문 실행 여부를 추적
buy_orders_active = True  # 매수 주문 활성화 여부
symbol = 'BTC-USDT-SWAP'  # OKX BTC 선물 상품 선택
exchange = None  # CCXT 거래소 객체 초기화
leverage = 50  # 레버리지를 50배로 설정
timeframe = '1h'  # 1시간 타임프레임 설정
position_mode = 'oneway'  # Position mode를 one-way mode로 설정

# OKX API 초기화 함수
def initialize_api():
    global exchange
    # CCXT를 이용해 OKX 거래소 객체 생성
    exchange = ccxt.okx({
        'apiKey': api_key,
        'secret': secret_key,
        'password': passphrase,
    })
    # 실거래 모드로 설정 (테스트 환경이 아님)
    exchange.set_sandbox_mode(False)  
    print("OKX 실거래 API가 초기화되었습니다.")

    # 시장 데이터를 불러와 레버리지 설정
    markets = exchange.load_markets()
    exchange.set_leverage(leverage, symbol)  # 레버리지 50배로 설정
    exchange.set_position_mode(False)  # Position mode를 One-way 모드로 설정 (False가 One-way 모드)
    print(f"{symbol}에 레버리지 {leverage}배 및 One-way 모드 설정 완료")

initialize_api()  # API 초기화

# 시장 데이터를 수집하는 함수 (변경사항 없음)
def get_market_data(symbol=symbol, timeframe=timeframe, limit=100):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)  # OHLCV 데이터 수집
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['close'] = df['close'].astype(float)
    return df

# 잔고 조회 함수 (USDT 잔고)
def get_balance():
    balance = exchange.fetch_balance()  # 거래소에서 잔고를 가져옴
    if 'USDT' in balance['total']:
        return balance['total']['USDT']  # USDT 잔고 반환
    else:
        print("잔고 없음")  # 잔고가 없을 때 메시지 출력
        return 0

# Prophet을 사용해 1시간 후 가격을 예측하는 함수 (변경사항 없음)
def predict_price(df):
    df_prophet = df[['timestamp', 'close']].rename(columns={'timestamp': 'ds', 'close': 'y'})
    model = Prophet()  # Prophet 모델 생성
    model.fit(df_prophet)
    future = model.make_future_dataframe(periods=1, freq='H')
    forecast = model.predict(future)
    predicted_price = forecast['yhat'].iloc[-1]  # 예측된 마지막 값을 추출
    current_price = df['close'].iloc[-1]
    return predicted_price, current_price

# 기술적 지표를 계산하는 함수 (변경사항 없음)
def calculate_indicators(df):
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    close = df['close'].astype(float)

    low_min = low.rolling(window=14).min()  # 14개 데이터 중 최저가
    high_max = high.rolling(window=14).max()  # 14개 데이터 중 최고가
    df['slowk'] = 100 * (close - low_min) / (high_max - low_min)  # 스토캐스틱 %K 계산
    df['slowd'] = df['slowk'].rolling(window=3).mean()  # 스토캐스틱 %D 계산

    short_ema = close.ewm(span=12, adjust=False).mean()
    long_ema = close.ewm(span=26, adjust=False).mean()
    df['macd'] = short_ema - long_ema
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()

    return df

# 시그널을 감지하는 함수 (변경사항 없음)
def check_signals(df):
    last_row = df.iloc[-1]

    if last_row['slowk'] > last_row['slowd']:
        return 'stochastic_cross_up'

    if last_row['macd'] < last_row['macd_signal']:
        return 'macd_cross_down'

    return None
#---------------------수정 posSide
# 거래 주문을 실행하는 함수
def place_order(side='buy', size=contract_amount):
    try:
        if side == 'buy':
            # 'posSide' 파라미터 제거
            exchange.create_order(symbol, 'market', 'buy', size)
        elif side == 'sell':
            # 'posSide' 파라미터 제거
            exchange.create_order(symbol, 'market', 'sell', size)
        print(f"{side.upper()} 주문 실행, 수량: {size}")
    except Exception as e:
        print(f"주문 실행 중 오류 발생: {e}")
#----
# 트레일링 스탑을 이용한 수익 및 손실 관리 함수 (변경사항 없음)
def manage_trailing_stop(entry_price, current_price, trailing_stop_percent=0.01):
    stop_loss_price = entry_price * (1 - trailing_stop_percent)
    if current_price <= stop_loss_price:
        return 'trailing_stop'
    return None

# 메인 트레이딩 루프 (변경사항 없음)
def trading_bot():
    global entry_price, sell_order_executed, buy_orders_active
    last_print_time = time.time()

    while True:
        df = get_market_data()
        df = calculate_indicators(df)

        signal = check_signals(df)

        if signal == 'stochastic_cross_up' and entry_price is None and buy_orders_active:
            predicted_price, current_price = predict_price(df)
            print(f"예측된 가격: {predicted_price}, 현재 가격: {current_price}")
            
            if predicted_price > current_price:
                place_order(side='buy')
                entry_price = df['close'].iloc[-1]
                print(f"매수 주문 체결, 진입가: {entry_price}")

        elif signal == 'macd_cross_down' and entry_price is not None and not sell_order_executed:
            predicted_price, current_price = predict_price(df)
            print(f"예측된 가격: {predicted_price}, 현재 가격: {current_price}")
            
            if predicted_price < current_price:
                place_order(side='sell')
                print(f"매도 주문 체결, 매도가: {df['close'].iloc[-1]}")
                entry_price = df['close'].iloc[-1]
                sell_order_executed = True

        elif sell_order_executed and entry_price is not None:
            current_price = df['close'].iloc[-1]
            action = manage_trailing_stop(entry_price, current_price)
            if action == 'trailing_stop':
                place_order(side='sell')
                print("트레일링 스탑! 익절 또는 손절")
                entry_price = None
                sell_order_executed = False
                buy_orders_active = True

        if time.time() - last_print_time >= 300:
            current_balance = get_balance()
            current_price = df['close'].iloc[-1]
            position_size = contract_amount if entry_price is not None else 0
            print(f"[상황 출력] 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, 잔고(USDT): {current_balance:.2f}, "
                  f"현재 가격(BTC-USDT): {current_price:.2f}, 진입 상태(계약 수량): {position_size}")

            last_print_time = time.time()

        time.sleep(300)

if __name__ == "__main__":
    trading_bot()