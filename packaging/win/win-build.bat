@echo off
set "currentDir=%CD%"

rem Attempt to run PyInstaller
pyinstaller --version >nul 2>&1

rem Check the ERRORLEVEL
if %ERRORLEVEL% equ 0 (
    pyinstaller --noconfirm --onedir --windowed --icon "%currentDir%\src\tiny_redirect\static\img\icon.ico" --name "TinyRedirect" --add-data "%currentDir%\src\tiny_redirect\static;static/" --add-data "%currentDir%\src\tiny_redirect\views;views/"  "%currentDir%\src\tiny_redirect\app.py"
) else (
    echo PyInstaller is NOT callable or recognized.
    echo Please ensure PyInstaller is installed and its path is in your system's PATH environment variable, or activate the correct virtual environment.
    goto :error_exit
)

makensis /version >nul 2>&1

if %ERRORLEVEL% equ 0 (
    makensis.exe "%currentDir%\installer.nsi"
) else (
    echo makensis is NOT callable or recognized.
    echo Please ensure makensis is installed and its path is in your system's PATH environment variable.
    goto :error_exit
)

:error_exit