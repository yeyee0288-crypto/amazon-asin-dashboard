@echo off
title Amazon ASIN Dashboard
echo ============================================
echo   Amazon ASIN Dashboard
echo ============================================
echo.
echo 正在启动本地服务，浏览器会自动打开 http://127.0.0.1:8080
echo 如果没有自动打开，请手动访问上面的地址。
echo.

python app.py --port 8080

pause
