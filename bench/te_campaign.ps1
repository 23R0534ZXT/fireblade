# One file at a time, each in its own scheduled session run, so a failure on the biggest
# file does not cost the four smaller ones. Results are appended as they end.
$plan = @(
    @{ rows = 250000;    limit = 420 },
    @{ rows = 1000000;   limit = 600 },
    @{ rows = 4000000;   limit = 900 },
    @{ rows = 16000000;  limit = 1500 },
    @{ rows = 32000000;  limit = 1800 }
)
$jsonl = 'C:\Users\23R\fb-bench\tleops-all.jsonl'
if (Test-Path $jsonl) { Remove-Item $jsonl -Force }
foreach ($item in $plan) {
    $s = $item.rows
    $csv = 'C:\Users\23R\fb-bench\size-' + $s + '-1\auth.log.csv'
    $out = 'C:\Users\23R\fb-bench\tleops_size-' + $s + '.json'
    if (-not (Test-Path $csv)) { Write-Output ("missing " + $csv); continue }
    $payload = '-Csv "' + $csv + '" -Tag size-' + $s + ' -Out "' + $out + '"'
    Write-Output ("=== " + $s + " rows (" + [math]::Round((Get-Item $csv).Length / 1MB, 0) + " MiB) ===")
    if (Test-Path $out) { Remove-Item $out -Force }
    & powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Users\23R\session_run.ps1' -Script 'C:\Users\23R\te_ops.ps1' -Payload $payload -Out $out -Limit $item.limit | Out-Null
    if (Test-Path $out) {
        $raw = Get-Content $out -Raw
        $j = $raw | ConvertFrom-Json
        Write-Output ("  load " + $j.load_seconds + " s")
        foreach ($st in $j.steps) { Write-Output ("  " + $st.step + " : " + $st.seconds + " s") }
        if ($j.failed) { Write-Output ("  FAILED: " + $j.failed) }
        Add-Content -Path $jsonl -Value (($raw -replace "`r?`n", ' ').Trim())
    } else { Write-Output '  NO RESULT' }
}
Write-Output 'CAMPAIGN DONE'
