param([string]$PythonExecutable = 'python')
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '../..')
& $PythonExecutable -m scripts.windows.build
if ($LASTEXITCODE -ne 0) { throw 'Construction ou verification Windows impossible' }
