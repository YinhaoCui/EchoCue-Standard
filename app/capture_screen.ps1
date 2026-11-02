$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class ScreenShotDpi {
 [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr value);
}
'@
[void][ScreenShotDpi]::SetProcessDpiAwarenessContext([IntPtr](-4))
$bounds = [System.Windows.Forms.Screen]::FromPoint([System.Windows.Forms.Cursor]::Position).Bounds
$bitmap = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
try {
 $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
 try { $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size) }
 finally { $graphics.Dispose() }
 $stream = New-Object System.IO.MemoryStream
 try {
  $bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
  [Console]::Out.Write([Convert]::ToBase64String($stream.ToArray()))
 } finally { $stream.Dispose() }
} finally { $bitmap.Dispose() }
