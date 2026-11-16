param([string]$Csv, [int]$Limit = 900, [string]$Out = 'C:\Users\23R\fb-bench\tle_one.json')
# Launch the measurement inside the console session and wait for its result file.
# The measuring loop cannot run here: this session cannot see another session's windows.
[System.IO.File]::WriteAllText('C:\Users\23R\fb-bench\current.txt', $Csv)
if (Test-Path $Out) { Remove-Item $Out -Force }
Remove-Item ($Out -replace '\.json$', '.png') -Force -ErrorAction SilentlyContinue

$args = '-NoProfile -ExecutionPolicy Bypass -File "C:\Users\23R\fb-bench\te_measure.ps1" -Csv "' + $Csv + '" -Out "' + $Out + '" -Limit ' + $Limit
@"
@echo off
start "" /wait powershell $args
"@ | Set-Content -Path 'C:\Users\23R\fb-bench\run_measure.cmd' -Encoding ASCII

& schtasks.exe /delete /tn FirebladeTLEBench /f 2>&1 | Out-Null
& schtasks.exe /create /tn FirebladeTLEBench /tr '"C:\Users\23R\fb-bench\run_measure.cmd"' /sc ONCE /st 23:59 /ru "$env:COMPUTERNAME\$env:USERNAME" /it /f 2>&1 | Out-Null
& schtasks.exe /run /tn FirebladeTLEBench 2>&1 | Out-Null

$deadline = (Get-Date).AddSeconds($Limit + 120)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    if (Test-Path $Out) { break }
}
if (Test-Path $Out) { Get-Content $Out -Raw } else { Write-Output '{"state":"no-result"}' }
& schtasks.exe /delete /tn FirebladeTLEBench /f 2>&1 | Out-Null
