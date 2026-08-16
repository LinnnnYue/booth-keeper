; BoothKeeper NSIS Installer Script
; Wraps dist/BoothKeeper.exe + assets into a Windows installer with shortcuts + uninstaller

Unicode True
SetCompressor /SOLID lzma

!define APP_NAME "BoothKeeper"
!define APP_DISPLAY_NAME "Booth Keeper · 展位守护者"
!define APP_VERSION "1.3.0"
!define APP_PUBLISHER "小凛酱"
!define APP_EXE "BoothKeeper.exe"
!define APP_ICON "D:\Lin_Agent\WB-WorkSpace\BoothKeeper\assets\app_icon.ico"

; R10：终结旧进程，让 BoothKeeper 运行时也能直接安装更新
; 用 tasklist + taskkill 命令（NSIS 自带 nsExec，无插件依赖）

Name "${APP_DISPLAY_NAME} ${APP_VERSION}"
OutFile "D:\Lin_Agent\WB-WorkSpace\BoothKeeper\dist\BoothKeeper_Setup_${APP_VERSION}.exe"
InstallDir "$PROGRAMFILES64\${APP_NAME}"
RequestExecutionLevel admin
ShowInstDetails show
ShowUninstDetails show

Function .onInit
  DetailPrint "正在检查 BoothKeeper 旧进程..."
  ; 用 tasklist 检查 BoothKeeper.exe（带过滤器，过滤 PID 列）
  nsExec::ExecToLog 'cmd /c tasklist /FI "IMAGENAME eq BoothKeeper.exe" /NH'
  Sleep 500
  ; 直接尝试关闭（如果不存在则 taskkill 会报错，忽略）
  nsExec::ExecToLog 'taskkill /IM "BoothKeeper.exe" /T'
  Sleep 800
  ; 检查是否还在
  nsExec::ExecToLog 'cmd /c tasklist /FI "IMAGENAME eq BoothKeeper.exe" /NH | findstr /I "BoothKeeper.exe"'
  Sleep 500
  ; 如果还在，强制关闭
  nsExec::ExecToLog 'taskkill /F /IM "BoothKeeper.exe" /T'
  Sleep 500
FunctionEnd

; Modern UI 2
!include "MUI2.nsh"
!define MUI_ABORTWARNING
!define MUI_ICON "${APP_ICON}"
!define MUI_UNICON "${APP_ICON}"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "${APP_ICON}"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "D:\Lin_Agent\WB-WorkSpace\BoothKeeper\LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "${APP_EXE}"
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\README.txt"
!define MUI_FINISHPAGE_SHOWREADME_TEXT "查看 README（包含爱发电 / 微信赞助码）"
!define MUI_FINISHPAGE_SHOWREADME_NOTCHECKED
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "SimpChinese"

Section "主程序（必需）" SEC01
    SetOutPath "$INSTDIR"
    File "D:\Lin_Agent\WB-WorkSpace\BoothKeeper\dist\${APP_EXE}"
    File "D:\Lin_Agent\WB-WorkSpace\BoothKeeper\README.md"
    File "D:\Lin_Agent\WB-WorkSpace\BoothKeeper\LICENSE.txt"
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; 开始菜单快捷方式
    CreateDirectory "$SMPROGRAMS\${APP_DISPLAY_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_DISPLAY_NAME}\${APP_DISPLAY_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
    CreateShortcut "$SMPROGRAMS\${APP_DISPLAY_NAME}\卸载.lnk" "$INSTDIR\Uninstall.exe"

    ; 桌面快捷方式
    CreateShortcut "$DESKTOP\${APP_DISPLAY_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
SectionEnd

; 注册卸载项
Section -un.SEC01
    Delete "$INSTDIR\${APP_EXE}"
    Delete "$INSTDIR\README.md"
    Delete "$INSTDIR\LICENSE.txt"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir "$INSTDIR"
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
    RMDir /r "$SMPROGRAMS\${APP_DISPLAY_NAME}"
    Delete "$DESKTOP\${APP_DISPLAY_NAME}.lnk"
SectionEnd

; 安装/卸载日志
Section "-InstallLog"
    ; 写注册表让添加/删除程序能识别
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName" "${APP_DISPLAY_NAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "Publisher" "${APP_PUBLISHER}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString" "$\"$INSTDIR\Uninstall.exe$\""
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayIcon" "$INSTDIR\${APP_EXE},0"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "InstallLocation" "$INSTDIR"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoRepair" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "EstimatedSize" 75000
SectionEnd