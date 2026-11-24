; Instalador de Antivirus Hogar PC (Inno Setup 6) — Carril E.
;
; Compilar (tras PyInstaller, ver Construir-en-Windows.bat):
;   ISCC.exe packaging\instalador.iss
; Produce: dist-instalador\Instalador-AntivirusHogarPC-1.0.6.exe
;
; La app se instala por máquina en Archivos de programa: escribir el hosts,
; crear la tarea semanal y tocar Defender exigen administrador, y la propia
; app pide elevación (UAC) solo para esas acciones concretas.
; El instalador NO va firmado: Windows mostrará el aviso de SmartScreen
; («Windows protegió su PC») la primera vez; ver LEEME.md.

#define AppNombre "Antivirus Hogar PC"
#define AppVersion "1.0.6"
#define AppEditor "Antivirus Hogar (proyecto familiar)"
#define AppExe "AntivirusHogarPC.exe"

[Setup]
AppId={{7E2A6B10-9C4D-4E51-A3F8-2B6D0E5A1C90}
AppName={#AppNombre}
AppVersion={#AppVersion}
AppPublisher={#AppEditor}
DefaultDirName={autopf}\Antivirus Hogar PC
DefaultGroupName={#AppNombre}
DisableProgramGroupPage=yes
OutputDir=..\dist-instalador
OutputBaseFilename=Instalador-AntivirusHogarPC-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#AppNombre}
; Icono del instalador y del desinstalador (v1.0.5): el espartano del
; usuario. Los accesos directos toman el icono del propio .exe.
SetupIconFile=icono.ico
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un icono en el &escritorio"; GroupDescription: "Iconos adicionales:"

[InstallDelete]
; v1.0.6 (nota del usuario): al actualizar ENCIMA, los accesos
; directos viejos se BORRAN antes de recrearlos. Sin esto, el
; acceso del escritorio/menú puede seguir enseñando el icono
; anterior (Windows lo sirve de su caché para esa ruta) aunque el
; .exe ya lleve el espartano: en su PC la 1.0.5 «no trajo» el icono.
Type: files; Name: "{autodesktop}\{#AppNombre}.lnk"
Type: files; Name: "{group}\{#AppNombre}.lnk"
Type: files; Name: "{group}\Desinstalar {#AppNombre}.lnk"

[Files]
; Salida --onedir de PyInstaller (dist\AntivirusHogarPC\*)
Source: "..\dist\AntivirusHogarPC\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; El .ico del espartano como archivo propio: los accesos directos
; apuntan a ÉL (no a la caché del recurso del .exe).
Source: "icono.ico"; DestDir: "{app}"; Flags: ignoreversion
; smartctl.exe (smartmontools) para la lectura SMART: SOLO si el paquete
; está presente en packaging\smartctl\ al compilar el instalador.
#if FileExists("smartctl\smartctl.exe")
Source: "smartctl\smartctl.exe"; DestDir: "{app}"; Flags: ignoreversion
#endif
#if FileExists("smartctl\smartd.exe")
Source: "smartctl\smartd.exe"; DestDir: "{app}"; Flags: ignoreversion
#endif

[Icons]
Name: "{group}\{#AppNombre}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\icono.ico"
Name: "{group}\Desinstalar {#AppNombre}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppNombre}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\icono.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir {#AppNombre} ahora"; Flags: nowait postinstall skipifsilent

[Code]
// v1.0.6: al terminar de instalar se avisa a Windows de que las
// asociaciones/iconos cambiaron (SHChangeNotify) para que el
// Explorador refresque su caché de iconos y enseñe el espartano
// sin esperar a un reinicio.
procedure SHChangeNotify(wEventId: Cardinal; uFlags: Cardinal;
  dwItem1: Cardinal; dwItem2: Cardinal);
  external 'SHChangeNotify@shell32.dll stdcall';

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    SHChangeNotify($08000000, $0000, 0, 0); { SHCNE_ASSOCCHANGED }
end;

[UninstallDelete]
; Solo lo generado dentro de la carpeta de instalación; los datos del
; usuario (%LOCALAPPDATA%\AntivirusHogarPC: caché, cuarentena, informes)
; se conservan a propósito para no borrar cuarentenas sin preguntar.
Type: filesandordirs; Name: "{app}\_internal\__pycache__"
