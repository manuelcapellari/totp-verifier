@echo off
setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

cd /d "%~dp0"

set "APP_NAME=TOTPVerifier"
set "ICON_FILE=totp_verifier_icon.ico"
set "PY_FILE="

if exist "totp_verifier.py" set "PY_FILE=totp_verifier.py"
if not defined PY_FILE if exist "test.py" set "PY_FILE=test.py"

if not defined PY_FILE (
    for %%F in (*.py) do (
        if /I not "%%~nxF"=="make.bat" (
            set "PY_FILE=%%~nxF"
            goto :found
        )
    )
)

:found
if not defined PY_FILE (
    echo Keine Python-Datei gefunden.
    echo Legen Sie die Anwendung als .py neben diese make.bat.
    pause
    exit /b 1
)

echo Verwende Script: %PY_FILE%

python --version >nul 2>&1
if errorlevel 1 (
    echo Python wurde nicht gefunden.
    pause
    exit /b 1
)

echo Installiere/aktualisiere Build-Abhaengigkeiten...
python -m pip install --upgrade pip
python -m pip install pyinstaller pyotp pillow opencv-python-headless pymupdf numpy segno reportlab
if errorlevel 1 (
    echo Paketinstallation fehlgeschlagen.
    pause
    exit /b 1
)

if not exist "%ICON_FILE%" (
    echo Warnung: %ICON_FILE% nicht gefunden. Es wird ohne Icon gebaut.
    set "ICON_ARG="
) else (
    set "ICON_ARG=--icon %ICON_FILE%"
)

set "DATA_ARGS="
if exist "totp_verifier_language.json" set "DATA_ARGS=!DATA_ARGS! --add-data totp_verifier_language.json;."
if exist "totp_verifier_settings.json" set "DATA_ARGS=!DATA_ARGS! --add-data totp_verifier_settings.json;."
if exist "%ICON_FILE%" set "DATA_ARGS=!DATA_ARGS! --add-data %ICON_FILE%;."

if exist "build" rmdir /s /q "build"
if exist "dist\%APP_NAME%.exe" del /q "dist\%APP_NAME%.exe"
if exist "%APP_NAME%.spec" del /q "%APP_NAME%.spec"

echo Starte Build einer portablen Einzeldatei...
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name "%APP_NAME%" ^
  %ICON_ARG% ^
  %DATA_ARGS% ^
  "%PY_FILE%"

if errorlevel 1 (
    echo Build fehlgeschlagen.
    pause
    exit /b 1
)

echo.
echo Fertig.
echo Portable EXE: dist\%APP_NAME%.exe
echo.
echo Hinweis:
echo Falls die EXE die Sprachdatei aus dem gleichen Ordner lesen soll,
echo legen Sie totp_verifier_language.json neben die EXE.
echo Die mit eingebundene Version dient nur als eingebettete Standardressource.
echo.
pause