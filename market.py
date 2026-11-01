from scanner import get_df, add_indicators

PANIC_RATIO = 3.0

def market_state():
    df = add_indicators(get_df("BTC/USDT:USDT", timeframe="4h"))
    last = df.iloc[-1]

    ranges = (df["high"] - df["low"]) / df["close"]
    avg = ranges.iloc[-53:-3].mean()
    recent = ranges.iloc[-3:].max()
    ratio = recent / avg if avg > 0 else 1
    if ratio >= PANIC_RATIO:
        return "VOLATILE", f"range ratio {ratio:.1f}"

    if last["close"] > last["ema50"] > last["ema200"] and last["adx"] > 20:
        return "UP", f"BTC uptrend (ADX {last['adx']:.0f})"
    if last["close"] < last["ema50"] < last["ema200"] and last["adx"] > 20:
        return "DOWN", f"BTC downtrend (ADX {last['adx']:.0f})"
    return "MIXED", f"BTC no clear trend (ADX {last['adx']:.0f})"

def allowed(state, side, strategy):
    if state == "VOLATILE":
        return False

    is_range = "range" in strategy
    is_trend = any(k in strategy for k in ("pullback", "structure", "macd_cross", "engulfing"))

    if state == "UP":
        return side == "LONG" and not is_range
    if state == "DOWN":
        return side == "SHORT" and not is_range
    
    # MIXED: هم رنج، هم روند
    return is_range or is_trend