import os
import time
import requests
from dotenv import load_dotenv
import db
import report

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_CHAT = os.getenv("CHAT_ID")

HELP = """📖 دستورات ربات:

/report — گزارش کامل
/open — سیگنال‌های باز
/stats — آمار کوتاه
/help — این راهنما"""

def send(chat_id, text, parse_mode=None):
    data = {"chat_id": chat_id, "text": text}
    if parse_mode:
        data["parse_mode"] = parse_mode
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data, timeout=15)
    except Exception as e:
        print(f"send failed: {e}")

def cmd_open():
    db.init()
    rows = db.get_open()
    if not rows:
        return "هیچ سیگنال بازی نداری."
    lines = ["⏳ سیگنال‌های باز:"]
    for r in rows:
        lines.append(f"{r['symbol']} {r['side']} ({r['timeframe']}) | entry {r['entry']:.4g} | lev {r['leverage']}x")
    return "\n".join(lines)

def cmd_stats():
    db.init()
    with db.connect() as c:
        rows = c.execute("SELECT * FROM signals").fetchall()
    closed = [r for r in rows if r["status"] != "OPEN"]
    open_rows = [r for r in rows if r["status"] == "OPEN"]
    if not closed:
        return f"هنوز معامله بسته‌شده‌ای نداریم. ({len(open_rows)} باز)"
    wins = sum(1 for r in closed if r["status"] == "TP")
    total = sum(r["result_pct"] or 0 for r in closed)
    return (
        f"📊 آمار:\n"
        f"بسته: {len(closed)} | باز: {len(open_rows)}\n"
        f"برد: {wins}/{len(closed)} ({wins / len(closed) * 100:.0f}%)\n"
        f"مجموع: {total:+.1f}%"
    )

def handle(update):
    msg = update.get("message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip().lower()
    if not chat_id or not text:
        return
    if str(chat_id) != str(ALLOWED_CHAT):
        return

    if text == "/report":
        send(chat_id, report.build_report(), "HTML")
    elif text == "/open":
        send(chat_id, cmd_open())
    elif text == "/stats":
        send(chat_id, cmd_stats())
    elif text in ("/start", "/help"):
        send(chat_id, HELP)
    else:
        send(chat_id, "دستور نامعتبر. /help رو بزن.")

def main():
    print("Bot commands listener started.")
    offset = 0
    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=40,
            ).json()
            for u in r.get("result", []):
                offset = u["update_id"] + 1
                handle(u)
        except Exception as e:
            print(f"poll error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()