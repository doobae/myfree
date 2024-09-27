import time
import pyupbit
import pandas as pd
import pandas_ta as ta  # MACD 계산을 위한 pandas_ta 사용
from prophet import Prophet
import warnings

# 첫 번째 계정의 Upbit API 키와 시크릿 키 설정
access1 = 'ix5Xex6TKVLDJXjbGP3hQUch8JbNxWz0q1zmQkA2'  # 첫 번째 계정의 API 키
secret1 = 'PkxbzEu7VIcm3KxyAH56wb2A49dzNIxPg6bLjPNh'  # 첫 번째 계정의 시크릿 키

# 두 번째 계정의 Upbit API 키와 시크릿 키 설정
access2 = 'E8jhhwOAz6xO4sIgBf13L53g06N14OW1gxls9Afv'  # 두 번째 계정의 API 키
secret2 = 'GBZsaNorvShO1uQ9iJiBQ6qQpP8rsOVefbBrRxxZ'  # 두 번째 계정의 시크릿 키

#API_KEY = 'ix5Xex6TKVLDJXjbGP3hQUch8JbNxWz0q1zmQkA2'
#SECRET_KEY = 'PkxbzEu7VIcm3KxyAH56wb2A49dzNIxPg6bLjPNh'
#access = 'E8jhhwOAz6xO4sIgBf13L53g06N14OW1gxls9Afv'
#secret = 'GBZsaNorvShO1uQ9iJiBQ6qQpP8rsOVefbBrRxxZ'
print("Auto-Price Detected Bot started")

# 첫 번째 Upbit 로그인
upbit1 = pyupbit.Upbit(access1, secret1)

# 두 번째 Upbit 로그인
upbit2 = pyupbit.Upbit(access2, secret2)

# 경고 메시지 무시
warnings.filterwarnings("ignore")

# 거래 간격 설정
interval = "minute60"  # 1시간봉 기준으로 변경

# 거래량 증가폭이 가장 큰 종목을 저장할 변수
buy_info1 = {}  # 첫 번째 계정용
buy_info2 = {}  # 두 번째 계정용

# 전체 종목에 대해 예측 수행
def get_all_pairs():
    return pyupbit.get_tickers(fiat="KRW")

# 비트코인(BTC-KRW)의 MACD(15,30) 및 시그널(10) 계산 함수
def calculate_btc_macd():
    try:
        btc_candles = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=50)
        if btc_candles is not None and len(btc_candles) >= 50:
            macd = ta.macd(btc_candles['close'], fast=15, slow=30, signal=10)
            macd_value = macd['MACD_15_30_10'].iloc[-1]
            signal_value = macd['MACDs_15_30_10'].iloc[-1]
            previous_macd = macd['MACD_15_30_10'].iloc[-2]
            previous_signal = macd['MACDs_15_30_10'].iloc[-2]
            return macd_value, signal_value, previous_macd, previous_signal  # MACD, 시그널 및 이전 값 반환
        else:
            print("BTC-KRW 캔들 데이터를 가져오지 못했습니다.")
            return None, None, None, None
    except Exception as e:
        print(f"비트코인 MACD 계산 에러 발생: {e}")
        return None, None, None, None

# MACD 하방 돌파(CrossDown) 확인 함수
def check_macd_crossdown(macd_value, signal_value, previous_macd, previous_signal):
    return previous_macd > previous_signal and macd_value < signal_value

# Prophet 모델 학습 함수
def train_prophet_model(pair):
    try:
        candles = pyupbit.get_ohlcv(pair, interval="minute60", count=50)
        if candles is not None and len(candles) >= 50:
            candles = candles.reset_index().rename(columns={'index': 'ds', 'close': 'y'})
            model = Prophet(daily_seasonality=False, yearly_seasonality=False, weekly_seasonality=False)
            model.fit(candles[['ds', 'y']])
            future = model.make_future_dataframe(periods=2, freq='H')
            forecast = model.predict(future)
            return forecast['yhat'].iloc[-1], candles
    except Exception as e:
        print(f"Prophet 모델 예측 실패: {e}")
    return None, None

# 예측 및 검증 수행
def predict_and_validate(all_pairs):
    results = {}
    
    for pair in all_pairs:
        prophet_forecast, prophet_candles = train_prophet_model(pair)
        
        if prophet_forecast and prophet_candles is not None:
            current_price = prophet_candles['y'].iloc[-1]

            if prophet_forecast > current_price:
                forecast_increase = prophet_forecast - current_price
                results[pair] = forecast_increase
    
    return results

# 매수 및 매도 전략
def execute_trades(upbit, buy_info, predictions):
    if not predictions:
        print("상승 예측된 종목이 없습니다.")
        return

    best_pair = max(predictions, key=predictions.get)
    print(f"상승률이 가장 높은 종목: {best_pair}")

    if best_pair and best_pair not in buy_info:
        buy_info[best_pair] = {'amount': 6000}
        upbit.buy_market_order(best_pair, buy_info[best_pair]['amount'])
        print(f"{best_pair}: 매수 주문 실행, 금액: {buy_info[best_pair]['amount']}")

    balance = upbit.get_balance()
    btc_price = pyupbit.get_current_price("KRW-BTC")
    print(f"현재 잔고: {balance} KRW, 비트코인 가격: {btc_price} KRW")

    for pair in list(buy_info.keys()):
        avg_buy_price = upbit.get_avg_buy_price(pair)
        current_price = pyupbit.get_current_price(pair)
        balance = upbit.get_balance(ticker=pair)

        if current_price >= avg_buy_price * 1.02 and balance > 0:
            upbit.sell_market_order(pair, balance)
            print(f"{pair}: 2% 익절 주문 실행 - 매도")
            del buy_info[pair]

        elif current_price <= avg_buy_price * 0.98 and balance > 0:
            if buy_info[pair]['amount'] <= 24000:
                new_amount = buy_info[pair]['amount'] * 2
                buy_info[pair]['amount'] = new_amount
                upbit.buy_market_order(pair, new_amount)
                print(f"{pair}: 마틴 전략으로 추가 매수, 금액: {new_amount}")
            else:
                upbit.sell_market_order(pair, balance)
                print(f"{pair}: 마틴 전략 최대 횟수 초과 - 청산")
                del buy_info[pair]

# 보유 종목 매도 함수
def sell_all_holdings(upbit):
    try:
        balances = upbit.get_balances()
        for balance in balances:
            currency = balance['currency']
            if currency == "KRW":
                continue

            ticker = f"KRW-{currency}"
            balance_amount = float(balance['balance'])
            if balance_amount > 0:
                avg_buy_price = float(balance['avg_buy_price'])
                current_value = balance_amount * pyupbit.get_current_price(ticker)

                if current_value >= 5050:
                    upbit.sell_market_order(ticker, balance_amount)
                    print(f"{ticker}: 시장가로 전량 매도, 잔고: {current_value} KRW")
    except Exception as e:
        print(f"잔고 매도 중 에러 발생: {e}")

# 메인 로직
while True:
    start_time = time.time()

    try:
        # 비트코인의 MACD 값을 먼저 확인
        macd_value, signal_value, previous_macd, previous_signal = calculate_btc_macd()

        if macd_value is not None and signal_value is not None:
            if check_macd_crossdown(macd_value, signal_value, previous_macd, previous_signal):
                print(f"MACD 하방 돌파 감지. 보유 종목을 전량 청산합니다.")
                sell_all_holdings(upbit1)
                sell_all_holdings(upbit2)
            else:
                if macd_value <= 0 and macd_value > signal_value:
                    print(f"비트코인 MACD 값이 {macd_value}, 시그널 값이 {signal_value}로 조건을 만족합니다. 거래 예측을 시작합니다.")

                    all_pairs = get_all_pairs()
                    if not all_pairs:
                        print("전체 종목을 가져올 수 없습니다.")
                    else:
                        predictions1 = predict_and_validate(all_pairs)
                        execute_trades(upbit1, buy_info1, predictions1)

                        predictions2 = predict_and_validate(all_pairs)
                        execute_trades(upbit2, buy_info2, predictions2)
                else:
                    print(f"MACD 조건 불충족: MACD 값 {macd_value}, 시그널 값 {signal_value}. 다음 실행을 대기합니다.")
        else:
            print("비트코인 MACD 값을 가져올 수 없습니다.")

    except Exception as e:
        print(f"에러 발생: {str(e)}")
        time.sleep(10)
        continue

    elapsed_time = time.time() - start_time
    remaining_time = max(60 - elapsed_time, 0)
    
    print(f"다음 실행까지 남은 시간: {remaining_time:.2f} 초")
    time.sleep(remaining_time)