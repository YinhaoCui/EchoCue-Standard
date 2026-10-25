# Build the geometric application mark at every native Windows icon size.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$assetDirectory = Join-Path (Split-Path -Parent $PSScriptRoot) 'app/assets'
New-Item -ItemType Directory -Path $assetDirectory -Force | Out-Null
$sizes = @(16, 20, 24, 32, 40, 48, 64, 128, 256)
$images = @()
foreach ($size in $sizes) {
    $bitmap = New-Object System.Drawing.Bitmap ($size * 4), ($size * 4)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = 'AntiAlias'
    $graphics.Clear([System.Drawing.Color]::Transparent)
    $graphics.ScaleTransform(($size * 4 / 256), ($size * 4 / 256))
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $path.AddArc(8, 8, 104, 104, 180, 90)
    $path.AddArc(144, 8, 104, 104, 270, 90)
    $path.AddArc(144, 144, 104, 104, 0, 90)
    $path.AddArc(8, 144, 104, 104, 90, 90)
    $path.CloseFigure()
    $brush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(22, 121, 247))
    $graphics.FillPath($brush, $path)
    $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::White), 16
    $pen.StartCap = 'Round'; $pen.EndCap = 'Round'
    foreach ($bar in @(@(64,108,148), @(96,80,176), @(128,60,196), @(160,88,168), @(192,112,144))) {
        $graphics.DrawLine($pen, $bar[0], $bar[1], $bar[0], $bar[2])
    }
    $output = New-Object System.Drawing.Bitmap $size, $size
    $resampler = [System.Drawing.Graphics]::FromImage($output)
    $resampler.InterpolationMode = 'HighQualityBicubic'
    $resampler.CompositingQuality = 'HighQuality'
    $resampler.DrawImage($bitmap, 0, 0, $size, $size)
    $stream = New-Object System.IO.MemoryStream
    $output.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
    $images += ,($stream.ToArray())
    if ($size -eq 256) { $output.Save((Join-Path $assetDirectory 'echocue.png'), [System.Drawing.Imaging.ImageFormat]::Png) }
    $stream.Dispose(); $resampler.Dispose(); $output.Dispose()
    $pen.Dispose(); $brush.Dispose(); $path.Dispose(); $graphics.Dispose(); $bitmap.Dispose()
}
$file = [System.IO.File]::Create((Join-Path $assetDirectory 'echocue.ico'))
$writer = New-Object System.IO.BinaryWriter $file
try {
    $writer.Write([uint16]0); $writer.Write([uint16]1); $writer.Write([uint16]$sizes.Count)
    $offset = 6 + 16 * $sizes.Count
    for ($i = 0; $i -lt $sizes.Count; $i++) {
        $dimension = if ($sizes[$i] -eq 256) { 0 } else { $sizes[$i] }
        $writer.Write([byte]$dimension); $writer.Write([byte]$dimension)
        $writer.Write([byte]0); $writer.Write([byte]0)
        $writer.Write([uint16]1); $writer.Write([uint16]32)
        $writer.Write([uint32]$images[$i].Length); $writer.Write([uint32]$offset)
        $offset += $images[$i].Length
    }
    foreach ($image in $images) { $writer.Write([byte[]]$image) }
} finally { $writer.Dispose(); $file.Dispose() }
Write-Output "Created multi-resolution application icon."
