@echo off
echo Setting Engine Analyzer Path...

REM This file lives in scripts\windows. Default library location is repo-root\engineanalyzer.
set "ENALYZER_LIB_DIR=%~dp0..\..\engineanalyzer"

echo ENALYZER_LIB_DIR set to: %ENALYZER_LIB_DIR%
echo.
echo You can now restart the backend server.
echo To make this permanent, add this environment variable to your system.
pause

