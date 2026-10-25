$ErrorActionPreference = 'Stop'
$appDirectory = Split-Path -Parent $PSScriptRoot
$compiler = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
$outputPath = Join-Path $appDirectory 'EchoCue.exe'
$iconPath = Join-Path $appDirectory 'app/assets/echocue.ico'
$version = (Get-Content -LiteralPath (Join-Path $appDirectory 'VERSION') -Raw).Trim()
if ($version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9]+)*$') { throw 'Invalid release version.' }
$assemblyVersion = (($version -split '[.-]') | Select-Object -First 3) -join '.'
$versionSource = Join-Path ([System.IO.Path]::GetTempPath()) ('EchoCue-Version-' + [guid]::NewGuid().ToString('N') + '.cs')
try {
    @"
[assembly: System.Reflection.AssemblyVersion("$assemblyVersion")]
[assembly: System.Reflection.AssemblyFileVersion("$assemblyVersion")]
[assembly: System.Reflection.AssemblyInformationalVersion("$version")]
"@ | Set-Content -LiteralPath $versionSource -Encoding UTF8
    & $compiler /nologo /codepage:65001 /target:winexe /optimize+ /reference:System.Windows.Forms.dll "/win32icon:$iconPath" "/out:$outputPath" (Join-Path $PSScriptRoot 'Launcher.cs') $versionSource
    if ($LASTEXITCODE -ne 0) { throw 'EXE compilation failed.' }
} finally {
    Remove-Item -LiteralPath $versionSource -ErrorAction SilentlyContinue
}
Write-Output $outputPath
