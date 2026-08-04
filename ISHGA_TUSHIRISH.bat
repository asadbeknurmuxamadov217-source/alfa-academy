@echo off
title ALFA Academy Web Sayti
color 0B
echo ========================================================
echo         ALFA ACADEMY SAYTI ISHGA TUSHMOQDA...
echo ========================================================
echo.
echo Brauzer avtomatik ochilmoqda: http://127.0.0.1:8000
echo Serverni to'xtatish uchun ushbu oynani yoping.
echo.
timeout /t 2 /nobreak >nul
start http://127.0.0.1:8000
python manage.py runserver 0.0.0.0:8000
pause
