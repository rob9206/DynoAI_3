param(
    [Parameter(Mandatory = $true)]
    [string]$MtFile,

    [Parameter(Mandatory = $true)]
    [string]$OutDir,

    [string]$VeFront = "",
    [string]$VeRear = "",
    [string]$LambdaTsv = "",
    [string]$AppPath = "C:\Program Files (x86)\TTS\HD\MasterTune2-HD\MasterTune2-HD.exe",
    [ValidateSet("map", "tps", "auto")]
    [string]$AxisMode = "auto"
)

$ScriptPath = Join-Path $PSScriptRoot "export_mt_tables_ui.py"

$argsList = @(
    $ScriptPath,
    "--mt-file", $MtFile,
    "--out-dir", $OutDir,
    "--app-path", $AppPath,
    "--axis-mode", $AxisMode
)

if ($VeFront -ne "") {
    $argsList += @("--ve-front", $VeFront)
}
if ($VeRear -ne "") {
    $argsList += @("--ve-rear", $VeRear)
}
if ($LambdaTsv -ne "") {
    $argsList += @("--lambda-tsv", $LambdaTsv)
}

python @argsList
$exitCode = $LASTEXITCODE
exit $exitCode

