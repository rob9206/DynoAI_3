@echo off
setlocal

REM === Project bootstrap (Windows, Python 3.11) ===
set PROJECT_DIR=%~dp0..\..
pushd "%PROJECT_DIR%"

if not exist .venv (
  py -3.11 -m venv .venv
)

call .venv\Scripts\activate

python -m pip install --upgrade pip
if exist requirements.txt (
  pip install -r requirements.txt
)

REM Optional: pre-commit hooks if config exists
if exist .pre-commit-config.yaml (
  pip install pre-commit
  pre-commit install
)

REM Fix argparse help % signs and ensure --selftest support (idempotent)
if exist fix_helppercents.py (
  python fix_helppercents.py tool\ai_tuner_toolkit_dyno_v1_2.py
)
if exist patch_selftest.py (
  python patch_selftest.py tool\ai_tuner_toolkit_dyno_v1_2.py
)

REM Run built-in self-test (generates a synthetic CSV + outputs)
python tool\ai_tuner_toolkit_dyno_v1_2.py --selftest --outdir outputs

REM If a dedicated selftest exists, run it too
if exist selftest.py (
  python selftest.py
)

echo.
echo Done. If you saw "Self-tests PASSED", you're good.
popd
