; Instalador de Antivirus Hogar PC (Inno Setup 6) — Carril E.
;
; Compilar (tras PyInstaller, ver Construir-en-Windows.bat):
;   ISCC.exe packaging\instalador.iss
; Produce: dist-instalador\Instalador-AntivirusHogarPC-1.0.11.exe
;
; v1.0.10: el instalador lleva INCORPORADO el instalador oficial
; de OpenVPN Community (MSI en packaging\openvpn\, ver su
; LEEME.md): se deja una copia en la carpeta «openvpn» de la app
; (el instalador interno que conserva el auto-actualizador) y, si
; el equipo no tiene ya OpenVPN, se instala EN SILENCIO con
; msiexec para dejar su servicio interactivo y su tarjeta virtual
; TAP-Windows, sin que el usuario instale ni abra nada mas.
; SoftEther SALE por completo: al actualizar desde versiones
; anteriores se retiran sus restos (servicio SEVPNCLIENT solo si
; lo registro esta app, su carpeta y su controlador).
;
; La app se instala por máquina en Archivos de programa: escribir el hosts,
; crear la tarea semanal y tocar Defender exigen administrador, y la propia
; app pide elevación (UAC) solo para esas acciones concretas.
; El instalador NO va firmado: Windows mostrará el aviso de SmartScreen
; («Windows protegió su PC») la primera vez; ver LEEME.md.

#define AppNombre "Antivirus Hogar PC"
#define AppVersion "1.0.11"
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
; v1.0.10: restos de SoftEther de versiones anteriores (su carpeta
; con el cliente incorporado y el registro de la preparacion de su
; tarjeta virtual) se retiran al actualizar: el motor ya es
; OpenVPN. Su servicio y su controlador los retira el codigo de
; instalacion (ver RetirarRestosSoftEther), solo si son de la app.
Type: filesandordirs; Name: "{app}\softether"
Type: files; Name: "{app}\softether-nic-instalacion.txt"

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
; OpenVPN Community INCORPORADO (v1.0.10): el instalador oficial
; (MSI amd64) verificado por la compilacion (tamano y SHA-256
; fijados en el workflow). Se deja en la carpeta «openvpn» de la
; app: es el instalador interno que conserva el
; auto-actualizador, y el propio instalador de la app lo instala
; en silencio si el equipo no tiene OpenVPN (ver el codigo).
; Solo si el paquete esta al compilar: la compilacion en la nube
; lo descarga del sitio oficial, verifica tamano y huella y
; FALLA si falta; una compilacion local sin el paquete produce
; la app sin el instalador conservado (la app lo detecta).
#if FileExists("openvpn\OpenVPN-2.7.9-I002-amd64.msi")
Source: "openvpn\OpenVPN-2.7.9-I002-amd64.msi"; DestDir: "{app}\openvpn"; Flags: ignoreversion
Source: "openvpn\OPENVPN-INSTALADOR.txt"; DestDir: "{app}\openvpn"; Flags: ignoreversion
#endif
; Script de la exclusión de Defender (v1.0.7, punto 4): lo ejecuta
; el propio instalador al terminar (ver [Code]) y deja su resultado
; verificado en {app}\defender-exclusion.json.
Source: "exclusion_defender.ps1"; DestDir: "{app}"; Flags: ignoreversion

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

{ v1.0.10: OpenVPN INCORPORADO y SoftEther RETIRADO.
  OpenVPN: el instalador oficial (MSI) viaja en la carpeta
  «openvpn» de la app como instalador interno conservado; si el
  equipo no tiene openvpn.exe, ESTE instalador lo instala en
  silencio (msiexec /quiet): quedan su servicio interactivo y su
  tarjeta TAP-Windows, con controladores firmados que Windows
  acepta. Si el equipo YA tiene OpenVPN (del usuario), no se toca:
  el auto-actualizador interno de la app lo mantiene al dia.
  SoftEther: al actualizar desde la 1.0.9 o anteriores, se retira
  lo que la propia app dejo — su servicio SEVPNCLIENT (SOLO si la
  marca del registro dice que lo registro esta app: el SoftEther
  propio del usuario no se toca), el paquete de su controlador
  Neo6 en el DriverStore y su carpeta (esta ultima por
  InstallDelete). Todo queda anotado en openvpn-instalacion.txt.
  Nada de esto aborta la instalacion si algo falla. }
function OpenVPNExePath(): String;
begin
  if FileExists(ExpandConstant('{pf}\OpenVPN\bin\openvpn.exe')) then
    Result := ExpandConstant('{pf}\OpenVPN\bin\openvpn.exe')
  else if FileExists(ExpandConstant('{pf32}\OpenVPN\bin\openvpn.exe')) then
    Result := ExpandConstant('{pf32}\OpenVPN\bin\openvpn.exe')
  else
    Result := '';
end;

function OpenVPNMsiPath(): String;
begin
  Result := ExpandConstant(
    '{app}\openvpn\OpenVPN-2.7.9-I002-amd64.msi');
  if not FileExists(Result) then
    Result := '';
end;

// Registro acumulado de la instalacion de OpenVPN y de la
// retirada de SoftEther: se guarda en openvpn-instalacion.txt.
var
  LogOpenVPN: String;

procedure AgregarLogOpenVPN(Texto: String);
begin
  LogOpenVPN := LogOpenVPN + Texto;
end;

// Retira los restos de SoftEther QUE DEJO ESTA APP (ver la marca
// en el registro). El servicio se para y se borra; el paquete de
// su controlador (Neo6_x64_VPN.inf) se quita del DriverStore con
// pnputil buscando su nombre publicado (oemNN.inf) por bloques.
// Si la marca no esta, el equipo tenia SU SoftEther (o ninguno):
// no se toca nada.
procedure RetirarRestosSoftEther();
var
  ResultCode: Integer;
  Marca: String;
  Ps: String;
  Script: String;
begin
  if not RegQueryStringValue(HKLM, 'Software\Antivirus Hogar PC',
      'SoftEtherServicioPropio', Marca) or (Marca <> '1') then
  begin
    AgregarLogOpenVPN('SoftEther: sin marca de servicio propio; ' +
      'no se retira ningun servicio (si el equipo tenia un ' +
      'SoftEther del usuario, es suyo y no se toca).' + #13#10);
    Exit;
  end;
  Exec(ExpandConstant('{sys}\net.exe'), 'stop SEVPNCLIENT', '',
    SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec(ExpandConstant('{sys}\sc.exe'), 'delete SEVPNCLIENT', '',
    SW_HIDE, ewWaitUntilTerminated, ResultCode);
  AgregarLogOpenVPN('SoftEther: servicio SEVPNCLIENT (registrado ' +
    'por esta app) parado y retirado.' + #13#10);
  Ps := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  Script := '$bloques = (pnputil /enum-drivers | Out-String) ' +
    '-split ''\r?\n\r?\n''; ' +
    'foreach ($b in $bloques) { ' +
    'if (($b -match ''Neo6_x64_VPN\.inf'') -and ' +
    '($b -match ''(oem\d+\.inf)'')) { ' +
    'pnputil /delete-driver $Matches[1] /uninstall /force | ' +
    'Out-Null } }';
  Exec(Ps, '-NoProfile -NonInteractive -ExecutionPolicy Bypass ' +
    '-Command "' + Script + '"', '', SW_HIDE,
    ewWaitUntilTerminated, ResultCode);
  AgregarLogOpenVPN('SoftEther: paquete de su controlador ' +
    '(Neo6_x64_VPN.inf) retirado del DriverStore si estaba ' +
    '(pnputil, codigo ' + IntToStr(ResultCode) + ').' + #13#10);
  RegDeleteValue(HKLM, 'Software\Antivirus Hogar PC',
    'SoftEtherServicioPropio');
end;

// Instala OpenVPN en silencio si el equipo no lo tiene. El MSI
// oficial deja el servicio interactivo y la tarjeta TAP-Windows.
// Codigos de msiexec que valen: 0 (instalado), 3010 y 1641
// (instalado, reinicio pendiente). Cualquier otro se anota tal
// cual: no se finge.
procedure InstalarOpenVPN();
var
  ResultCode: Integer;
  Msi: String;
begin
  if OpenVPNExePath() <> '' then
  begin
    AgregarLogOpenVPN('OpenVPN: ya presente en el equipo (' +
      OpenVPNExePath() + '); no se reinstala. Su mantenimiento ' +
      'queda en el auto-actualizador interno de la app.' + #13#10);
    Exit;
  end;
  Msi := OpenVPNMsiPath();
  if Msi = '' then
  begin
    AgregarLogOpenVPN('OpenVPN: este instalador NO traia el ' +
      'paquete oficial (openvpn\OpenVPN-2.7.9-I002-amd64.msi): ' +
      'el motor VPN no se pudo instalar.' + #13#10);
    Exit;
  end;
  if Exec(ExpandConstant('{sys}\msiexec.exe'),
      '/i "' + Msi + '" /quiet /norestart', '',
      SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    AgregarLogOpenVPN('OpenVPN: instalador oficial ejecutado en ' +
      'silencio (msiexec, codigo ' + IntToStr(ResultCode) + '). ' +
      '0 = instalado; 3010/1641 = instalado con reinicio ' +
      'pendiente.' + #13#10)
  else
    AgregarLogOpenVPN('OpenVPN: no se pudo ni lanzar msiexec ' +
      'para instalar el paquete oficial.' + #13#10);
  if OpenVPNExePath() <> '' then
    AgregarLogOpenVPN('Verificacion: openvpn.exe presente en ' +
      OpenVPNExePath() + '.' + #13#10)
  else
    AgregarLogOpenVPN('Verificacion: openvpn.exe SIGUE sin ' +
      'aparecer tras la instalacion silenciosa; el codigo de ' +
      'msiexec de arriba dice la causa.' + #13#10);
end;

procedure PrepararMotorOpenVPN();
begin
  LogOpenVPN := 'Antivirus Hogar PC v1.0.11 - motor VPN OpenVPN ' +
    'durante la instalacion.' + #13#10 + #13#10;
  RetirarRestosSoftEther();
  InstalarOpenVPN();
  SaveStringToFile(ExpandConstant('{app}\openvpn-instalacion.txt'),
    LogOpenVPN, False);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
  Marca: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    { Solo se retira el servicio si lo registró ESTE instalador
      (instalaciones de la epoca de SoftEther, hasta la 1.0.9).
      OpenVPN NO se desinstala: es un programa del sistema que el
      usuario puede usar con otros fines. }
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

{ v1.0.7 (punto 4): exclusión de Defender anti-falso-positivo.
  Defender borró la 1.0.6 instalada en la PC del usuario (ejecutable
  PyInstaller sin firmar). El instalador —que ya corre como admin—
  ejecuta el script versionado junto a la app: añade la exclusión
  SOLO para la carpeta de instalación y para la de datos, la
  VERIFICA leyéndola de vuelta (Get-MpPreference) y deja el
  resultado en defender-exclusion.json. Si una política lo impide,
  el JSON lo dice y la app avisa al abrir con el paso manual: aquí
  no se finge nada. Queda constancia en ese JSON (declarado). }
procedure AplicarExclusionDefender();
var
  ResultCode: Integer;
  Ps: String;
  Args: String;
begin
  Ps := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  Args := '-NoProfile -ExecutionPolicy Bypass -File "' +
    ExpandConstant('{app}\exclusion_defender.ps1') +
    '" -AppDir "' + ExpandConstant('{app}') +
    '" -DatosDir "' + ExpandConstant('{localappdata}\AntivirusHogarPC') +
    '" -Resultado "' + ExpandConstant('{app}\defender-exclusion.json') + '"';
  Exec(Ps, Args, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

{ Manifiesto de componentes esperados: al abrir, la app lo usa para
  comprobar que ningún antivirus se llevó piezas por el camino. }
procedure EscribirManifiestoComponentes();
var
  Lineas: String;
begin
  Lineas := '["AntivirusHogarPC.exe", "icono.ico", "exclusion_defender.ps1"';
  { v1.0.10: el instalador interno de OpenVPN conservado. }
  if OpenVPNMsiPath() <> '' then
    Lineas := Lineas + ', "openvpn\OpenVPN-2.7.9-I002-amd64.msi"';
  Lineas := Lineas + ']';
  SaveStringToFile(ExpandConstant('{app}\componentes.json'),
    Lineas, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    SHChangeNotify($08000000, $0000, 0, 0); { SHCNE_ASSOCCHANGED }
    PrepararMotorOpenVPN();
    AplicarExclusionDefender();
    EscribirManifiestoComponentes();
  end;
end;

[UninstallDelete]
; Solo lo generado dentro de la carpeta de instalación; los datos del
; usuario (%LOCALAPPDATA%\AntivirusHogarPC: caché, cuarentena, informes)
; se conservan a propósito para no borrar cuarentenas sin preguntar.
Type: filesandordirs; Name: "{app}\_internal\__pycache__"
