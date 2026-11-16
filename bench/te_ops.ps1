param([string]$Csv = 'C:\Users\23R\fb-bench\size-250000-1\auth.log.csv',
      [string]$Tag = 'size-250000',
      [string]$Out = '', [int]$Limit = 900)
# Timeline Explorer has no automation tree and its search box is a ToolStrip item, so the
# only way in is the foreground window: click, type, wait for the CPU to go quiet, capture.
# Every step re-checks that Timeline Explorer really owns the foreground first; a stray
# window (a browser, a user click) silently eats the keystrokes otherwise.
if (-not $Out) { $Out = "C:\Users\23R\fb-bench\tleops_$Tag.json" }
$exe = 'C:\Users\23R\TimelineExplorer\TimelineExplorer\TimelineExplorer.exe'
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public class WO {
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint f);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr SetActiveWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  public static string Text(IntPtr h) { var s = new StringBuilder(512); GetWindowTextW(h, s, 512); return s.ToString(); }
  public const uint DOWN = 0x0002, UP = 0x0004;
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

$script:main = [IntPtr]::Zero
$cb = [WO+EnumProc]{ param($h, $p)
    $owner = 0; [void][WO]::GetWindowThreadProcessId([IntPtr]$h, [ref]$owner)
    if ($owner -eq $proc.Id -and [WO]::IsWindowVisible([IntPtr]$h) -and [WO]::Text([IntPtr]$h) -like 'Timeline Explorer*') { $script:main = [IntPtr]$h }
    return $true }
[void][WO]::EnumWindows($cb, [IntPtr]::Zero)
if ($script:main -eq [IntPtr]::Zero) { '{"state":"no-window"}' | Set-Content $Out -Encoding UTF8; exit 1 }
$r = New-Object WO+RECT; [void][WO]::GetWindowRect($script:main, [ref]$r)
$W = $r.Right - $r.Left; $H = $r.Bottom - $r.Top

function Get-Point([double]$fx, [double]$fy) { @([int]($r.Left + $W * $fx), [int]($r.Top + $H * $fy)) }

function Assert-Foreground {
    for ($i = 0; $i -lt 6; $i++) {
        if ([WO]::GetForegroundWindow() -eq $script:main) { return $true }
        $fg = [WO]::GetForegroundWindow()
        $fgThread = [WO]::GetWindowThreadProcessId($fg, [IntPtr]::Zero)
        $me = [WO]::GetCurrentThreadId()
        [void][WO]::AttachThreadInput($me, $fgThread, $true)
        [void][WO]::BringWindowToTop($script:main)
        [void][WO]::SetForegroundWindow($script:main)
        [void][WO]::SetActiveWindow($script:main)
        [void][WO]::AttachThreadInput($me, $fgThread, $false)
        Start-Sleep -Milliseconds 400
    }
    return ([WO]::GetForegroundWindow() -eq $script:main)
}

function Invoke-Click([double]$fx, [double]$fy) {
    $p = Get-Point $fx $fy
    [void][WO]::SetCursorPos($p[0], $p[1]); Start-Sleep -Milliseconds 150
    [WO]::mouse_event([WO]::DOWN, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 70
    [WO]::mouse_event([WO]::UP, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 200
}

function Invoke-Drag([double]$fx1, [double]$fy1, [double]$fx2, [double]$fy2) {
    $a = Get-Point $fx1 $fy1; $b = Get-Point $fx2 $fy2
    [void][WO]::SetCursorPos($a[0], $a[1]); Start-Sleep -Milliseconds 250
    [WO]::mouse_event([WO]::DOWN, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 300
    for ($i = 1; $i -le 15; $i++) {
        $x = [int]($a[0] + ($b[0] - $a[0]) * $i / 15); $y = [int]($a[1] + ($b[1] - $a[1]) * $i / 15)
        [void][WO]::SetCursorPos($x, $y); Start-Sleep -Milliseconds 70
    }
    Start-Sleep -Milliseconds 250
    [WO]::mouse_event([WO]::UP, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 250
}

function Wait-Quiet([int]$Quiet = 8) {
    $last = $proc.TotalProcessorTime.TotalSeconds; $still = 0; $t0 = Get-Date
    while (((Get-Date) - $t0).TotalSeconds -lt 240) {
        Start-Sleep -Milliseconds 250
        if ($proc.HasExited) { break }
        $proc.Refresh()
        $cpu = $proc.TotalProcessorTime.TotalSeconds
        if ($cpu -gt $last + 0.05) { $still = 0 } else { $still++ }
        $last = $cpu
        if ($still -ge $Quiet) { break }
    }
    $elapsed = ((Get-Date) - $t0).TotalSeconds - ($Quiet * 0.25)
    if ($elapsed -lt 0) { $elapsed = 0 }
    return [math]::Round($elapsed, 2)
}

function Save-Shot([string]$name) {
    $path = ($Out -replace '\.json$', '') + "_$name.png"
    $bmp = New-Object System.Drawing.Bitmap $W, $H
    $g = [System.Drawing.Graphics]::FromImage($bmp); $hdc = $g.GetHdc()
    [void][WO]::PrintWindow($script:main, $hdc, 2); $g.ReleaseHdc($hdc)
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()
    return $path
}

function Invoke-Search([string]$text) {
    if (-not (Assert-Foreground)) { throw 'foreground lost before search' }
    Invoke-Click 0.863 0.130
    [System.Windows.Forms.SendKeys]::SendWait('^a')
    if ($text) { [System.Windows.Forms.SendKeys]::SendWait($text) }
    Start-Sleep -Milliseconds 250
    [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
}

$steps = New-Object System.Collections.ArrayList
$failed = $null
try {
    Invoke-Search 'session'
    [void]$steps.Add([ordered]@{ step = 'search_session_all_rows'; seconds = (Wait-Quiet); png = (Save-Shot 'search_session') })

    Invoke-Search 'host07'
    [void]$steps.Add([ordered]@{ step = 'search_host07'; seconds = (Wait-Quiet); png = (Save-Shot 'search_host07') })

    Invoke-Search 'error'
    [void]$steps.Add([ordered]@{ step = 'search_error_none'; seconds = (Wait-Quiet); png = (Save-Shot 'search_error') })

    # An empty search does not remove the filter in this build: it leaves the previous
    # one in place. A term every row carries brings the whole file back, and the capture
    # proves it (Visible lines back to Total lines).
    Invoke-Search 'message'
    [void]$steps.Add([ordered]@{ step = 'search_message_all_rows'; seconds = (Wait-Quiet); png = (Save-Shot 'search_message') })

    if (-not (Assert-Foreground)) { throw 'foreground lost before sort' }
    Invoke-Click 0.157 0.175
    [void]$steps.Add([ordered]@{ step = 'sort_timestamp'; seconds = (Wait-Quiet); png = (Save-Shot 'sort_timestamp') })

    if (-not (Assert-Foreground)) { throw 'foreground lost before sort_host' }
    Invoke-Click 0.277 0.175
    [void]$steps.Add([ordered]@{ step = 'sort_host'; seconds = (Wait-Quiet); png = (Save-Shot 'sort_host') })

    if (-not (Assert-Foreground)) { throw 'foreground lost before group' }
    Invoke-Drag 0.277 0.175 0.471 0.130
    [void]$steps.Add([ordered]@{ step = 'group_by_host'; seconds = (Wait-Quiet 14); png = (Save-Shot 'group_host') })
} catch { $failed = $_.Exception.Message }

[ordered]@{
    csv = $Csv
    tag = $Tag
    load_seconds = $loadSeconds
    window = @{ x = $r.Left; y = $r.Top; w = $W; h = $H }
    steps = @($steps)
    failed = $failed
} | ConvertTo-Json -Depth 5 | Set-Content -Path $Out -Encoding UTF8
Start-Sleep 1
Get-Process TimelineExplorer -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
