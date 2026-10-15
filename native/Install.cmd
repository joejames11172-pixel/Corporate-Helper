@echo off
setlocal
cd /d "%~dp0"
set "CORPORATE_PYTHON="
if exist "C:\Python34\python.exe" set "CORPORATE_PYTHON=C:\Python34\python.exe"
if not defined CORPORATE_PYTHON (
  if not exist "%~dp0python-3.4.4.msi" (
    echo Python runtime is missing from this installation package.
    pause
    exit /b 1
  )
  start /wait msiexec /i "%~dp0python-3.4.4.msi" /qn ALLUSERS=1 TARGETDIR=C:\Python34
  if exist "C:\Python34\python.exe" set "CORPORATE_PYTHON=C:\Python34\python.exe"
)
if not defined CORPORATE_PYTHON (
 echo Python installation did not complete. Corporate Helper was not installed.
 pause
 exit /b 1
)
"%CORPORATE_PYTHON%" -E -s -B "%~dp0install_windows.py"
echo.
pause
