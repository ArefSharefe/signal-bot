import os
import logging
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from scanner import get_symbols, get_df, add_indicators, exchange, fetch_with_retry
import strategies
import market
import db

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STOP_ATR = 1.5
TP_ATR = 3.0
MARGIN_LOSS_PCT = 20
MAX_LEVERAGE = 4
MIN_STOP_PCT = 1.5
MAX_STOP_PCT = 6.0
MAX_OPEN = 15
MIN_SCORE = 80
MAX_DRIFT_ATR = 0.5
COOLDOWN_HOURS = 12
USE_1D_ALIGN = True

LINE = "━━━━━━━━━━━━━━"
IRAN = timedelta(hours=3, minutes=30)

# ✅ این بخش جا افتاده بود، این رو اضافه کن:
STATE_FA = {
    "UP": "صعودی (فقط لانگ)",
    "DOWN": "نزولی (فقط شورت)",
    "MIXED": "نامشخص (فقط پولبک)",
    "VOLATILE": "نوسان شدید (توقف)",
}

logging.basicConfig(filename="bot.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

def send(text, reply_markup=None):
    payload = {"chat_id": CHAT_ID, "text": text}
    if reply_markup:
        import json
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=payload, timeout=15)
        if r.status_code != 200:
            print(f"❌ خطای تلگرام: {r.text}")
    except Exception as e:
        print(f"❌ خطای شبکه در تلگرام: {e}")

def send_log(lines):
    try:
        send("\n".join(lines))
    except Exception as e:
        log.error(f"log send failed: {type(e).__name__}")

def iran_now():
    return datetime.now(timezone.utc) + IRAN

def header():
    return ["🤖 گزارش اجرا", f"🕐 {iran_now():%H:%M} (ایران)", LINE]

def closed_line(closed):
    return f"🔒 بسته‌شده در این اجرا: ✅ {closed.count('TP')} | ❌ {closed.count('STOP')}"

def daily_aligned(symbol, side):
    if not USE_1D_ALIGN:
        return True
    try:
        df = add_indicators(get_df(symbol, timeframe="1d", limit=220))
        if len(df) < 200 or df["ema200"].isna().iloc[-1]:
            return True
        last = df.iloc[-1]
        if side == "LONG":
            return last["close"] > last["ema50"]
        return last["close"] < last["ema50"]
    except Exception as e:
        log.warning(f"1d check failed {symbol}: {type(e).__name__}")
        return True

def build_signal(symbol, row, side, strategy, tf):
    entry = row["close"]
    atr = row["atr"]
    if side == "LONG":
        stop = entry - STOP_ATR * atr
        tp = entry + TP_ATR * atr
    else:
        stop = entry + STOP_ATR * atr
        tp = entry - TP_ATR * atr
    stop_pct = abs(entry - stop) / entry * 100
    tp_pct = abs(tp - entry) / entry * 100
    leverage = int(max(1, min(MAX_LEVERAGE, MARGIN_LOSS_PCT // stop_pct)))
    return {
        "symbol": symbol, "side": side, "strategy": strategy,
        "entry": entry, "stop": stop, "tp": tp,
        "stop_pct": stop_pct, "tp_pct": tp_pct,
        "leverage": leverage,
        "n_confirm": max(0, strategy.count("+") - 1),
        "vol_ratio": float(row["vol_ratio"]),
        "adx": float(row["adx"]),
        "signal_time": row["time"].isoformat(),
        "timeframe": tf,
    }

def score_signal(s):
    pts = 40
    pts += 12 * min(s["n_confirm"], 2)
    v = s["vol_ratio"]
    pts += 12 if v >= 1.5 else 6 if v >= 1.0 else 0
    adx = s["adx"]
    pts += 15 if 25 <= adx <= 45 else 8 if adx >= 20 else 0
    if 2 <= s["stop_pct"] <= 5:
        pts += 8
    return min(pts, 100)

def check_open_signals():
    closed = []
    for sig in db.get_open():
        try:
            df = get_df(sig["symbol"], timeframe=sig["timeframe"])
            sig_time = pd.to_datetime(sig["signal_time"]).tz_localize(None)
            df["time"] = pd.to_datetime(df["time"]).dt.tz_localize(None)
            df = df[df["time"] > sig_time]
            for _, c in df.iterrows():
                if sig["side"] == "LONG":
                    hit_stop = c["low"] <= sig["stop"]
                    hit_tp = c["high"] >= sig["tp"]
                else:
                    hit_stop = c["high"] >= sig["stop"]
                    hit_tp = c["low"] <= sig["tp"]
                if not (hit_stop or hit_tp):
                    continue
                status = "STOP" if hit_stop else "TP"
                exit_price = sig["stop"] if hit_stop else sig["tp"]
                move = (exit_price - sig["entry"]) / sig["entry"] * 100
                if sig["side"] == "SHORT":
                    move = -move
                result = move * sig["leverage"]
                db.close_signal(sig["id"], status, result, str(c["time"]))
                closed.append(status)
                emoji = "✅" if status == "TP" else "❌"
                send(f"{emoji} {status} {sig['side']} {sig['symbol']} ({sig['timeframe']})\nنتیجه با اهرم {sig['leverage']}x: {result:+.1f}%")
                break
        except Exception as e:
            log.error(f"check failed {sig['symbol']}: {type(e).__name__}")
    return closed

def run_scan(timeframe):
    db.init()
    closed = check_open_signals()

    try:
        state, info = market.market_state()
    except Exception as e:
        log.error(f"Market check failed: {type(e).__name__}")
        return

    log.info(f"Market: {state} ({info})")
    market_line = f"📈 وضعیت بازار: {STATE_FA.get(state, state)}"

    open_rows = db.get_open()
    skip = {r["symbol"] for r in open_rows}
    counts = {"LONG": 0, "SHORT": 0}
    for r in open_rows:
        counts[r["side"]] += 1
    slots = MAX_OPEN - len(open_rows)

    if state == "VOLATILE" or slots <= 0:
        return

    try:
        tickers = fetch_with_retry(exchange.fetch_tickers)
    except Exception as e:
        log.error(f"Ticker fetch failed: {type(e).__name__}")
        return

    stats = {"scanned": 0, "raw": 0, "market": 0, "drift": 0, "stop": 0, "score": 0, "cooldown": 0, "1d": 0}
    signals = []

    for symbol in get_symbols():
        if symbol in skip or db.recently_signaled(symbol, timeframe, hours=COOLDOWN_HOURS):
            stats["cooldown"] += 1
            continue
        stats["scanned"] += 1
        try:
            df = get_df(symbol, timeframe=timeframe)
            if len(df) < 210: continue
            df = add_indicators(df)
            if df["ema200"].isna().iloc[-1]: continue

            result = strategies.evaluate_fresh(df, timeframe)
            if not result: continue
            stats["raw"] += 1
            name, side = result

            if not market.allowed(state, side, name):
                stats["market"] += 1
                continue

            last_price = (tickers.get(symbol) or {}).get("last")
            row = df.iloc[-1]
            if not last_price or abs(last_price - row["close"]) > MAX_DRIFT_ATR * row["atr"]:
                stats["drift"] += 1
                continue

            s = build_signal(symbol, row, side, name, timeframe)
            if not (MIN_STOP_PCT <= s["stop_pct"] <= MAX_STOP_PCT):
                stats["stop"] += 1
                continue
            if not daily_aligned(symbol, side):
                stats["1d"] += 1
                continue

            s["score"] = score_signal(s)
            if s["score"] < MIN_SCORE:
                stats["score"] += 1
                continue
            signals.append(s)
        except Exception as e:
            log.warning(f"skip {symbol}: {type(e).__name__}")

    signals.sort(key=lambda s: s["score"], reverse=True)
    chosen = signals[:slots]

    for s in chosen:
        db.save_signal(s)
        counts[s["side"]] += 1
        icon = "🟢" if s["side"] == "LONG" else "🔴"
        send(f"{icon} {s['side']} {s['symbol']} ({s['timeframe']})\nامتیاز: {s['score']}/100\nاهرم: {s['leverage']}x\nاستراتژی: {s['strategy']}\nورود: {s['entry']:.6g}\nاستاپ: {s['stop']:.6g} ({s['stop_pct']:.1f}%)\nتی‌پی: {s['tp']:.6g} ({s['tp_pct']:.1f}%)\n⚠️ آزمایشی")

    send_log(header() + [market_line, f"🔍 اسکن {timeframe}: {stats['scanned']} ارز", f"✅ سیگنال جدید: {len(chosen)}", closed_line(closed)] + [LINE])

def main_4h():
    run_scan("4h")

def main_1h():
    run_scan("1h")

def main_15m():
    run_scan("15m")

def main_1d():
    run_scan("1d")

def send_startup_message():
    msg = "🚀 ربات با موفقیت راه‌اندازی شد.\n"
    msg += f"🕐 زمان: {iran_now():%H:%M} (ایران)\n"
    msg += "📊 تایم‌فریم‌های فعال: 15m, 1h, 4h, 1d\n"
    msg += "✅ آماده دریافت سیگنال‌ها."
    send(msg)

if __name__ == "__main__":
    main_4h() # پیش‌فرض
