$ErrorActionPreference = "Continue"
$logFile = "E:\新创意构思\OpenClass\build_log.txt"
$specFile = "E:\新创意构思\OpenClass\OpenClass.spec"

Write-Host "Starting PyInstaller build..." 
"D:\pyhon\python.exe" -m PyInstaller $specFile --noconfirm --log-level=ERROR *>&1 | Tee-Object -FilePath $logFile

Write-Host "Build exit code: $LASTEXITCODE"
if (Test-Path "dist\OpenClass.exe") {
    $size = [math]::Round((Get-Item "dist\OpenClass.exe").Length / 1MB, 1)
    Write-Host "SUCCESS: dist\OpenClass.exe ($size MB)"
} else {
    Write-Host "FAIL: exe not found"
}
