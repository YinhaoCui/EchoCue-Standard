param([long]$WindowHandle, [uint32]$WindowProcess)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class WindowShot {
 [StructLayout(LayoutKind.Sequential)] public struct Rect { public int L,T,R,B; }
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out Rect r);
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
 [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr value);
}
'@
[void][WindowShot]::SetProcessDpiAwarenessContext([IntPtr](-4))
$handle = [IntPtr]$WindowHandle
[uint32]$actualProcess = 0
[void][WindowShot]::GetWindowThreadProcessId($handle, [ref]$actualProcess)
if ($actualProcess -ne $WindowProcess -or -not [WindowShot]::IsWindowVisible($handle) -or [WindowShot]::IsIconic($handle)) { throw 'Window unavailable or minimized' }
$rect = New-Object WindowShot+Rect
if (-not [WindowShot]::GetWindowRect($handle, [ref]$rect)) { throw 'Cannot read window bounds' }
$width = $rect.R - $rect.L; $height = $rect.B - $rect.T
if ($width -le 0 -or $height -le 0) { throw 'Invalid window size' }
$bitmap = New-Object System.Drawing.Bitmap($width, $height)
try {
 $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
 try {
  $dc = $graphics.GetHdc()
  try { $ok = [WindowShot]::PrintWindow($handle, $dc, 2) }
  finally { $graphics.ReleaseHdc($dc) }
 } finally { $graphics.Dispose() }
 if (-not $ok) { throw 'Window does not support capture' }
 $stream = New-Object System.IO.MemoryStream
 try {
  $bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
  [Console]::Out.Write([Convert]::ToBase64String($stream.ToArray()))
 } finally { $stream.Dispose() }
} finally { $bitmap.Dispose() }
