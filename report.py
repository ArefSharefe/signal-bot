import os
import re
import requests
from dotenv import load_dotenv
import db
from scanner import exchange, fetch_with_retry

load_dotenv()

def short(symbol):
    return symbol.split("/")[0]

def closed_stats(rows):
    n = len(rows)
    if n == 0:
        return 0, 0, 0
    wins = sum(1 for r in rows if r["status"] == "TP")
    total = sum(r["result_pct"] or 0 for r in rows)
    return n, wins / n * 100, total

def floating_pnl(open_rows):
    tickers = fetch_with_retry(exchange.fetch_tickers)
    out = []
    for r in open_rows:
        t = tickers.get(r["symbol"])
        if not t or not t.get("last"):
            continue
        move = (t["last"] - r["entry"]) / r["entry"] * 100
        if r["side"] == "SHORT":
            move = -move
        out.append((r["symbol"], r["side"], move * r["leverage"], t["last"]))
    return out

def build_report():
    db.init()
    with db.connect() as c:
        rows = c.execute("SELECT * FROM signals").fetchall()
    closed = [r for r in rows if r["status"] != "OPEN"]
    open_rows = [r for r in rows if r["status"] == "OPEN"]

    lines = ["📊 <b>گزارش ربات سیگنال</b>", ""]
    lines.append(f"بسته‌شده: {len(closed)}   |   باز: {len(open_rows)}")

    closed_total = 0.0
    if closed:
        n, win, closed_total = closed_stats(closed)
        lines += [
            "",
            "✅ <b>معاملات بسته‌شده</b>",
            f"نرخ برد: {win:.0f}%",
            f"مجموع: {closed_total:+.1f}%",
            f"میانگین هر سیگنال: {closed_total / n:+.1f}%",
        ]
        groups = {}
        for r in closed:
            groups.setdefault(r["strategy"] or "?", []).append(r)
        table = ["Strategy          N  Win    Total"]
        for name, rs in sorted(groups.items()):
            n2, w2, t2 = closed_stats(rs)
            table.append(f"{name:<18}{n2:>2}{w2:>5.0f}%{t2:>+9.1f}%")
        lines += [
            "", "<b>به تفکیک استراتژی</b>",
            "<pre>" + "\n".join(table) + "</pre>",
        ]

    if open_rows:
        try:
            fl = floating_pnl(open_rows)
            fl.sort(key=lambda x: x[2], reverse=True)
            float_total = sum(x[2] for x in fl)
            table = ["Coin       Side      Price        PnL"]
            for sym, side, pnl, price in fl:
                table.append(f"{short(sym):<11}{side:<6}{price:>10.4g}  {pnl:>+7.1f}%")
            lines += [
                "",
                "⏳ <b>سیگنال‌های باز (سود و ضرر لحظه‌ای)</b>",
                "<pre>" + "\n".join(table) + "</pre>",
                f"مجموع لحظه‌ای: {float_total:+.1f}%",
                "",
                f"🧮 <b>جمع کل (بسته + باز): {closed_total + float_total:+.1f}%</b>",
            ]
        except Exception as e:
            print(f"floating pnl failed: {e}")
            lines += ["", "⚠️ دریافت قیمت لحظه‌ای ناموفق بود."]

    lines += [
        "",
        "ℹ️ درصدها با اهرم هر سیگنال و مارجین مساوی حساب شده‌اند. کارمزد و اسلیپیج لحاظ نشده.",
    ]
    return "\n".join(lines)

def main():
    text = build_report()
    print(re.sub(r"<[^>]+>", "", text))
    requests.post(
        f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage",
        data={
            "chat_id": os.getenv("CHAT_ID"),
            "text": text,
            "parse_mode": "HTML",
        },
        timeout=15,
    )

if __name__ == "__main__":
    main()