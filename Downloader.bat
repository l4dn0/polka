@echo off
setlocal EnableExtensions
title YouTube Album / Playlist Downloader

if "%~1"=="" chcp 65001 >nul

if not exist "%~dp0yt-dlp.exe" (
    echo [ОШИБКА] Не найден yt-dlp.exe в этой папке!
    if "%~1"=="" pause
    exit /b 1
)

if not exist "%~dp0ffmpeg.exe" (
    echo [ОШИБКА] Не найден ffmpeg.exe в этой папке!
    if "%~1"=="" pause
    exit /b 1
)

if "%~1"=="" goto interactive

set "URL=%~1"
set "TYPE=%~2"
set "FORMAT=%~3"
set "OUTDIR=%~4"
set "IDS=%~5"
set "ARCHIVE=%~6"
set "SPLIT=%~7"
if "%FORMAT%"=="" set "FORMAT=mp3"
if "%OUTDIR%"=="" set "OUTDIR=%~dp0Downloads"
goto download

:interactive
color 0A
echo ==============================================
echo   YouTube Album / Playlist Downloader
echo   Папка: название видео
echo   Треки: 01 - Название.mp3
echo ==============================================
echo.

:start
cls
echo.
set "URL="
set /p "URL=Вставьте ссылку (видео или плейлист): "

if "%URL%"=="" (
    echo Ссылка не введена.
    pause
    goto start
)

echo.
echo Тип:
echo   1 - Одно видео (альбом с главами)
echo   2 - Плейлист
set /p "TYPE=Выбор (1 или 2): "

echo.
echo Формат:
echo   1 - MP3
echo   2 - M4A
echo   3 - OPUS
echo   4 - FLAC
echo   5 - AAC   6 - OGG   7 - WAV   8 - ALAC   9 - как есть (без перекодирования)
set /p "CHOICE=Формат (Enter = MP3): "

set "FORMAT=mp3"
if "%CHOICE%"=="2" set "FORMAT=m4a"
if "%CHOICE%"=="3" set "FORMAT=opus"
if "%CHOICE%"=="4" set "FORMAT=flac"
if "%CHOICE%"=="5" set "FORMAT=aac"
if "%CHOICE%"=="6" set "FORMAT=ogg"
if "%CHOICE%"=="7" set "FORMAT=wav"
if "%CHOICE%"=="8" set "FORMAT=alac"
if "%CHOICE%"=="9" set "FORMAT=best"
echo.
set "SPLIT="
set /p "SPLIT=Разбить на треки по главам? (Enter = да, 0 = нет): "
set "OUTDIR=%~dp0Downloads"

:download
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

echo.
echo ----------------------------------------
echo Ссылка: %URL%
echo Формат: %FORMAT%
echo Папка:  %OUTDIR%
echo ----------------------------------------
echo.
echo Начинаю...
echo.

if "%TYPE%"=="2" (set "PLAYLIST=--yes-playlist") else (set "PLAYLIST=--no-playlist")
rem downloaded.json: skip IDs already listed, append the ID of each finished video
set "SKIP="
if not "%ARCHIVE%"=="" set SKIP=--download-archive "%ARCHIVE%"
set "TRACK="
if not "%IDS%"=="" set TRACK=--print-to-file after_move:id "%IDS%"

rem формат: ogg = vorbis; best = исходная дорожка без перекодирования
set "AFMT=%FORMAT%"
if /i "%FORMAT%"=="ogg" set "AFMT=vorbis"
rem обложку встраиваем только туда, где это надёжно работает
set "THUMB="
for %%T in (mp3 m4a alac flac) do if /i "%FORMAT%"=="%%T" set "THUMB=--embed-thumbnail"
set "COMMON=-x --audio-format %AFMT% --audio-quality 0 %THUMB% --embed-metadata --ignore-errors --newline %PLAYLIST% %SKIP% %TRACK%"

if "%SPLIT%"=="0" goto whole

set "FULL=%OUTDIR%\_full"
if not exist "%FULL%" mkdir "%FULL%"

"%~dp0yt-dlp.exe" %COMMON% --split-chapters --ffmpeg-location "%~dp0." ^
    --parse-metadata "%%(title)s:%%(artist)s - %%(album)s" ^
    -o "%FULL%\%%(title)s.%%(ext)s" ^
    -o "chapter:%OUTDIR%\%%(title)s\%%(section_number)02d - %%(section_title)s.%%(ext)s" ^
    "%URL%"
set "RC=%errorlevel%"
call :cleanup_full
goto finish

:whole
rem без разбиения: видео — папка с названием и один файл; плейлист — папка плейлиста, NN - название
if "%TYPE%"=="2" goto whole_list
"%~dp0yt-dlp.exe" %COMMON% --ffmpeg-location "%~dp0." ^
    --parse-metadata "%%(title)s:%%(artist)s - %%(album)s" ^
    -o "%OUTDIR%\%%(title)s\%%(title)s.%%(ext)s" ^
    "%URL%"
set "RC=%errorlevel%"
goto finish
:whole_list
"%~dp0yt-dlp.exe" %COMMON% --ffmpeg-location "%~dp0." ^
    -o "%OUTDIR%\%%(playlist_title)s\%%(playlist_index)02d - %%(title)s.%%(ext)s" ^
    "%URL%"
set "RC=%errorlevel%"
goto finish

:finish
call :stamp_now
dir /s /b "%OUTDIR%\*.mp3" "%OUTDIR%\*.m4a" "%OUTDIR%\*.flac" "%OUTDIR%\*.opus" "%OUTDIR%\*.aac" "%OUTDIR%\*.ogg" "%OUTDIR%\*.wav" "%OUTDIR%\*.webm" 2>nul | findstr /i "." >nul
if not errorlevel 1 set "RC=0"
echo.
echo ==============================================
if "%RC%"=="0" (
    echo Готово!
    echo Папка: %OUTDIR%
) else (
    echo Была ошибка. Смотрите текст выше.
)
echo ==============================================
echo.

if not "%~1"=="" exit /b %RC%

set /p "AGAIN=Скачать ещё? (Y/N): "
if /i "%AGAIN%"=="Y" goto start
if /i "%AGAIN%"=="Д" goto start

echo.
pause
goto :eof

:stamp_now
echo Прописываю артиста, альбом и названия треков...
where py >nul 2>&1
if not errorlevel 1 (
    py -3 "%~dp0polka.py" --stamp "%OUTDIR%"
    goto :eof
)
where python >nul 2>&1
if not errorlevel 1 python "%~dp0polka.py" --stamp "%OUTDIR%"
goto :eof

:cleanup_full
if not exist "%OUTDIR%\_full" goto trim_all
for %%E in (mp3 m4a flac opus ogg wav webm aac) do (
    for %%F in ("%OUTDIR%\_full\*.%%E") do (
        if exist "%%F" call :sort_full "%%F"
    )
)
rmdir "%OUTDIR%\_full" 2>nul
:trim_all
for /d %%D in ("%OUTDIR%\*") do call :trim_dir "%%D"
goto :eof

:sort_full
dir /b "%OUTDIR%\%~n1\*" 2>nul | findstr /b /r /c:"[0-9][0-9]* - " >nul
if errorlevel 1 (
    if not exist "%OUTDIR%\%~n1" mkdir "%OUTDIR%\%~n1"
    if not exist "%OUTDIR%\%~n1\%~nx1" move /y "%~1" "%OUTDIR%\%~n1\" >nul
    goto :eof
)
del /f /q "%~1"
goto :eof

:trim_dir
if /I "%~nx1"=="_full" goto :eof
dir /b "%~1\*" 2>nul | findstr /b /r /c:"[0-9][0-9]* - " >nul
if errorlevel 1 goto :eof
for %%E in (mp3 m4a flac opus ogg wav webm aac) do (
    for %%F in ("%~1\*.%%E") do (
        if exist "%%F" (
            echo(%%~nF| findstr /b /r /c:"[0-9][0-9]* - " >nul
            if errorlevel 1 del /f /q "%%F"
        )
    )
)
goto :eof
