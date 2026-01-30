@echo off
python tools\ai_tuner_toolkit_dyno_v1_2.py --selftest
if errorlevel 1 exit /b 1
python scripts\test\selftest.py
if errorlevel 1 exit /b 1
echo Self-tests PASSED
