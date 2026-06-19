; Frame Player 설치 스크립트 (Inno Setup 6)
; 빌드: Inno Setup 설치 후 이 파일을 ISCC로 컴파일하거나 Inno Setup IDE에서 열어 Build
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\FramePlayer.iss
;
; 특징: 관리자 권한 불필요(사용자별 설치) + HKCU 파일 연결 등록

#define AppName "Frame Player"
#define AppVersion "0.1.2"
#define AppPublisher "G-Turtle"
#define AppExe "FramePlayer.exe"
#define ProgId "FramePlayer.VideoFile"

[Setup]
; AppId는 업그레이드/제거 식별용 고정 GUID (변경 금지)
AppId={{8E3A2F14-9B6C-4D5E-A1F7-2C3B4D5E6F70}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
; 관리자 권한 없이 사용자별로 설치
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\FramePlayer
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; 64비트 전용 (x64 및 x64 에뮬레이션 가능한 ARM64)
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 설치 파일 출력 위치/이름
OutputDir=..\dist
OutputBaseFilename=FramePlayer-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; 업데이트 시 실행 중인 앱을 자동으로 닫고 파일을 교체한다.
; 재시작은 아래 [Run]에서 처리하므로 RestartApplications는 끈다.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; GroupDescription: "추가 아이콘:"; Flags: unchecked

[Files]
; PyInstaller 폴더 빌드 결과물 전체 복사 (FramePlayer.exe + _internal\)
Source: "..\dist\FramePlayer\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{#AppName} 제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; --- ProgID 등록 (이 앱으로 열기) ---
Root: HKCU; Subkey: "Software\Classes\{#ProgId}"; ValueType: string; ValueData: "Frame Player 동영상"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\{#ProgId}\DefaultIcon"; ValueType: string; ValueData: "{app}\{#AppExe},0"
Root: HKCU; Subkey: "Software\Classes\{#ProgId}\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""

; --- mp4 우클릭 '연결 프로그램' 목록에 노출 ---
Root: HKCU; Subkey: "Software\Classes\.mp4\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue

; --- 기본 앱(Capabilities) 등록: Windows 설정 > 기본 앱에 표시 ---
Root: HKCU; Subkey: "Software\FramePlayer\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{#AppName}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\FramePlayer\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "프레임 단위 탐색을 지원하는 동영상 플레이어"
Root: HKCU; Subkey: "Software\FramePlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mp4"; ValueData: "{#ProgId}"
Root: HKCU; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "FramePlayer"; ValueData: "Software\FramePlayer\Capabilities"; Flags: uninsdeletevalue

[Run]
; 설치 완료 후 앱 실행.
; 일반 설치: 마법사 마지막에 체크박스로 표시.
; 무인(/SILENT) 업데이트: skipifsilent가 없으므로 자동 실행 → 앱 자동 재시작.
Filename: "{app}\{#AppExe}"; Description: "{#AppName} 실행"; Flags: nowait postinstall
