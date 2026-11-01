import time
import traceback
from datetime import datetime, timezone, timedelta
import signals

IRAN = timedelta(hours=3, minutes=30)

def run_4h():
    now = datetime.now(timezone.utc) + IRAN
    print(f"\n[{now:%H:%M}] ⏳ شروع اسکن ۴ ساعته...")
    try:
        signals.main_4h()
        print(f"[{now:%H:%M}] ✅ اسکن ۴ ساعته تمام شد.")
    except Exception as e:
        print(f"[{now:%H:%M}] ❌ خطا در ۴ ساعته: {e}")
        traceback.print_exc()

def run_1h():
    now = datetime.now(timezone.utc) + IRAN
    print(f"\n[{now:%H:%M}] ⏳ شروع اسکن ۱ ساعته...")
    try:
        signals.main_1h()
        print(f"[{now:%H:%M}] ✅ اسکن ۱ ساعته تمام شد.")
    except Exception as e:
        print(f"[{now:%H:%M}] ❌ خطا در ۱ ساعته: {e}")
        traceback.print_exc()

def run_15m():
    now = datetime.now(timezone.utc) + IRAN
    print(f"\n[{now:%H:%M}] ⏳ شروع اسکن ۱۵ دقیقه...")
    try:
        signals.main_15m()
        print(f"[{now:%H:%M}] ✅ اسکن ۱۵ دقیقه تمام شد.")
    except Exception as e:
        print(f"[{now:%H:%M}] ❌ خطا در ۱۵ دقیقه: {e}")
        traceback.print_exc()

def run_1d():
    now = datetime.now(timezone.utc) + IRAN
    print(f"\n[{now:%H:%M}] ⏳ شروع اسکن ۱ روزه...")
    try:
        signals.main_1d()
        print(f"[{now:%H:%M}] ✅ اسکن ۱ روزه تمام شد.")
    except Exception as e:
        print(f"[{now:%H:%M}] ❌ خطا در ۱ روزه: {e}")
        traceback.print_exc()

def get_next_run_time(now, interval_minutes, offset_minutes=2):
    """محاسبه دقیق زمان اجرای بعدی بر اساس دقیقه"""
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    minutes_since_midnight = now.hour * 60 + now.minute
    next_interval = (minutes_since_midnight // interval_minutes + 1) * interval_minutes
    return midnight + timedelta(minutes=next_interval + offset_minutes)

print("🚀 Bot started. Running 15m, 1h, 4h, 1d scans...")
signals.send_startup_message()

# اجرای اولیه
run_4h()
run_1h()
run_15m()
run_1d()

while True:
    now = datetime.now(timezone.utc)
    
    # محاسبه زمان‌های بعدی با تابع جدید
    next_15m = get_next_run_time(now, 15)
    next_1h = get_next_run_time(now, 60)
    next_4h = get_next_run_time(now, 240)
    next_1d = get_next_run_time(now, 1440)
    
    wait_15m = (next_15m - now).total_seconds()
    wait_1h = (next_1h - now).total_seconds()
    wait_4h = (next_4h - now).total_seconds()
    wait_1d = (next_1d - now).total_seconds()

    # پیدا کردن نزدیک‌ترین زمان
    waits = [wait_15m, wait_1h, wait_4h, wait_1d]
    min_wait = min(waits)
    idx = waits.index(min_wait)

    now_ir = now + IRAN
    next_name = '15m' if idx==0 else '1h' if idx==1 else '4h' if idx==2 else '1d'
    print(f"[{now_ir:%H:%M}] 💤 در حال انتظار... (بعدی: {next_name} در {min_wait/60:.1f} دقیقه دیگر)")

    time.sleep(max(min_wait, 1))
    
    if idx == 0:
        run_15m()
    elif idx == 1:
        run_1h()
    elif idx == 2:
        run_4h()
    else:
        run_1d()