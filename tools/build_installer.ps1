param([string]$CompilerPath, [string]$OutputFolder)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$version = (Get-Content -LiteralPath (Join-Path $projectRoot 'VERSION') -Raw).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw 'Installer requires a three-part version.' }
$standard = (Test-Path -LiteralPath (Join-Path $projectRoot 'EDITION')) -and ((Get-Content -LiteralPath (Join-Path $projectRoot 'EDITION') -Raw).Trim() -eq 'standard')
$packageName = if ($standard) { 'EchoCue-Standard' } else { 'EchoCue' }
$productName = if ($standard) { 'EchoCue Standard' } else { 'EchoCue' }
$productId = if ($standard) { 'F9F9346D-93F0-465A-8812-66514C6876D6' } else { '5F021B01-4F3C-47A3-BBC8-A0C922C52E45' }
if (-not $OutputFolder) { $OutputFolder = Join-Path $projectRoot 'dist' }
$release = Join-Path $OutputFolder "$packageName-$version-windows-x64"
if (-not (Test-Path -LiteralPath (Join-Path $release 'EchoCue.exe'))) { throw 'Build the portable package first.' }
if (-not $CompilerPath) {
    $candidates = @((Join-Path $projectRoot 'work/inno-setup/ISCC.exe'),
        "${env:ProgramFiles(x86)}/Inno Setup 6/ISCC.exe", "$env:LOCALAPPDATA/Programs/Inno Setup 6/ISCC.exe")
    $CompilerPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $CompilerPath) { throw 'Install Inno Setup 6, or pass -CompilerPath.' }
$prerequisites = Join-Path $projectRoot 'work/installer-prerequisites'
New-Item -ItemType Directory -Path $prerequisites -Force | Out-Null
$bootstrapper = Join-Path $prerequisites 'MicrosoftEdgeWebview2Setup.exe'
if (-not (Test-Path -LiteralPath $bootstrapper)) {
    Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $bootstrapper
}
$signature = Get-AuthenticodeSignature -LiteralPath $bootstrapper
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
    throw 'WebView2 bootstrapper signature is not a valid Microsoft signature.'
}
& $CompilerPath "/DAppVersion=$version" "/DReleaseDir=$release" "/DBootstrapper=$bootstrapper" "/DProductName=$productName" "/DProductId=$productId" "/DPackageName=$packageName" "/DOutputFolder=$OutputFolder" (Join-Path $PSScriptRoot 'installer.iss')
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }
$installer = Join-Path $OutputFolder "$packageName-$version-Setup-x64.exe"
$digest = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
"$digest  $([IO.Path]::GetFileName($installer))" | Set-Content -LiteralPath "$installer.sha256" -Encoding ascii
Write-Output $installer
