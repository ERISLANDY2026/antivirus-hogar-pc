; Instalador de Antivirus Hogar PC (Inno Setup 6) — Carril E.
;
; Compilar (tras PyInstaller, ver Construir-en-Windows.bat):
;   ISCC.exe packaging\instalador.iss
; Produce: dist-instalador\Instalador-AntivirusHogarPC-1.0.9.exe
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
#define AppVersion "1.0.9"
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
  «vpnclient_x64.exe /service»).
  v1.0.9 — LA SOLUCIÓN DEL «ERROR 31»: en la 1.0.8 la tarjeta se
  creaba aquí, elevado, y AUN ASÍ NicCreate devolvía «Error code:
  31 — Installation of the Virtual Network Adapter device driver
  failed» (evidencia: el softether-nic-instalacion.txt de la PC del
  usuario). Causa raíz probada: el paquete del CONTROLADOR de la
  tarjeta (Neo6 x64) nunca quedaba instalado en el almacén de
  controladores de Windows (DriverStore); NicCreate lo ejecuta el
  servicio (SYSTEM, sesión 0), que no puede mostrar el aviso de
  confianza del editor para un controlador aún no almacenado, y la
  instalación del driver moría siempre. El instalador oficial de
  SoftEther SÍ deja ese controlador almacenado al instalar. Desde
  la 1.0.9 ESTE instalador hace lo mismo: con pnputil, A LA VISTA y
  ANTES de NicCreate, almacena el paquete oficial del controlador
  (softether\driver\Neo6_x64_VPN.inf, extraído en la compilación
  del hamcore del instalador oficial y verificado por huella) y
  comprueba con pnputil /enum-drivers que quedó guardado. Todo el
  proceso queda en softether-nic-instalacion.txt.
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

// v1.0.9: registro ACUMULADO de la preparación de la tarjeta
// virtual (sección del controlador + sección de NicCreate) que se
// guarda de una vez en softether-nic-instalacion.txt.
var
  LogNic: String;

procedure AgregarLogNic(Texto: String);
begin
  LogNic := LogNic + Texto;
end;

// Trae el paquete del controlador en la enumeración de pnputil?
// La salida de /enum-drivers trae «Original Name: Neo6_x64_VPN.inf»
// (en español: «Nombre original:»); basta buscar el nombre del .inf.
function EnumTraeControlador(RutaCaptura: String): Boolean;
begin
  Result := Pos('neo6_x64_vpn.inf',
    LowerCase(LeerCaptura(RutaCaptura))) > 0;
end;

// v1.0.9: EL CONTROLADOR SE ALMACENA EN EL DRIVERSTORE, A LA VISTA
// Y ANTES DE CREAR LA TARJETA. Es EL paso que faltaba (ver la causa
// raíz en el comentario de RegistrarServicioSoftEther): pnputil
// /add-driver deja el paquete Neo6_x64_VPN (el controlador oficial
// de SoftEther para Windows 10 x64, hardware NeoAdapter_VPN) en el
// almacén de controladores de Windows; con el paquete ya
// almacenado y aceptado, el servicio SEVPNCLIENT puede crear la
// tarjeta sin necesitar ningún aviso interactivo. Este paso corre
// VISIBLE (SW_SHOW), NUNCA SW_HIDE: si Windows enseña su aviso de
// instalación del controlador, el usuario debe poder verlo y
// aceptarlo. Su salida exacta y la verificación con
// pnputil /enum-drivers van al registro acumulado.
procedure InstalarControladorTarjetaVirtual();
var
  ResultCode: Integer;
  Inf: String;
  Pnp: String;
  CapAdd: String;
  CapEnum: String;
  Orden: String;
begin
  Inf := ExpandConstant('{app}\softether\driver\Neo6_x64_VPN.inf');
  if not FileExists(Inf) then
  begin
    AgregarLogNic('Controlador de la tarjeta virtual: el paquete ' +
      'NO trae softether\driver\Neo6_x64_VPN.inf: no se pudo ' +
      'almacenar el controlador en el DriverStore.' + #13#10);
    Exit;
  end;
  Pnp := ExpandConstant('{sys}\pnputil.exe');
  CapAdd := ExpandConstant('{tmp}\ahpc-pnputil-add.txt');
  CapEnum := ExpandConstant('{tmp}\ahpc-pnputil-enum.txt');
  Orden := '/C ""' + Pnp + '" /add-driver "' + Inf + '" /install ' +
    '> "' + CapAdd + '" 2>&1"';
  Exec(ExpandConstant('{cmd}'), Orden, '', SW_SHOW,
    ewWaitUntilTerminated, ResultCode);
  AgregarLogNic('--- pnputil /add-driver "' + Inf + '" /install ' +
    '(codigo del proceso: ' + IntToStr(ResultCode) + ') ---' + #13#10 +
    LeerCaptura(CapAdd) + #13#10);
  Orden := '/C ""' + Pnp + '" /enum-drivers > "' + CapEnum + '" 2>&1"';
  Exec(ExpandConstant('{cmd}'), Orden, '', SW_HIDE,
    ewWaitUntilTerminated, ResultCode);
  if EnumTraeControlador(CapEnum) then
    AgregarLogNic('Verificacion del controlador: pnputil ' +
      '/enum-drivers TRAE el paquete Neo6_x64_VPN.inf: el ' +
      'controlador quedo ALMACENADO en el DriverStore.' + #13#10)
  else
    AgregarLogNic('Verificacion del controlador: pnputil ' +
      '/enum-drivers NO trae Neo6_x64_VPN.inf: el controlador NO ' +
      'quedo almacenado; la salida de pnputil va arriba.' + #13#10);
  AgregarLogNic(#13#10);
end;

// LA TARJETA VIRTUAL SE CREA EN LA INSTALACION (v1.0.8), DESPUÉS de
// almacenar su controlador (v1.0.9). Aqui se asegura el servicio en
// marcha, se ejecuta NicCreate con el vpncmd incorporado y se
// verifica con NicList; su sección se añade al registro acumulado.
// Si algo falla NO se aborta la instalacion: queda registrado para
// que el usuario pueda reportarlo.
procedure CrearTarjetaVirtualSoftEther();
var
  ResultCode: Integer;
  Cmd: String;
  CapAntes: String;
  CapCreate: String;
  CapDespues: String;
  Orden: String;
begin
  Cmd := VpncmdPath();
  if Cmd = '' then
  begin
    AgregarLogNic('vpncmd no encontrado en la carpeta de ' +
      'SoftEther: la tarjeta virtual NO se pudo crear.' + #13#10);
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
    AgregarLogNic('La tarjeta virtual (VPN) YA existia: NicList ' +
      'la trae y no hizo falta crearla.' + #13#10);
  end
  else
  begin
    Orden := '/C ""' + Cmd + '" localhost /CLIENT /CMD NicCreate VPN' +
      ' > "' + CapCreate + '" 2>&1"';
    Exec(ExpandConstant('{cmd}'), Orden, '', SW_HIDE,
      ewWaitUntilTerminated, ResultCode);
    AgregarLogNic('NicCreate ejecutado durante la instalacion ' +
      '(codigo del proceso: ' + IntToStr(ResultCode) + ').' + #13#10);
    Sleep(2000);
    Orden := '/C ""' + Cmd + '" localhost /CLIENT /CMD NicList > "' +
      CapDespues + '" 2>&1"';
    Exec(ExpandConstant('{cmd}'), Orden, '', SW_HIDE,
      ewWaitUntilTerminated, ResultCode);
    if NicListTraeVPN(CapDespues) then
      AgregarLogNic('Verificacion: NicList trae la tarjeta (VPN): ' +
        'tarjeta creada y presente.' + #13#10)
    else
      AgregarLogNic('Verificacion: NicList sigue SIN traer la ' +
        'tarjeta (VPN): la creacion fallo; la salida exacta de ' +
        'vpncmd va debajo para poder reportarla.' + #13#10);
    AgregarLogNic(#13#10 + '--- Salida de NicCreate ---' + #13#10 +
      LeerCaptura(CapCreate) + #13#10 +
      '--- Salida de NicList (despues) ---' + #13#10 +
      LeerCaptura(CapDespues));
  end;
end;

// v1.0.9: la preparación completa de la tarjeta, en orden: primero
// el controlador al DriverStore (pnputil, visible) y después la
// creación de la tarjeta (NicCreate verificado con NicList). El
// registro acumulado se guarda de una vez junto a la app.
procedure PrepararTarjetaVirtualSoftEther();
begin
  LogNic := 'Antivirus Hogar PC v1.0.9 - preparacion de la tarjeta ' +
    'virtual de SoftEther durante la instalacion.' + #13#10 + #13#10;
  if VpncmdPath() = '' then
    AgregarLogNic('vpncmd no encontrado en la carpeta de SoftEther: ' +
      'este instalador no traia el paquete y la tarjeta virtual NO ' +
      'se pudo preparar.' + #13#10)
  else
  begin
    InstalarControladorTarjetaVirtual();
    CrearTarjetaVirtualSoftEther();
  end;
  SaveStringToFile(ExpandConstant('{app}\softether-nic-instalacion.txt'),
    LogNic, False);
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
  begin
    Lineas := Lineas + ', "softether\vpnclient_x64.exe", ' +
      '"softether\vpncmd_x64.exe", "softether\vpncmgr_x64.exe", ' +
      '"softether\hamcore.se2"';
    { v1.0.9: el paquete del controlador de la tarjeta virtual. }
    if FileExists(ExpandConstant(
        '{app}\softether\driver\Neo6_x64_VPN.inf')) then
      Lineas := Lineas + ', "softether\driver\Neo6_x64_VPN.inf", ' +
        '"softether\driver\Neo6_x64_VPN.sys", ' +
        '"softether\driver\Neo6_x64_VPN.cat"';
  end;
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
    PrepararTarjetaVirtualSoftEther();
    AplicarExclusionDefender();
    EscribirManifiestoComponentes();
  end;
end;

[UninstallDelete]
; Solo lo generado dentro de la carpeta de instalación; los datos del
; usuario (%LOCALAPPDATA%\AntivirusHogarPC: caché, cuarentena, informes)
; se conservan a propósito para no borrar cuarentenas sin preguntar.
Type: filesandordirs; Name: "{app}\_internal\__pycache__"
