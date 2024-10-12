import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
from prophet import Prophet
from statsmodels.tsa.arima.model import ARIMA  # ARIMA 모델 추가
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

# 전역 변수 설정
api_key = '6e7e839f-207b-4a09-8993-03c0ceb73028'        # 실제 API 키
secret_key = 'A055683D48D5BC36A3AD9E3E8727281F'  # 실제 Secret 키
passphrase = 'K1b2k3b/'   # 실제 Passphrase
contract_amount = 0.1
demo_mode = False
entry_price = None
sell_order_executed = False
buy_orders_active = True
symbol = 'BTC-USDT-SWAP'
leverage = 100
timeframe = '1h'
atr_period = 14  # ATR 계산에 사용할 기간
# OKX API 초기화
def initialize_api():
    global exchange
    exchange = ccxt.okx({
        'apiKey': api_key,
        'secret': secret_key,
        'password': passphrase,
    })
    exchange.set_sandbox_mode(False)  # 실거래 모드 설정
    markets = exchange.load_markets()
    exchange.set_leverage(leverage, symbol)

initialize_api()

# 시장 데이터 수집
def get_market_data(symbol=symbol, timeframe=timeframe, limit=100):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['close'] = df['close'].astype(float)
    return df

# Prophet 예측
def predict_price_prophet(df):
    df_prophet = df[['timestamp', 'close']].rename(columns={'timestamp': 'ds', 'close': 'y'})
    model = Prophet()
    model.fit(df_prophet)
    future = model.make_future_dataframe(periods=1, freq='H')
    forecast = model.predict(future)
    predicted_price = forecast['yhat'].iloc[-1]  # 예측된 값 중 yhat 사용
    current_price = df['close'].iloc[-1]  # 현재 가격은 데이터의 마지막 값 사용
    return predicted_price, current_price

# ARIMA 예측
def predict_price_arima(df):
    try:
        # ARIMA 모델의 차수를 조정 (p=5, d=1, q=0은 일단 유지)
        model = ARIMA(df['close'], order=(5, 1, 0))
        model_fit = model.fit()
        forecast = model_fit.forecast(steps=1)

        # 예측 값이 비어 있거나 0인 경우 처리
        if len(forecast) > 0 and forecast[0] != 0:
            predicted_price = forecast[0]  # 예측값 가져오기
        else:
            predicted_price = None  # 0이거나 비어 있으면 None 처리
            print("ARIMA 모델 예측값이 0이거나 비어 있습니다. Prophet 모델만 사용합니다.")
        
        current_price = df['close'].iloc[-1]  # 현재 가격은 데이터의 마지막 값 사용
        
    except Exception as e:
        print(f"ARIMA 예측 중 오류 발생: {e}")
        predicted_price = None
        current_price = None
    
    return predicted_price, current_price

# ATR 계산 (평균 진폭 범위)
def calculate_atr(df, period=atr_period):
    df['tr'] = np.maximum((df['high'] - df['low']),
                          np.abs(df['high'] - df['close'].shift(1)),
                          np.abs(df['low'] - df['close'].shift(1)))
    df['atr'] = df['tr'].rolling(window=period).mean()  # ATR 값 계산
    return df

# 기술적 지표 계산 (스토캐스틱 및 MACD)
def calculate_indicators(df):
    high = df['high']
    low = df['low']
    close = df['close']

    # 스토캐스틱 계산
    low_min = low.rolling(window=14).min()  # 14일 기간 중 최저점
    high_max = high.rolling(window=14).max()  # 14일 기간 중 최고점
    df['slowk'] = 100 * (close - low_min) / (high_max - low_min)  # 스토캐스틱 %K
    df['slowd'] = df['slowk'].rolling(window=3).mean()  # 스토캐스틱 %D

    # MACD 계산
    short_ema = close.ewm(span=12, adjust=False).mean()  # 12일 EMA
    long_ema = close.ewm(span=26, adjust=False).mean()  # 26일 EMA
    df['macd'] = short_ema - long_ema  # MACD 값
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()  # MACD 신호선

    # ATR 계산 추가
    df = calculate_atr(df)

    return df

# 시그널 감지
def check_signals(df):
    last_row = df.iloc[-1]  # 마지막 데이터를 사용
    if last_row['slowk'] > last_row['slowd']:  # 스토캐스틱 상향 교차 확인
        return 'stochastic_cross_up'
    elif last_row['slowk'] < last_row['slowd']:  # 스토캐스틱 하향 교차 확인
        return 'stochastic_cross_down'
    return None

# 동적 손익 관리 (ATR 기반)
def manage_profit_and_loss(entry_price, current_price, atr_value):
    take_profit_level = entry_price + 2 * atr_value  # ATR의 2배로 익절 설정
    stop_loss_level = entry_price - 1 * atr_value  # ATR의 1배로 손절 설정

    if current_price >= take_profit_level:
        return 'take_profit'  # 익절 시그널
    elif current_price <= stop_loss_level:
        return 'stop_loss'  # 손절 시그널
    return None

# 거래 주문 실행
def place_order(side='buy', size=contract_amount):
    try:
        if side == 'buy':
            exchange.create_order(symbol, 'market', 'buy', size, params={"posSide": "long"})  # 매수 주문 실행
        elif side == 'sell':
            exchange.create_order(symbol, 'market', 'sell', size, params={"posSide": "short"})  # 매도 주문 실행
        print(f"{side.upper()} 주문 실행, 수량: {size}")
    except Exception as e:
        print(f"주문 실행 중 오류 발생: {e}")

# 메인 트레이딩 루프-----------------------------
def trading_bot():
    global entry_price, sell_order_executed, buy_orders_active
    last_print_time = time.time()

    while True:
        df = get_market_data()  # 시장 데이터 수집
        df = calculate_indicators(df)  # 기술적 지표 계산

        signal = check_signals(df)  # 시그널 감지

        # Prophet 예측
        predicted_price_prophet, current_price = predict_price_prophet(df)
        
        # ARIMA 예측
        predicted_price_arima, _ = predict_price_arima(df)

        # 예측 가격 계산 (둘 중 하나가 None일 때 Prophet만 사용)
        if predicted_price_prophet is None and predicted_price_arima is None:
            print("예측된 가격이 둘 다 없음, 스킵합니다.")
            continue
        elif predicted_price_prophet is None:
            predicted_price = predicted_price_arima
            print(f"ARIMA 예측만 사용: {predicted_price}")
        elif predicted_price_arima is None:
            predicted_price = predicted_price_prophet
            print(f"Prophet 예측만 사용: {predicted_price}")
        else:
            predicted_price = (predicted_price_prophet + predicted_price_arima) / 2
            print(f"예측 평균값 사용: {predicted_price}")

        # 이후 거래 로직 계속...
#---------------------------------
        # 매수 시그널 시 매수 주문
        if signal == 'stochastic_cross_up' and entry_price is None and buy_orders_active:
            print(f"Prophet 예측: {predicted_price_prophet}, ARIMA 예측: {predicted_price_arima}")
            if predicted_price > current_price:
                place_order('buy')
                entry_price = current_price
                print(f"매수 주문 체결, 진입가: {entry_price}")

        # 매도 시그널 시 매도 주문
        elif signal == 'stochastic_cross_down' and entry_price is not None and not sell_order_executed:
            print(f"Prophet 예측: {predicted_price_prophet}, ARIMA 예측: {predicted_price_arima}")
            if predicted_price < current_price:
                place_order('sell')
                sell_order_executed = True
                print(f"매도 주문 체결, 매도가: {df['close'].iloc[-1]}")

        # ATR을 사용한 동적 수익 및 손실 관리
        if sell_order_executed and entry_price is not None:
            atr_value = df['atr'].iloc[-1]
            action = manage_profit_and_loss(entry_price, current_price, atr_value)
            if action == 'take_profit':
                place_order('sell')
                entry_price = None
                sell_order_executed = False
                print("익절!")
            elif action == 'stop_loss':
                place_order('sell')
                entry_price = None
                sell_order_executed = False
                print("손절!")

        time.sleep(300)  # 5분마다 실행

# 트레이딩 봇 실행
if __name__ == "__main__":
    trading_bot()