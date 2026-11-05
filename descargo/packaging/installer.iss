; Instalador de DescarGO para Windows (Inno Setup 6)
; Compilación:  iscc packaging\installer.iss

#define AppName "DescarGO"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppPublisher "lliuya.pe"
#define AppURL "https://lliuya.pe"

[Setup]
AppId={{6B1F3C2E-6A8D-4F1B-9C7E-3D2A5E8F0B41}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppCopyright=© 2026 lliuya.pe. Todos los derechos reservados.
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=DescarGO-Setup-{#AppVersion}
SetupIconFile=..\descargo\assets\descargo.ico
UninstallDisplayIcon={app}\DescarGO.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\DescarGO\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\DescarGO.exe"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\DescarGO.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\DescarGO.exe"; Description: "Abrir {#AppName}"; Flags: nowait postinstall skipifsilent
