# Get current directory
$currentDir = (Get-Location).Path

# --- Check PyInstaller availability ---
pyinstaller --version *> $null

if ($LASTEXITCODE -eq 0) {
    pyinstaller `
        --noconfirm `
        --onedir `
        --windowed `
        --icon "$currentDir\src\tiny_redirect\static\img\icon.ico" `
        --name "TinyRedirect" `
        --add-data "$currentDir\src\tiny_redirect\static;static/" `
        --add-data "$currentDir\src\tiny_redirect\views;views/" `
        "$currentDir\src\tiny_redirect\app.py"
} else {
    Write-Host "PyInstaller is NOT callable or recognized."
    Write-Host "Please ensure PyInstaller is installed and its path is in your system's PATH environment variable, or activate the correct virtual environment."
    exit 1
}

# --- Check makensis availability ---
makensis /version *> $null

if ($LASTEXITCODE -eq 0) {
    makensis.exe "$currentDir\installer.nsi"
} else {
    Write-Host "makensis is NOT callable or recognized."
    Write-Host "Please ensure makensis is installed and its path is in your system's PATH environment variable."
    exit 1
}

