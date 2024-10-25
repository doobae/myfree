import ccxt  # CCXT 라이브러리를 이용해 거래소 API를 제어
import pandas as pd  # 데이터를 다루기 위한 판다스 라이브러리
import numpy as np  # 수학적 연산을 위한 넘파이
import time  # 시간 제어를 위한 라이브러리
from datetime import datetime, timedelta  # 날짜와 시간을 다루기 위한 라이브러리
from prophet import Prophet  # 시계열 예측을 위한 Prophet 라이브러리 추가
import warnings  # 경고를 무시하기 위한 라이브러리
warnings.simplefilter(action='ignore', category=FutureWarning)

# 전역 변수 설정
#api_key = '6e7e839f-207b-4a09-8993-03c0ceb73028'        # 실제 API 키
#secret_key = 'A055683D48D5BC36A3AD9E3E8727281F'  # 실제 Secret 키
#passphrase = 'K1b2k3b/'   # 실제 Passphrase
#print("Auto-Liveokx1hdual_YHSTMA241010 Detected Bot started")
api_key = 'ef0e145c-9afd-4a02-a5fb-04b8a364a94f'        # 실제 API 키  okx_CW241021
secret_key = 'FAEC20B8FD85B7AFCC99E0E05DB3A123'         # 실제 Secret 키
passphrase = '*Kcw117138'   # 실제 Passphrase
print("Auto-Liveokx1hdual_CWSTMA241010 Detected Bot started")
# 거래할 계약 수량을 0.2로 설정
contract_amount = 1
demo_mode = False  # 실거래 모드 설정 (False)
entry_price = None  # 진입가를 저장할 변수
sell_order_executed = False  # 매도 주문 실행 여부를 추적
buy_orders_active = True  # 매수 주문 활성화 여부
symbol = 'BTC-USDT-SWAP'  # OKX BTC 선물 상품 선택
exchange = None  # CCXT 거래소 객체 초기화
leverage = 100  # 레버리지를 100배로 설정
timeframe = '1h'  # 1시간 타임프레임 설정

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
    exchange.set_leverage(leverage, symbol)  # 레버리지 100배로 설정
    print(f"{symbol}에 레버리지 {leverage}배 설정 완료")

initialize_api()  # API 초기화

# 시장 데이터를 수집하는 함수
def get_market_data(symbol=symbol, timeframe=timeframe, limit=100):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)  # OHLCV 데이터 수집
    # 데이터프레임으로 변환하여 각 열에 적절한 이름을 지정
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')  # 타임스탬프를 날짜 형식으로 변환
    df['close'] = df['close'].astype(float)  # 종가 데이터를 실수형으로 변환
    return df

# 잔고 조회 함수 (USDT 잔고)
def get_balance():
    balance = exchange.fetch_balance()  # 거래소에서 잔고를 가져옴
    if 'USDT' in balance['total']:
        return balance['total']['USDT']  # USDT 잔고 반환
    else:
        print("잔고 없음")  # 잔고가 없을 때 메시지 출력
        return 0

# Prophet을 사용해 1시간 후 가격을 예측하는 함수
def predict_price(df):
    # Prophet에서 사용할 수 있도록 데이터프레임의 열 이름을 변경
    df_prophet = df[['timestamp', 'close']].rename(columns={'timestamp': 'ds', 'close': 'y'})  

    model = Prophet()  # Prophet 모델 생성
    model.fit(df_prophet)  # 모델 학습
    
    # 1시간 후의 데이터를 예측
    future = model.make_future_dataframe(periods=1, freq='H')  
    forecast = model.predict(future)
    
    predicted_price = forecast['yhat'].iloc[-1]  # 예측된 마지막 값을 추출 (1시간 후 가격)
    current_price = df['close'].iloc[-1]  # 현재 가격
    
    return predicted_price, current_price

# 기술적 지표를 계산하는 함수 (스토캐스틱 및 MACD)
def calculate_indicators(df):
    high = df['high'].astype(float)  # 고가 데이터를 실수형으로 변환
    low = df['low'].astype(float)  # 저가 데이터를 실수형으로 변환
    close = df['close'].astype(float)  # 종가 데이터를 실수형으로 변환

    # 스토캐스틱 계산
    low_min = low.rolling(window=14).min()  # 14개 데이터 중 최저가
    high_max = high.rolling(window=14).max()  # 14개 데이터 중 최고가
    df['slowk'] = 100 * (close - low_min) / (high_max - low_min)  # 스토캐스틱 %K 계산
    df['slowd'] = df['slowk'].rolling(window=3).mean()  # 스토캐스틱 %D 계산

    # MACD 계산
    short_ema = close.ewm(span=12, adjust=False).mean()  # 12주기 지수 이동 평균
    long_ema = close.ewm(span=26, adjust=False).mean()  # 26주기 지수 이동 평균
    df['macd'] = short_ema - long_ema  # MACD 계산 (단기 EMA - 장기 EMA)
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()  # 시그널 라인 계산
    
    return df

# 시그널을 감지하는 함수
def check_signals(df):
    last_row = df.iloc[-1]  # 데이터프레임의 마지막 행 선택

    # 스토캐스틱 크로스업 확인
    if last_row['slowk'] > last_row['slowd']:
        return 'stochastic_cross_up'

    # MACD 크로스다운 확인 (매도 조건 변경)
    if last_row['macd'] < last_row['macd_signal']:
        return 'macd_cross_down'

    return None

# 거래 주문을 실행하는 함수
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

# 트레일링 스탑을 이용한 수익 및 손실 관리 함수
def manage_trailing_stop(entry_price, current_price, trailing_stop_percent=0.01):
    stop_loss_price = entry_price * (1 - trailing_stop_percent)  # 트레일링 스탑 가격 계산 (진입가 - 1%)
    if current_price <= stop_loss_price:
        return 'trailing_stop'
    return None

# 메인 트레이딩 루프
def trading_bot():
    global entry_price, sell_order_executed, buy_orders_active
    last_print_time = time.time()  # 마지막 출력 시간 기록

    while True:
        df = get_market_data()  # 시장 데이터 가져오기
        df = calculate_indicators(df)  # 기술적 지표 계산

        signal = check_signals(df)  # 시그널 감지

        # 스토캐스틱 크로스업에서 매수 주문 (Prophet 예측 결과 상승 시)
        if signal == 'stochastic_cross_up' and entry_price is None and buy_orders_active:
            predicted_price, current_price = predict_price(df)  # 예측된 가격과 현재 가격 가져오기
            print(f"예측된 가격: {predicted_price}, 현재 가격: {current_price}")
            
            if predicted_price > current_price:  # 예측된 가격이 현재 가격보다 높으면 매수
                place_order(side='buy')  # 매수 주문 실행
                entry_price = df['close'].iloc[-1]  # 진입가 저장
                print(f"매수 주문 체결, 진입가: {entry_price}")

        # MACD 크로스다운에서 매도 주문
        elif signal == 'macd_cross_down' and entry_price is not None and not sell_order_executed:
            predicted_price, current_price = predict_price(df)
            print(f"예측된 가격: {predicted_price}, 현재 가격: {current_price}")
            
            if predicted_price < current_price:  # 예측된 가격이 현재 가격보다 낮으면 매도
                place_order(side='sell')  # 매도 주문 실행
                print(f"매도 주문 체결, 매도가: {df['close'].iloc[-1]}")
                entry_price = df['close'].iloc[-1]  # 새로운 진입가로 업데이트
                sell_order_executed = True  # 매도 주문 실행 여부 설정

        # 트레일링 스탑을 이용한 수익 및 손실 관리
        elif sell_order_executed and entry_price is not None:
            current_price = df['close'].iloc[-1]  # 현재 가격 가져오기
            action = manage_trailing_stop(entry_price, current_price)  # 트레일링 스탑 적용
            if action == 'trailing_stop':
                place_order(side='sell')  # 트레일링 스탑 도달 시 매도
                print("트레일링 스탑! 익절 또는 손절")
                entry_price = None
                sell_order_executed = False
                buy_orders_active = True  # 다시 매수 주문 활성화

        # 5분마다 상황 출력
        if time.time() - last_print_time >= 300:  # 300초 = 5분
            current_balance = get_balance()  # 잔고 조회
            current_price = df['close'].iloc[-1]  # 현재 가격 조회
            position_size = contract_amount if entry_price is not None else 0  # 진입 상태 (계약 수량)
            print(f"[상황 출력] 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, 잔고(USDT): {current_balance:.2f}, "
                  f"현재 가격(BTC-USDT): {current_price:.2f}, 진입 상태(계약 수량): {position_size}")

            last_print_time = time.time()  # 마지막 출력 시간 갱신

        time.sleep(300)  # 5분마다 실행

# 트레이딩 봇 실행
if __name__ == "__main__":
    trading_bot()