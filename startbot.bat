@echo off
C:\Users\badri\Downloads\telegram_payment_bot\telegram_payment_bot
echo Waiting for internet connection .. 
:checkInternet
ping -n 1 google.com >nul 2>&1
if errorlevel 1 (
echo No internet yet .. retrying in 10 seconds.
timout /t 10 >nul
goto checkInternet
)
echo internet connected! starting bot..
python cluster_runner.py
pause