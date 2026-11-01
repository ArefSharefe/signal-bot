@echo off
cd /d C:\signal_bot_2
call venv\Scripts\activate
taskkill /F /IM python.exe 2>nul
timeout /t 2 >nul
start "Signal Loop" python run_loop.py
start "Bot Commands" python bot_commands.py
echo ربات‌ها اجرا شدند. برای توقف، پنجره‌ها را ببندید.
pause