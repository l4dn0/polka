@echo off
setlocal EnableExtensions
cd /d "%~dp0"
where node >nul 2>&1
if errorlevel 1 (
  echo Нужен Node.js один раз: https://nodejs.org
  echo Поставь версию LTS и снова открой Polka.bat
  pause
  exit /b 1
)
if not exist "%~dp0electron\node_modules\electron\package.json" (
  echo Первый запуск: скачиваю Electron. Это один раз и занимает несколько минут.
  call npm --prefix "%~dp0electron" install
  if errorlevel 1 (
    echo Не удалось скачать Electron.
    pause
    exit /b 1
  )
)
call npm --prefix "%~dp0electron" start
if errorlevel 1 pause
exit /b 0
