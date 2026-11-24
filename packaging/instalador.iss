; Instalador de Antivirus Hogar PC (Inno Setup 6) — Carril E.
;
; Compilar (tras PyInstaller, ver Construir-en-Windows.bat):
;   ISCC.exe packaging\instalador.iss
; Produce: dist-instalador\Instalador-AntivirusHogarPC-1.0.7.exe
;
; v1.0.7: el instalador lleva INCORPORADO SoftEther VPN Client
; (archivos oficiales en packaging\softether\client\, ver su
; LEEME.md): se copian a {app}\softether y al terminar se registra
; su servicio SEVPNCLIENT (solo si el equipo no tiene ya uno) para
; que la app lo maneje por vpncmd en segundo plano, sin que el
; usuario instale ni abra nada más.
;
; La app se instala por máquina en Archivos de programa: escribir el hosts,
; crear la tarea semanal y tocar Defender exigen administrador, y la propia
; app pide elevación (UAC) solo para esas acciones concretas.
; El instalador NO va firmado: Windows mostrará el aviso de SmartScreen
; («Windows protegió su PC») la primera vez; ver LEEME.md.

#define AppNombre "Antivirus Hogar PC"
#define AppVersion "1.0.7"
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
; SoftEther VPN Client INCORPORADO (v1.0.7): los archivos del cliente
; oficial 4.44-9807 (extraídos de su instalador; el instalador oficial
; NO tiene modo silencioso, por eso la vía es copiar los archivos y
; registrar el servicio — ver [Code]). Solo si el paquete está al
; compilar: la compilación en la nube lo descarga del sitio oficial,
; verifica tamaño y huella, lo extrae y FALLA si falta; una
; compilación local sin el paquete produce la app sin SoftEther y la
; app lo detecta (cae a la vía del perfil .ovpn).
#if FileExists("softether\client\SOFTETHER-CLIENT.txt")
Source: "softether\client\*"; DestDir: "{app}\softether"; Flags: ignoreversion recursesubdirs createallsubdirs
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

{ v1.0.7: SoftEther INCORPORADO. El instalador oficial de SoftEther
  no admite instalación silenciosa (verificado: es un instalador
  propio sin parámetros desatendidos documentados), así que la vía
  es la de su comunidad oficial: copiar los archivos del cliente y
  registrar su servicio de Windows (SEVPNCLIENT, binario
  «vpnclient_x64.exe /service»). El driver de la tarjeta virtual lo
  instala el propio cliente la primera vez que la app crea la
  tarjeta por vpncmd (NicCreate), en la sesión del usuario.
  Si el equipo YA tiene un servicio SEVPNCLIENT (SoftEther propio
  del usuario), no se toca nada. Si lo registramos nosotros, se
  deja una marca en el registro para que el desinstalador solo
  retire el servicio cuando es el incorporado. }
function SoftEtherExePath(): String;
begin
  if FileExists(ExpandConstant('{app}\softether\vpnclient_x64.exe')) then
    Result := ExpandConstant('{app}\softether\vpnclient_x64.exe')
  else if FileExists(ExpandConstant('{app}\softether\vpnclient.exe')) then
    Result := ExpandConstant('{app}\softether\vpnclient.exe')
  else
    Result := '';
end;

procedure RegistrarServicioSoftEther();
var
  ResultCode: Integer;
  Exe: String;
begin
  Exe := SoftEtherExePath();
  if Exe = '' then
    Exit;
  { ¿Ya existe el servicio? Entonces es del usuario: no se toca. }
  if Exec(ExpandConstant('{sys}\sc.exe'), 'query SEVPNCLIENT', '',
      SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0) then
    Exit;
  if Exec(ExpandConstant('{sys}\sc.exe'),
      'create SEVPNCLIENT binPath= "' + Exe + ' /service" ' +
      'DisplayName= "SoftEther VPN Client" start= auto', '',
      SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0) then
  begin
    RegWriteStringValue(HKLM, 'Software\Antivirus Hogar PC',
      'SoftEtherServicioPropio', '1');
    Exec(ExpandConstant('{sys}\sc.exe'),
      'description SEVPNCLIENT "Cliente VPN incluido con Antivirus ' +
      'Hogar PC: trabaja en segundo plano para las conexiones de ' +
      'VPN Gate."', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(ExpandConstant('{sys}\net.exe'), 'start SEVPNCLIENT', '',
      SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
  Marca: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    { Solo se retira el servicio si lo registró ESTE instalador. }
    if RegQueryStringValue(HKLM, 'Software\Antivirus Hogar PC',
        'SoftEtherServicioPropio', Marca) and (Marca = '1') then
    begin
      Exec(ExpandConstant('{sys}\net.exe'), 'stop SEVPNCLIENT', '',
        SW_HIDE, ewWaitUntilTerminated, ResultCode);
      Exec(ExpandConstant('{sys}\sc.exe'), 'delete SEVPNCLIENT', '',
        SW_HIDE, ewWaitUntilTerminated, ResultCode);
      RegDeleteValue(HKLM, 'Software\Antivirus Hogar PC',
        'SoftEtherServicioPropio');
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    SHChangeNotify($08000000, $0000, 0, 0); { SHCNE_ASSOCCHANGED }
    RegistrarServicioSoftEther();
  end;
end;

[UninstallDelete]
; Solo lo generado dentro de la carpeta de instalación; los datos del
; usuario (%LOCALAPPDATA%\AntivirusHogarPC: caché, cuarentena, informes)
; se conservan a propósito para no borrar cuarentenas sin preguntar.
Type: filesandordirs; Name: "{app}\_internal\__pycache__"
