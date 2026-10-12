@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 goto use_python

py -3 app.py %*
goto check_result

:use_python
python app.py %*

:check_result
if errorlevel 1 goto failed
endlocal
exit /b 0

:failed
echo.
echo OpenCodex Switcher failed to start.
echo Install Python and the packages listed in requirements.txt, then try again.
pause
endlocal
exit /b 1
