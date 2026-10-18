#ifndef AppVersion
  #define AppVersion "1.1.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\build\release\dist\EntreTerras"
#endif
#ifndef ArtifactsDir
  #define ArtifactsDir "..\dist\release"
#endif

[Setup]
AppId={{F3B26B75-1B6E-41F8-88B3-7AA9971F41DC}
AppName=Entre Terras
AppVersion={#AppVersion}
AppPublisher=SamuelASDev
AppPublisherURL=https://github.com/SamuelASDev/pythonleitorEldenRing
AppSupportURL=https://github.com/SamuelASDev/pythonleitorEldenRing/issues
AppUpdatesURL=https://github.com/SamuelASDev/pythonleitorEldenRing/releases/latest
DefaultDirName={autopf}\Entre Terras
DefaultGroupName=Entre Terras
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\EntreTerras.exe
SetupIconFile=..\entre_terras\assets\entre-terras.ico
LicenseFile=..\LICENSE
InfoBeforeFile=leia-me.txt
OutputDir={#ArtifactsDir}
OutputBaseFilename=EntreTerras-{#AppVersion}-Setup-x64
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
PrivilegesRequired=admin
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
AppMutex=Local\EntreTerras-Running
CloseApplications=no
RestartApplications=no
UninstallDisplayName=Entre Terras
VersionInfoDescription=Instalador do Entre Terras
VersionInfoCompany=SamuelASDev
VersionInfoVersion={#AppVersion}
#ifdef SignedBuild
SignTool=ReleaseSign
SignedUninstaller=yes
#endif

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Entre Terras"; Filename: "{app}\EntreTerras.exe"; Parameters: "--show"; AppUserModelID: "EntreTerras.DeathCounter.Desktop"
Name: "{autodesktop}\Entre Terras"; Filename: "{app}\EntreTerras.exe"; Parameters: "--show"; Tasks: desktopicon; AppUserModelID: "EntreTerras.DeathCounter.Desktop"
Name: "{group}\Desinstalar Entre Terras"; Filename: "{uninstallexe}"

; User data in LOCALAPPDATA is intentionally never removed by the installer.
