; Instalador de Antivirus Hogar PC (Inno Setup 6) — Carril E.
;
; Compilar (tras PyInstaller, ver Construir-en-Windows.bat):
;   ISCC.exe packaging\instalador.iss
; Produce: dist-instalador\Instalador-AntivirusHogarPC-1.0.8.exe
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
#define AppVersion "1.0.8"
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

{ v1.0.7: SoftEther INCORPORADO. El instalador oficial de SoftEther
  no admite instalación silenciosa (verificado: es un instalador
  propio sin parámetros desatendidos documentados), así que la vía
  es la de su comunidad oficial: copiar los archivos del cliente y
  registrar su servicio de Windows (SEVPNCLIENT, binario
  «vpnclient_x64.exe /service»). La tarjeta virtual la crea ESTE
  instalador al terminar (v1.0.8: ver CrearTarjetaVirtualSoftEther),
  elevado e interactivo, que es el contexto que Windows exige para
  instalar su driver; en la 1.0.7 ese paso quedaba para el primer
  «Conectar» de la app, sin elevar y en oculto, y fallaba siempre.
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

// v1.0.8: ruta del vpncmd INCORPORADO (para crear la tarjeta
// virtual durante la instalacion, ver CrearTarjetaVirtualSoftEther).
function VpncmdPath(): String;
begin
  if FileExists(ExpandConstant('{app}\softether\vpncmd_x64.exe')) then
    Result := ExpandConstant('{app}\softether\vpncmd_x64.exe')
  else if FileExists(ExpandConstant('{app}\softether\vpncmd.exe')) then
    Result := ExpandConstant('{app}\softether\vpncmd.exe')
  else
    Result := '';
end;

// Lee un archivo de texto capturado y lo devuelve como un bloque.
function LeerCaptura(Ruta: String): String;
var
  Lineas: TArrayOfString;
  i: Integer;
begin
  Result := '';
  if LoadStringsFromFile(Ruta, Lineas) then
    for i := 0 to GetArrayLength(Lineas) - 1 do
      Result := Result + Lineas[i] + #13#10;
end;

// Trae la captura de NicList la tarjeta «VPN»? Las tablas de vpncmd
// ponen el nombre del adaptador como primera celda de su fila (la
// fila lleva «|»); el prompt «VPN Client>» no lleva «|» y se descarta.
function NicListTraeVPN(RutaCaptura: String): Boolean;
var
  Lineas: TArrayOfString;
  i: Integer;
  L: String;
begin
  Result := False;
  if not LoadStringsFromFile(RutaCaptura, Lineas) then
    Exit;
  for i := 0 to GetArrayLength(Lineas) - 1 do
  begin
    L := Trim(Lineas[i]);
    if (Length(L) >= 3) and (Copy(L, 1, 3) = 'VPN') and
        (Pos('|', L) > 0) then
      if (Length(L) = 3) or (Copy(L, 4, 1) = ' ') or
          (Copy(L, 4, 1) = '|') then
      begin
        Result := True;
        Exit;
      end;
  end;
end;

// v1.0.8: LA TARJETA VIRTUAL SE CREA EN LA INSTALACION.
// Causa raiz del fallo de VPN Gate en la 1.0.7: el instalador nunca
// instalaba el driver de la tarjeta virtual y la app intentaba
// crearla despues, sin elevar y en oculto; crear esa tarjeta es
// operacion de administrador con posible dialogo de Windows. El
// instalador SI corre elevado e interactivo: aqui se asegura el
// servicio en marcha, se ejecuta NicCreate con el vpncmd incorporado
// y se verifica con NicList. TODO queda escrito, con la salida
// exacta de vpncmd, en softether-nic-instalacion.txt junto a la app.
// Si algo falla NO se aborta la instalacion: queda registrado para
// que el usuario pueda reportarlo.
procedure CrearTarjetaVirtualSoftEther();
var
  ResultCode: Integer;
  Cmd: String;
  Log: String;
  CapAntes: String;
  CapCreate: String;
  CapDespues: String;
  Orden: String;
begin
  Cmd := VpncmdPath();
  if Cmd = '' then
  begin
    SaveStringToFile(ExpandConstant('{app}\softether-nic-instalacion.txt'),
      'v1.0.8: vpncmd no encontrado en la carpeta de SoftEther: este ' +
      'instalador no traia el paquete y la tarjeta virtual NO se ' +
      'pudo crear.' + #13#10, False);
    Exit;
  end;
  CapAntes := ExpandConstant('{tmp}\ahpc-niclist-antes.txt');
  CapCreate := ExpandConstant('{tmp}\ahpc-niccreate.txt');
  CapDespues := ExpandConstant('{tmp}\ahpc-niclist-despues.txt');
  // El servicio debe estar en marcha para que vpncmd le hable; si ya
  // corria, este «net start» devuelve error sin ninguna importancia.
  Exec(ExpandConstant('{sys}\net.exe'), 'start SEVPNCLIENT', '',
    SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(2000);
  Orden := '/C ""' + Cmd + '" localhost /CLIENT /CMD NicList > "' +
    CapAntes + '" 2>&1"';
  Exec(ExpandConstant('{cmd}'), Orden, '', SW_HIDE,
    ewWaitUntilTerminated, ResultCode);
  if NicListTraeVPN(CapAntes) then
  begin
    Log := 'v1.0.8: la tarjeta virtual (VPN) YA existia: NicList la ' +
      'trae y no hizo falta crearla.' + #13#10;
  end
  else
  begin
    Orden := '/C ""' + Cmd + '" localhost /CLIENT /CMD NicCreate VPN' +
      ' > "' + CapCreate + '" 2>&1"';
    Exec(ExpandConstant('{cmd}'), Orden, '', SW_HIDE,
      ewWaitUntilTerminated, ResultCode);
    Log := 'v1.0.8: NicCreate ejecutado durante la instalacion ' +
      '(codigo del proceso: ' + IntToStr(ResultCode) + ').' + #13#10;
    Sleep(2000);
    Orden := '/C ""' + Cmd + '" localhost /CLIENT /CMD NicList > "' +
      CapDespues + '" 2>&1"';
    Exec(ExpandConstant('{cmd}'), Orden, '', SW_HIDE,
      ewWaitUntilTerminated, ResultCode);
    if NicListTraeVPN(CapDespues) then
      Log := Log + 'Verificacion: NicList trae la tarjeta (VPN): ' +
        'tarjeta creada y presente.' + #13#10
    else
      Log := Log + 'Verificacion: NicList sigue SIN traer la tarjeta ' +
        '(VPN): la creacion fallo; la salida exacta de vpncmd va ' +
        'debajo para poder reportarla.' + #13#10;
    Log := Log + #13#10 + '--- Salida de NicCreate ---' + #13#10 +
      LeerCaptura(CapCreate) + #13#10 +
      '--- Salida de NicList (despues) ---' + #13#10 +
      LeerCaptura(CapDespues);
  end;
  SaveStringToFile(ExpandConstant('{app}\softether-nic-instalacion.txt'),
    Log, False);
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
  if SoftEtherExePath() <> '' then
    Lineas := Lineas + ', "softether\vpnclient_x64.exe", ' +
      '"softether\vpncmd_x64.exe", "softether\vpncmgr_x64.exe", ' +
      '"softether\hamcore.se2"';
  Lineas := Lineas + ']';
  SaveStringToFile(ExpandConstant('{app}\componentes.json'),
    Lineas, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    SHChangeNotify($08000000, $0000, 0, 0); { SHCNE_ASSOCCHANGED }
    RegistrarServicioSoftEther();
    CrearTarjetaVirtualSoftEther();
    AplicarExclusionDefender();
    EscribirManifiestoComponentes();
  end;
end;

[UninstallDelete]
; Solo lo generado dentro de la carpeta de instalación; los datos del
; usuario (%LOCALAPPDATA%\AntivirusHogarPC: caché, cuarentena, informes)
; se conservan a propósito para no borrar cuarentenas sin preguntar.
Type: filesandordirs; Name: "{app}\_internal\__pycache__"
