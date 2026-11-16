param([string]$Csv = 'C:\Users\23R\fb-bench\size-250000-1\auth.log.csv',
      [string]$Out = 'C:\Users\23R\fb-bench\tle_look.json', [int]$Limit = 300)
# Capture the application window only. Never the screen: that desktop belongs to its user,
# and a full-screen grab once captured his game instead of the tool under test.
$exe = 'C:\Users\23R\TimelineExplorer\TimelineExplorer\TimelineExplorer.exe'
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public class WL {
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint f);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  public static string Text(IntPtr h) { var s = new StringBuilder(512); GetWindowTextW(h, s, 512); return s.ToString(); }
}
'@

Get-Process TimelineExplorer -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 2
$started = Get-Date
$proc = Start-Process -FilePath $exe -ArgumentList ('"' + $Csv + '"') -PassThru
$deadline = $started.AddSeconds($Limit)
$lastCpu = 0.0; $idle = 0
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 500
    if ($proc.HasExited) { break }
    $proc.Refresh()
    $cpu = $proc.TotalProcessorTime.TotalSeconds
    if ($cpu -gt $lastCpu + 0.05) { $idle = 0 } else { $idle++ }
    $lastCpu = $cpu
    if ($idle -ge 10) { break }
}
$loadSeconds = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)
Start-Sleep 2

$targets = New-Object System.Collections.ArrayList
$cb = [WL+EnumProc]{ param($h, $p)
    $owner = 0; [void][WL]::GetWindowThreadProcessId([IntPtr]$h, [ref]$owner)
    if ($owner -eq $proc.Id -and [WL]::IsWindowVisible([IntPtr]$h)) {
        $r = New-Object WL+RECT; [void][WL]::GetWindowRect([IntPtr]$h, [ref]$r)
        $w = $r.Right-$r.Left; $hgt = $r.Bottom-$r.Top
        if ($w -gt 200 -and $hgt -gt 200) {
            [void]$targets.Add([pscustomobject]@{ H=[IntPtr]$h; Title=[WL]::Text([IntPtr]$h); W=$w; Hh=$hgt; X=$r.Left; Y=$r.Top })
        }
    }
    return $true }
[void][WL]::EnumWindows($cb, [IntPtr]::Zero)

$shots = @()
$ordered = $targets | Sort-Object { $_.W * $_.Hh } -Descending
$index = 0
foreach ($t in $ordered) {
    $index++
    $path = ($Out -replace '\.json$', '') + "_$index.png"
    $ok = $false
    try {
        $bmp = New-Object System.Drawing.Bitmap $t.W, $t.Hh
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $hdc = $g.GetHdc()
        $ok = [WL]::PrintWindow($t.H, $hdc, 2)
        if (-not $ok) { [void][WL]::SendMessage($t.H, 0x0317, $hdc, [IntPtr]0x1E) }  # WM_PRINT, PRF_CLIENT|CHILDREN|OWNED
        $g.ReleaseHdc($hdc)
        $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
        $g.Dispose(); $bmp.Dispose()
    } catch { $ok = $_.Exception.Message }
    $shots += [ordered]@{ index=$index; title=$t.Title; w=$t.W; h=$t.Hh; x=$t.X; y=$t.Y; png=$path; printwindow=$ok }
}

[ordered]@{
    csv = $Csv
    load_seconds = $loadSeconds
    windows = $shots
} | ConvertTo-Json -Depth 5 | Set-Content -Path $Out -Encoding UTF8
Get-Process TimelineExplorer -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
