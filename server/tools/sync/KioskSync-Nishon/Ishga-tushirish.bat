@echo off
chcp 65001 >nul
title Kiosk kontent qabulchisi
echo.
echo  Kontent qabul qilish oynasi ochilmoqda...
echo  (Firewall ruxsat sorasa - "Ruxsat berish" / "Allow" bosing)
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0receiver.ps1"
echo.
echo  Oyna yopildi. Chiqish uchun istalgan tugmani bosing.
pause >nul
