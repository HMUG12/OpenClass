; ═══════════════════════════════════════════════════════════
; Inno Setup 脚本 — OpenClass 安装包
; 执行方式: iscc setup.iss
; 前置要求: 先运行 PyInstaller 打包 → dist/OpenClass.exe 已生成
; ═══════════════════════════════════════════════════════════

[Setup]
AppName=OpenClass
AppVersion=测试版
AppPublisher=未知之致
AppPublisherURL=https://github.com/HMUG12/OpenClass
AppSupportURL=https://github.com/HMUG12/OpenClass
DefaultDirName={autopf}\OpenClass
DefaultGroupName=OpenClass
UninstallDisplayIcon={app}\OpenClass.exe
Compression=lzma2
SolidCompression=yes
OutputDir=.
OutputBaseFilename=OpenClass_Setup
SetupIconFile=openclass.ico
WizardStyle=modern
DisableProgramGroupPage=no

; ── 安装文件 ──
[Files]
; 单文件打包模式（--onefile）
Source: "dist\OpenClass.exe"; DestDir: "{app}"; Flags: ignoreversion
; 将图标也复制到安装目录，供快捷方式使用
Source: "openclass.ico"; DestDir: "{app}"; Flags: ignoreversion

; ── 桌面 + 开始菜单快捷方式 ──
[Icons]
; 【核心】桌面快捷方式 — 一键启动
Name: "{commondesktop}\OpenClass"; Filename: "{app}\OpenClass.exe"; WorkingDir: "{app}"; IconFilename: "{app}\openclass.ico"
; 开始菜单 — 主程序
Name: "{group}\OpenClass"; Filename: "{app}\OpenClass.exe"; WorkingDir: "{app}"; IconFilename: "{app}\openclass.ico"
; 开始菜单 — 卸载程序
Name: "{group}\卸载 OpenClass"; Filename: "{uninstallexe}"

; ── 安装完成后可选立即运行 ──
[Run]
Filename: "{app}\OpenClass.exe"; Description: "运行 OpenClass"; Flags: postinstall nowait skipifsilent unchecked

; ── 卸载前确认 ──
[UninstallRun]
; (无需额外操作)
