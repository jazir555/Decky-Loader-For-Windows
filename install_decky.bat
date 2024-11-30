@echo off
setlocal EnableDelayedExpansion

echo Checking for Python installation...

:: Define minimum required Python version
set MIN_VER_MAJOR=3
set MIN_VER_MINOR=12

:: First check if Python is in PATH
python --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=2 delims=." %%V in ('python -c "import sys; print(sys.version.split()[0])"') do (
        set PYTHON_VER=%%V
        if !PYTHON_VER! GEQ %MIN_VER_MINOR% (
            set "PYTHON_PATH=python"
            echo Found Python in PATH
            goto :python_found
        )
    )
)

:: Check common Python installation paths if not found in PATH
set PYTHON_PATHS=^
    "C:\Python313\python.exe" ^
    "C:\Program Files\Python313\python.exe" ^
    "C:\Program Files (x86)\Python313\python.exe" ^
    "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python313\python.exe" ^
    "C:\Python312\python.exe" ^
    "C:\Program Files\Python312\python.exe" ^
    "C:\Program Files (x86)\Python312\python.exe" ^
    "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\python.exe"

:: Try to find existing Python installation
for %%p in (%PYTHON_PATHS%) do (
    if exist %%p (
        set "PYTHON_PATH=%%p"
        echo Found Python at: !PYTHON_PATH!
        goto :python_found
    )
)

:python_not_found
echo No suitable Python installation found. Installing Python %MIN_VER_MAJOR%.%MIN_VER_MINOR%...
curl -o python_installer.exe https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe

echo Installing Python %MIN_VER_MAJOR%.%MIN_VER_MINOR%...
start /wait python_installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 Include_pip=1

echo Cleaning up...
del python_installer.exe

echo Python installation completed!
echo Waiting for installation to complete...
timeout /t 10 /nobreak

:: Set default Python path after installation
set "PYTHON_PATH=C:\Program Files\Python312\python.exe"

:python_found
echo Installing required Python packages...
"%PYTHON_PATH%" -m pip install --upgrade pip
"%PYTHON_PATH%" -m pip install pywin32 pyinstaller

echo Python setup completed successfully.
echo Running Decky Loader installer...
"%PYTHON_PATH%" decky_builder.py
pause