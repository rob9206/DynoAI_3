@echo off
setlocal

REM === Example: run DynoAI on a real WinPEP CSV ===
REM Usage: scripts\run_csv_example.bat C:\path\to\winpep.csv C:\path\to\outputs
REM Optional base VE front/rear CSVs can be set via environment variables:
REM   set BASE_FRONT=C:\path\to\FXDLS_Wheelie_VE_Base_Front.csv
REM   set BASE_REAR=C:\path\to\FXDLS_Wheelie_VE_Base_Rear.csv

if "%~1"=="" (
  echo Usage: %~nx0 ^<winpep.csv^> [outdir]
  exit /b 2
)

set CSV=%~1
set OUTDIR=%~2
if "%OUTDIR%"=="" set OUTDIR=outputs\run_%DATE:~10,4%-%DATE:~4,2%-%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%

set PROJECT_DIR=%~dp0..\..
pushd "%PROJECT_DIR%"
call .venv\Scripts\activate

set CMD=python tool\ai_tuner_toolkit_dyno_v1_2.py --csv "%CSV%" --outdir "%OUTDIR%" --smooth_passes 2 --clamp 15 --rear_bias 2.5 --rear_rule_deg 2.0 --hot_extra -1.0

if NOT "%BASE_FRONT%"=="" set CMD=%CMD% --base_front "%BASE_FRONT%"
if NOT "%BASE_REAR%"=="" set CMD=%CMD% --base_rear "%BASE_REAR%"

echo Running: %CMD%
%CMD%

echo Outputs written to: %OUTDIR%
popd
