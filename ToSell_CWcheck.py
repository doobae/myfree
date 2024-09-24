import ccxt
import datetime
# 원화 잔고와 보유잔고(KRW)를 출력합니다.
# Upbit API 키와 비밀 키를 설정합니다.
API_KEY = 'E8jhhwOAz6xO4sIgBf13L53g06N14OW1gxls9Afv'
SECRET_KEY = 'GBZsaNorvShO1uQ9iJiBQ6qQpP8rsOVefbBrRxxZ'
#API_KEY = 'ix5Xex6TKVLDJXjbGP3hQUch8JbNxWz0q1zmQkA2'
#SECRET_KEY = 'PkxbzEu7VIcm3KxyAH56wb2A49dzNIxPg6bLjPNh'
# Upbit API 클라이언트 초기화
upbit = ccxt.upbit({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
})

def get_balance():
    try:
        # 잔고를 가져옵니다.
        balance = upbit.fetch_balance()
        krw_balance = balance['total']['KRW']
        coin_balance = {k: v for k, v in balance['total'].items() if k != 'KRW'}
        return krw_balance, coin_balance
    except Exception as e:
        print(f"Error fetching balance: {e}")
        return None, None

def get_price(symbol):
    try:
        ticker = upbit.fetch_ticker(symbol)
        return ticker['last']
    except Exception as e:
        print(f"Error fetching price for {symbol}: {e}")
        return None

def main():
    krw_balance, coin_balance = get_balance()
    
    if krw_balance is not None:
        print(f"Current Time: {datetime.datetime.now()}")

        # 비트코인 가격 조회
        btc_price = get_price('BTC/KRW')
        if btc_price is not None:
            print(f"Current BTC Price: {btc_price:.1f} KRW")
        
        # 코인 가격 환산 및 출력
        total_krw_value = krw_balance
        print(f"Current KRW Balance: {krw_balance:.1f}")
        print("Coin Balances (in KRW):")

        for coin, amount in coin_balance.items():
            if amount > 0:
                # 코인 가격 조회
                coin_price = get_price(f'{coin}/KRW')
                if coin_price is not None:
                    coin_value = amount * coin_price
                    total_krw_value += coin_value
                    print(f"{coin}: {amount:.1f} (Value: {coin_value:.1f} KRW)")
                else:
                    print(f"{coin}: {amount:.1f} (Price not available)")
        
        print(f"Total Value in KRW: {total_krw_value:.1f}")
    else:
        print("Failed to retrieve balance.")

if __name__ == "__main__":
    main()