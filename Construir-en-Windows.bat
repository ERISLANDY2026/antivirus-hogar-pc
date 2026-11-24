@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Construir Antivirus Hogar PC

echo ============================================================
echo   Antivirus Hogar PC - construccion del instalador (.exe)
echo ============================================================
echo.

REM --- 1. Python 3.11+ ---------------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] No se encontro Python. Instalalo desde https://www.python.org
    echo         marcando "Add python.exe to PATH" y vuelve a intentarlo.
    pause
    exit /b 1
    )
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
    echo [ERROR] Se necesita Python 3.11 o superior.
    python --version
    pause
    exit /b 1
    )
python --version
echo.

REM --- 2. Dependencias ----------------------------------------------------
echo [1/4] Instalando dependencias (requirements.txt + PyInstaller)...
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :error
echo.

REM --- 3. PyInstaller (--onedir) ------------------------------------------
echo [2/4] Compilando la aplicacion con PyInstaller...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
python -m PyInstaller packaging\antivirus-hogar-pc.spec --noconfirm
if errorlevel 1 goto :error
if not exist "dist\AntivirusHogarPC\AntivirusHogarPC.exe" (
    echo [ERROR] PyInstaller termino sin producir AntivirusHogarPC.exe.
    goto :error
    )
echo.

REM --- 4. Inno Setup -------------------------------------------------------
echo [3/4] Buscando Inno Setup (ISCC.exe)...
set "ISCC="
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe") do (
    if not defined ISCC if exist %%~P set "ISCC=%%~P"
    )
if not defined ISCC (
    echo [ERROR] No se encontro Inno Setup 6. Descargalo gratis de
    echo         https://jrsoftware.org/isdl.php e instalalo; luego repite.
    echo         La aplicacion compilada ya esta en dist\AntivirusHogarPC\
    pause
    exit /b 1
    )

echo [4/4] Creando el instalador con Inno Setup...
"%ISCC%" packaging\instalador.iss
if errorlevel 1 goto :error
echo.
echo ============================================================
echo   LISTO: dist-instalador\Instalador-AntivirusHogarPC-1.0.1.exe
echo   Sin firmar: Windows mostrara el aviso de SmartScreen la
echo   primera vez ("Mas informacion" -^> "Ejecutar de todas formas").
echo ============================================================
pause
exit /b 0

:error
echo.
echo [ERROR] La construccion se detuvo. Revisa el mensaje anterior.
pause
exit /b 1
