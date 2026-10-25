# Build EchoCue Standard for Windows x64

Use Python 3.14 x64 and Inno Setup 6. Keep this edition's source in its own folder.

```powershell
python -m pip install --only-binary=:all: --no-binary=proxy_tools --target vendor -r requirements.txt
python tools/setup_streaming.py --models-only
python tools/run_tests.py
./tools/build_launcher.ps1
python tools/package_release.py
./tools/build_installer.ps1 -CompilerPath 'C:/Program Files (x86)/Inno Setup 6/ISCC.exe'
```

Optional batch transcription uses `runtime/Release/whisper-cli.exe`, its DLLs, and `runtime/ggml-base.bin`. When present, the packager includes them alongside streaming models. Local dependencies, models, generated packages and user files are excluded from Git.

The installer is `dist/EchoCue-Standard-1.0.0-Setup-x64.exe`. Its default destination is `%LOCALAPPDATA%/Programs/EchoCue Standard`. Installed data goes to `%LOCALAPPDATA%/EchoCue Standard/data`; the portable edition keeps data in `_internal/data`. Upgrades and uninstall retain installed user data. The two editions use separate application identities and can coexist. Set distinct global shortcuts if running them together.

Microsoft's signed WebView2 bootstrapper is verified during installer compilation. Installation needs internet access only if the WebView2 Runtime is missing. Installer signing requires your own code-signing certificate; the provided build does not sign the installer.
