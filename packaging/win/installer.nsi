; TinyRedirect NSIS Installer Script
; Requires NSIS 3.x

;--------------------------------
; Includes
!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

;--------------------------------
; General

; Name and output file
Name "TinyRedirect"
OutFile "TinyRedirect-Setup.exe"
Unicode True

; Default installation directory
InstallDir "$PROGRAMFILES\TinyRedirect"

; Request application privileges for Windows Vista+
RequestExecutionLevel admin

; Installer attributes
!define PRODUCT_NAME "TinyRedirect"
!define PRODUCT_VERSION "1.0.0"
!define PRODUCT_PUBLISHER "TinyRedirect"
!define PRODUCT_WEB_SITE "https://sethstenzel.me/portfolio/tinyredirect/"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"

;--------------------------------
; Interface Settings
!define MUI_ABORTWARNING
!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\modern-install.ico"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\modern-uninstall.ico"

;--------------------------------
; Pages

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

;--------------------------------
; Languages
!insertmacro MUI_LANGUAGE "English"

;--------------------------------
; Installer Sections

Section "TinyRedirect" SecMain
    SectionIn RO

    ; Set output path to the installation directory
    SetOutPath "$INSTDIR"

    ; Copy all files from the PyInstaller output
    File /r "output\TinyRedirect\*.*"

    ; Create uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; Create Start Menu shortcuts
    CreateDirectory "$SMPROGRAMS\TinyRedirect"
    CreateShortCut "$SMPROGRAMS\TinyRedirect\TinyRedirect.lnk" "$INSTDIR\TinyRedirect.exe"
    CreateShortCut "$SMPROGRAMS\TinyRedirect\Uninstall.lnk" "$INSTDIR\Uninstall.exe"

    ; Create Desktop shortcut
    CreateShortCut "$DESKTOP\TinyRedirect.lnk" "$INSTDIR\TinyRedirect.exe"

    ; Write registry keys for uninstaller
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayName" "${PRODUCT_NAME}"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\TinyRedirect.exe"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"

    ; Get installed size
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "EstimatedSize" "$0"

    ; Ask user if they want to start on Windows startup
    MessageBox MB_YESNO|MB_ICONQUESTION "Would you like TinyRedirect to start automatically when Windows starts?" IDNO SkipStartup

    ; Add to Windows startup (run on login with --startup flag)
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "TinyRedirect" '"$INSTDIR\TinyRedirect.exe" --startup'

    SkipStartup:

    ; Update hosts file to add 'r' pointing to 127.0.0.1
    Call UpdateHostsFile

SectionEnd

;--------------------------------
; Functions

Function UpdateHostsFile
    ; Path to Windows hosts file
    StrCpy $0 "$WINDIR\System32\drivers\etc\hosts"

    ; Check if hosts file exists
    IfFileExists $0 0 HostsNotFound

    ; Read the hosts file to check if 'r' entry already exists
    FileOpen $1 $0 r
    StrCpy $2 "" ; Will hold the file contents
    StrCpy $3 "0" ; Flag: 0 = not found, 1 = found

    ReadHostsLoop:
        FileRead $1 $4
        IfErrors DoneReading

        ; Check if this line contains the 'r' host entry
        ; We look for "127.0.0.1" followed by whitespace and "r"
        Push $4
        Push "127.0.0.1"
        Call StrContains
        Pop $5

        ${If} $5 != ""
            ; Line contains 127.0.0.1, check if it has 'r' as hostname
            Push $4
            Call CheckForRHost
            Pop $6
            ${If} $6 == "1"
                StrCpy $3 "1" ; Found existing entry
            ${EndIf}
        ${EndIf}

        ; Append line to contents
        StrCpy $2 "$2$4"
        Goto ReadHostsLoop

    DoneReading:
    FileClose $1

    ; If 'r' entry not found, add it
    ${If} $3 == "0"
        ; Append the new entry
        FileOpen $1 $0 a
        FileSeek $1 0 END

        ; Add newline if file doesn't end with one
        FileWrite $1 "$\r$\n"
        FileWrite $1 "127.0.0.1	r$\r$\n"
        FileClose $1

        ; Show message to user
        MessageBox MB_ICONINFORMATION|MB_OK "Added 'r' hostname to Windows hosts file (127.0.0.1	r).$\r$\n$\r$\nYou can now use http://r:port/ to access TinyRedirect."
    ${Else}
        ; Entry already exists
        MessageBox MB_ICONINFORMATION|MB_OK "The 'r' hostname already exists in your Windows hosts file."
    ${EndIf}

    Goto HostsDone

    HostsNotFound:
        MessageBox MB_ICONEXCLAMATION|MB_OK "Warning: Could not find Windows hosts file.$\r$\n$\r$\nYou may need to manually add the following entry to your hosts file:$\r$\n127.0.0.1	r"

    HostsDone:
FunctionEnd

; Helper function to check if a string contains a substring
Function StrContains
    Exch $1 ; substring
    Exch
    Exch $0 ; string
    Push $2
    Push $3
    Push $4

    StrLen $2 $0
    StrLen $3 $1
    ${If} $3 > $2
        StrCpy $0 ""
        Goto StrContainsDone
    ${EndIf}

    IntOp $2 $2 - $3
    IntOp $2 $2 + 1

    StrCpy $4 0
    StrContainsLoop:
        ${If} $4 >= $2
            StrCpy $0 ""
            Goto StrContainsDone
        ${EndIf}

        StrCpy $0 $0 $3 $4
        ${If} $0 == $1
            ; Found
            Goto StrContainsDone
        ${EndIf}

        ; Reset $0 and try next position
        Exch $0
        Exch
        Exch $0

        IntOp $4 $4 + 1
        Goto StrContainsLoop

    StrContainsDone:
    Pop $4
    Pop $3
    Pop $2
    Pop $1
    Exch $0
FunctionEnd

; Check if a line has 'r' as a hostname (after 127.0.0.1)
Function CheckForRHost
    Exch $0 ; line to check
    Push $1
    Push $2

    ; Simple check: look for tab or space followed by 'r' followed by space/tab/newline/end
    ; This is a simplified check - matches common patterns

    ; Check for "	r" (tab + r)
    Push $0
    Push "	r"
    Call StrContains
    Pop $1
    ${If} $1 != ""
        StrCpy $0 "1"
        Goto CheckForRHostDone
    ${EndIf}

    ; Check for " r" (space + r)
    Push $0
    Push " r"
    Call StrContains
    Pop $1
    ${If} $1 != ""
        StrCpy $0 "1"
        Goto CheckForRHostDone
    ${EndIf}

    StrCpy $0 "0"

    CheckForRHostDone:
    Pop $2
    Pop $1
    Exch $0
FunctionEnd

;--------------------------------
; Uninstaller Section

Section "Uninstall"

    ; Remove Start Menu shortcuts
    Delete "$SMPROGRAMS\TinyRedirect\TinyRedirect.lnk"
    Delete "$SMPROGRAMS\TinyRedirect\Uninstall.lnk"
    RMDir "$SMPROGRAMS\TinyRedirect"

    ; Remove Desktop shortcut
    Delete "$DESKTOP\TinyRedirect.lnk"

    ; Remove installation directory and all contents
    RMDir /r "$INSTDIR"

    ; Remove registry keys
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"

    ; Remove startup registry entry
    DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "TinyRedirect"

    ; Note: We don't remove the hosts file entry during uninstall
    ; as it might be used by other applications or the user might want to keep it
    MessageBox MB_YESNO|MB_ICONQUESTION "Do you want to remove the 'r' entry from your Windows hosts file?" IDNO SkipHostsRemoval

    ; Remove 'r' from hosts file
    Call un.RemoveFromHostsFile

    SkipHostsRemoval:

SectionEnd

; Uninstaller function to remove 'r' from hosts file
Function un.RemoveFromHostsFile
    StrCpy $0 "$WINDIR\System32\drivers\etc\hosts"

    IfFileExists $0 0 un.HostsNotFound

    ; Read all lines except the 'r' entry
    FileOpen $1 $0 r
    StrCpy $2 "" ; New file contents

    un.ReadLoop:
        FileRead $1 $3
        IfErrors un.DoneReading

        ; Check if this line is the 'r' entry we added
        Push $3
        Push "127.0.0.1"
        Call un.StrContains
        Pop $4

        ${If} $4 != ""
            Push $3
            Call un.CheckForRHost
            Pop $5
            ${If} $5 == "1"
                ; Skip this line (don't add to new contents)
                Goto un.ReadLoop
            ${EndIf}
        ${EndIf}

        ; Keep this line
        StrCpy $2 "$2$3"
        Goto un.ReadLoop

    un.DoneReading:
    FileClose $1

    ; Write the new contents back
    FileOpen $1 $0 w
    FileWrite $1 $2
    FileClose $1

    MessageBox MB_ICONINFORMATION|MB_OK "Removed 'r' entry from Windows hosts file."
    Goto un.HostsDone

    un.HostsNotFound:
        MessageBox MB_ICONEXCLAMATION|MB_OK "Could not find Windows hosts file."

    un.HostsDone:
FunctionEnd

; Uninstaller version of StrContains
Function un.StrContains
    Exch $1
    Exch
    Exch $0
    Push $2
    Push $3
    Push $4

    StrLen $2 $0
    StrLen $3 $1
    ${If} $3 > $2
        StrCpy $0 ""
        Goto un.StrContainsDone
    ${EndIf}

    IntOp $2 $2 - $3
    IntOp $2 $2 + 1

    StrCpy $4 0
    un.StrContainsLoop:
        ${If} $4 >= $2
            StrCpy $0 ""
            Goto un.StrContainsDone
        ${EndIf}

        StrCpy $0 $0 $3 $4
        ${If} $0 == $1
            Goto un.StrContainsDone
        ${EndIf}

        Exch $0
        Exch
        Exch $0

        IntOp $4 $4 + 1
        Goto un.StrContainsLoop

    un.StrContainsDone:
    Pop $4
    Pop $3
    Pop $2
    Pop $1
    Exch $0
FunctionEnd

; Uninstaller version of CheckForRHost
Function un.CheckForRHost
    Exch $0
    Push $1
    Push $2

    Push $0
    Push "	r"
    Call un.StrContains
    Pop $1
    ${If} $1 != ""
        StrCpy $0 "1"
        Goto un.CheckForRHostDone
    ${EndIf}

    Push $0
    Push " r"
    Call un.StrContains
    Pop $1
    ${If} $1 != ""
        StrCpy $0 "1"
        Goto un.CheckForRHostDone
    ${EndIf}

    StrCpy $0 "0"

    un.CheckForRHostDone:
    Pop $2
    Pop $1
    Exch $0
FunctionEnd
