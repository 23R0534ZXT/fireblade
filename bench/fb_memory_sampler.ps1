param([int]$IntervalMs = 200, [string]$Out = 'C:\Users\23R\fb-bench\fb_peak_memory.txt', [int]$MaxMinutes = 25)
# Sampled from another session on purpose: the process cannot read its own peak on this
# build, and an external sampler sees the same working set Task Manager would show.
$peak = 0
$deadline = (Get-Date).AddMinutes($MaxMinutes)
while ((Get-Date) -lt $deadline) {
    $procs = Get-Process python -ErrorAction SilentlyContinue
    if (-not $procs) { break }
    foreach ($proc in $procs) {
        if ($proc.WorkingSet64 -gt $peak) { $peak = $proc.WorkingSet64 }
    }
    [System.IO.File]::WriteAllText($Out, ([string][math]::Round($peak / 1MB)))
    Start-Sleep -Milliseconds $IntervalMs
}
[System.IO.File]::WriteAllText($Out, ('peak_mb=' + [math]::Round($peak / 1MB)))
