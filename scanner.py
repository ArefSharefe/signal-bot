import time
import ccxt
import pandas as pd
import numpy as np
import pandas_ta as ta
from ccxt.base.errors import NetworkError, RateLimitExceeded

# ✅ تغییر صرافی از Bybit به KuCoin
exchange = ccxt.kucoin({
    "enableRateLimit": True,
    "options": {"defaultType": "swap"}, # برای معاملات فیوچرز
})

MIN_VOLUME_USDT = 3_000_000
MAX_COINS = 300
SKIP = ("USDC", "FDUSD", "TUSD", "DAI", "USDE", "EUR", "UP/", "DOWN/", "3L", "3S")
SKIP_SYMBOLS = {
    "BTC/USDT:USDT", "ETH/USDT:USDT", "AVAX/USDT:USDT",
    "CASHCAT/USDT:USDT", "EPIC/USDT:USDT", "STRK/USDT:USDT",
    "ARB/USDT:USDT", "AKE/USDT:USDT", "LSK/USDT:USDT",
    "KORU/USDT:USDT", "TRUMP/USDT:USDT", "1000BONK/USDT:USDT",
}

def fetch_with_retry(func, *args, retries=3, **kwargs):
    last_err = None
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except RateLimitExceeded as e:
            last_err = e
            time.sleep(2 ** attempt)
        except NetworkError as e:
            last_err = e
            if attempt == retries - 1:
                raise
            time.sleep(1)
    if last_err:
        raise last_err

def get_symbols():
    exchange.load_markets()
    tickers = fetch_with_retry(exchange.fetch_tickers)
    rows = []
    for symbol, t in tickers.items():
        if not symbol.endswith("/USDT:USDT"):
            continue
        if any(s in symbol for s in SKIP):
            continue
        if symbol in SKIP_SYMBOLS:
            continue
        volume = t.get("quoteVolume") or 0
        if volume >= MIN_VOLUME_USDT:
            rows.append((symbol, volume))
    rows.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in rows[:MAX_COINS]]

def get_df(symbol, timeframe="4h", limit=300):
    candles = fetch_with_retry(
        exchange.fetch_ohlcv, symbol, timeframe=timeframe, limit=limit
    )
    df = pd.DataFrame(
        candles,
        columns=["time", "open", "high", "low", "close", "volume"],
    )
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    return df.iloc[:-1].reset_index(drop=True)

def add_indicators(df):
    df = df.copy()
    # پایه
    df["ema20"] = ta.ema(df["close"], length=20)
    df["ema50"] = ta.ema(df["close"], length=50)
    df["ema200"] = ta.ema(df["close"], length=200)
    df["rsi"] = ta.rsi(df["close"], length=14)
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)
    macd = ta.macd(df["close"])
    df["macd_hist"] = macd["MACDh_12_26_9"]
    df["vol_ratio"] = df["volume"] / df["volume"].rolling(20).mean()

    # سطوح حمایت/مقاومت (برای استراتژی پولبک)
    df["high20"] = df["high"].rolling(20).max().shift(1)
    df["low20"] = df["low"].rolling(20).min().shift(1)
    df["hh10"] = df["high"].rolling(10).max().shift(1)
    df["ll10"] = df["low"].rolling(10).min().shift(1)
    df["hh5"] = df["high"].rolling(5).max().shift(1)
    df["ll5"] = df["low"].rolling(5).min().shift(1)

    # ADX
    adx = ta.adx(df["high"], df["low"], df["close"], length=14)
    df["adx"] = adx.iloc[:, 0]

    # الگوهای کندلی
    body = (df["close"] - df["open"]).abs()
    rng = (df["high"] - df["low"]).replace(0, 1)
    df["body_ratio"] = body / rng
    df["upper_wick"] = (df["high"] - df[["close", "open"]].max(axis=1)) / rng
    df["lower_wick"] = (df[["close", "open"]].min(axis=1) - df["low"]) / rng

    return df

def main():
    # (همان کد قبلی، بدون تغییر)
    pass

if __name__ == "__main__":
    main()
