"""
استراتژی‌های جامع برای تایم‌فریم‌های 15m, 1h, 4h, 1d.
- استراتژی اصلی: Pullback به EMA + شکست ساختار + تأییدیه Breakout.
- استراتژی 1d: MACD Cross + Moving Average.
- استراتژی 15m: تأیید روند 1h/4h + الگوی کندلی Engulfing.
"""

def pullback_core(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    recent = df.iloc[-3:]

    if last["close"] > last["ema50"] > last["ema200"]:
        touched = recent["low"].min() <= last["ema50"] * 1.008
        bounce = last["close"] > prev["high"] and 38 < last["rsi"] < 62
        structure_ok = last["close"] > last["hh10"]
        if touched and bounce and structure_ok:
            return "LONG"

    if last["close"] < last["ema50"] < last["ema200"]:
        touched = recent["high"].max() >= last["ema50"] * 0.992
        bounce = last["close"] < prev["low"] and 38 < last["rsi"] < 62
        structure_ok = last["close"] < last["ll10"]
        if touched and bounce and structure_ok:
            return "SHORT"
    return None


def breakout_confirm(df):
    last = df.iloc[-1]
    if last["close"] > last["hh5"] and last["close"] > last["ema200"]:
        return "LONG"
    if last["close"] < last["ll5"] and last["close"] < last["ema200"]:
        return "SHORT"
    return None


def engulfing_pattern(df):
    """الگوی کندلی Engulfing"""
    last = df.iloc[-1]
    prev = df.iloc[-2]
    prev_body = abs(float(prev["close"]) - float(prev["open"]))
    last_body = abs(float(last["close"]) - float(last["open"]))
    
    if prev_body == 0 or last_body < prev_body * 1.3: return None
    if last["body_ratio"] < 0.6: return None
    
    if (prev["close"] < prev["open"] and last["close"] > last["open"] 
        and last["close"] > prev["open"] and last["close"] > last["ema50"]):
        return "LONG"
    if (prev["close"] > prev["open"] and last["close"] < last["open"] 
        and last["close"] < prev["open"] and last["close"] < last["ema50"]):
        return "SHORT"
    return None


def macd_cross(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    if prev["macd_hist"] <= 0 and last["macd_hist"] > 0:
        if last["close"] > last["ema200"]: return "LONG"
    if prev["macd_hist"] >= 0 and last["macd_hist"] < 0:
        if last["close"] < last["ema200"]: return "SHORT"
    return None


def evaluate(df, timeframe="4h"):
    """تابع اصلی ارزیابی که بر اساس تایم‌فریم تصمیم می‌گیرد."""
    if timeframe == "1d":
        # استراتژی روزانه: MACD Cross + تأیید EMA
        res = macd_cross(df)
        if res:
            return "macd_cross", res
        return None
    
    if timeframe == "15m":
        # استراتژی 15 دقیقه: Engulfing + تأیید روند (از قبل در df داریم)
        res = engulfing_pattern(df)
        if res:
            return "engulfing", res
        return None
    
    # استراتژی‌های اصلی برای 1h و 4h
    core = pullback_core(df)
    if not core:
        return None

    if breakout_confirm(df) != core:
        return None

    return "pullback+structure+breakout", core


def evaluate_fresh(df, timeframe="4h", lookback=2):
    cur = evaluate(df, timeframe)
    if not cur:
        return None
    for i in range(1, lookback + 1):
        if len(df) <= i + 210:
            continue
        prev = evaluate(df.iloc[:-i], timeframe)
        if prev and prev[1] == cur[1]:
            return None
    return cur