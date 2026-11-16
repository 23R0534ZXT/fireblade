param([string]$Csv, [string]$Out = 'C:\Users\23R\fb-bench\tle_one.json', [int]$Limit = 900)
# Runs INSIDE the console session (scheduled task with interactive logon). A process started
# from the SSH session cannot see another session's windows: MainWindowHandle stays 0 and a
# screen capture comes back white - that is a measurement defect, not a locked desktop.
#
# The window is captured with PrintWindow, never the whole screen: this desktop belongs to
# its user and the only pixels this benchmark needs are the ones of the tool under test.
$exe = 'C:\Users\23R\TimelineExplorer\TimelineExplorer\TimelineExplorer.exe'
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class Win {
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdc, uint flags);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hwnd, int cmd);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
'@

$sizeMb = [math]::Round((Get-Item $Csv).Length / 1MB, 1)
Get-Process TimelineExplorer -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 2

$started = Get-Date
$proc = Start-Process -FilePath $exe -ArgumentList ('"' + $Csv + '"') -PassThru
$deadline = $started.AddSeconds($Limit)
$peak = 0
$lastCpu = 0.0
$idle = 0
$window = [IntPtr]::Zero
$title = ''
$state = 'timeout'

while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 250
    if ($proc.HasExited) { $state = 'exited'; break }
    $proc.Refresh()
    if ($proc.WorkingSet64 -gt $peak) { $peak = $proc.WorkingSet64 }
    if ($proc.MainWindowHandle -ne [IntPtr]::Zero) {
        $window = $proc.MainWindowHandle
        $title = $proc.MainWindowTitle
    }
    $cpu = $proc.TotalProcessorTime.TotalSeconds
    if ($cpu -gt $lastCpu + 0.05) { $idle = 0 } else { $idle++ }
    $lastCpu = $cpu
    if ($window -ne [IntPtr]::Zero -and $idle -ge 12) { $state = 'loaded'; break }
}

$elapsed = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)
$shot = $Out -replace '\.json$', '.png'
try {
    $rect = New-Object Win+RECT
    [void][Win]::GetWindowRect($window, [ref]$rect)
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    if ($width -gt 0 -and $height -gt 0) {
        $bitmap = New-Object System.Drawing.Bitmap $width, $height
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $hdc = $graphics.GetHdc()
        # PW_RENDERFULLCONTENT draws the DWM surface even when the window is behind another.
        [void][Win]::PrintWindow($window, $hdc, 2)
        $graphics.ReleaseHdc($hdc)
        $bitmap.Save($shot, [System.Drawing.Imaging.ImageFormat]::Png)
        $bitmap.Dispose()
    } else { $shot = '' }
} catch {
    $shot = ''
}

[ordered]@{
    file = $Csv
    file_mb = $sizeMb
    seconds = $elapsed
    state = $state
    window = ($window -ne [IntPtr]::Zero)
    title = $title
    peak_mb = [math]::Round($peak / 1MB, 1)
    cpu_seconds = [math]::Round($proc.TotalProcessorTime.TotalSeconds, 1)
    screenshot = $shot
    at = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
} | ConvertTo-Json | Set-Content -Path $Out -Encoding UTF8

Start-Sleep 1
Get-Process TimelineExplorer -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
