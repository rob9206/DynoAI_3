# PowerShell equivalents

# 1) Create venv + install deps
py -3.11 -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

# Optional: install hooks
if (Test-Path .pre-commit-config.yaml) {
  pip install pre-commit
  pre-commit install
}

# 2) Patch help strings and ensure --selftest (idempotent)
if (Test-Path .\fix_helppercents.py) {
  python .\fix_helppercents.py .\tool\ai_tuner_toolkit_dyno_v1_2.py
}
if (Test-Path .\patch_selftest.py) {
  python .\patch_selftest.py .\tool\ai_tuner_toolkit_dyno_v1_2.py
}

# 3) Run self-test
python .\tool\ai_tuner_toolkit_dyno_v1_2.py --selftest --outdir .\outputs
python .\selftest.py

# 4) Run a real CSV (edit paths)
$csv = "C:\DynoAI\data\winpep_export.csv"
$out = "outputs\run_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"

$cmd = "python .\tool\ai_tuner_toolkit_dyno_v1_2.py --csv `"$csv`" --outdir `"$out`" --smooth_passes 2 --clamp 15 --rear_bias 2.5 --rear_rule_deg 2.0 --hot_extra -1.0"
# Optional base tables
#$cmd += " --base_front `"C:\DynoAI\tables\FXDLS_Wheelie_VE_Base_Front.csv`""
# $cmd += " --base_rear  `"C:\DynoAI\tables\FXDLS_Wheelie_VE_Base_Rear.csv`""

Write-Host "Running: $cmd"
Invoke-Expression $cmd
