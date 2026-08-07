@echo off
chcp 65001 >nul
title Avtobus - holat
echo ====================================================
echo   AVTOBUS - litsenziya holati va qurilma ID
echo ====================================================
echo.
"%~dp0Avtobus.exe" --license-status
echo.
echo ----------------------------------------------------
echo  Qurilma HARDWARE ID (litsenziya uchun vendorga yuboring):
echo ----------------------------------------------------
"%~dp0Avtobus.exe" --hwid
echo.
echo Litsenziya faylini o'rnatish:
echo    "%~dp0Avtobus.exe" --license C:\yo'l\license.key
echo.
pause
