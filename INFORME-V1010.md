# INFORME V1.0.10 — Cambio de motor VPN: fuera SoftEther, entra OpenVPN

Fecha: 2026-11-25. Orden del usuario (llamada de voz, ~07:55 EST):
reemplazar SoftEther por OpenVPN dentro del paquete de instalación,
programado internamente para suplirlo en segundo plano de la misma
manera, con instalador/actualizador interno AUTOMÁTICO y SILENCIOSO
que siga cumpliendo sus funciones y que NO rompa OpenVPN con una
actualización. Orden de arranque: «Arranca».

## Por qué salió SoftEther (cadena cerrada en la 1.0.9)

La prueba del usuario de la 1.0.9 en su Toughbook CF-54 demostró
con el registro `softether-nic-instalacion.txt` que pnputil SÍ
almacenó el controlador Neo6_x64_VPN (quedó como oem78.inf,
verificado en el DriverStore) y AUN ASÍ NicCreate devolvió
«Error code: 31 — Installation of the Virtual Network Adapter
device driver failed». Con la Integridad de memoria (Core
Isolation) confirmada APAGADA por el propio usuario, la barrera
restante es la política de firma de Windows contra el controlador
de SoftEther de 2018 al instalar el DISPOSITIVO: ninguna versión
de la app puede forzarlo por código. Decisión del usuario:
cambiar el motor a OpenVPN, cuyo controlador TAP-Windows trae la
firma que Windows acepta.

## 1. Fuera SoftEther (completo)

- Sin payload de SoftEther en el instalador (fuera la carpeta
  `packaging/softether/` y su descarga en CI), sin servicio
  SEVPNCLIENT, sin controlador Neo, sin pnputil/NicCreate, sin
  `winapi/softether_update.py` (borrado) y sin ninguna función
  vpncmd en `winapi/vpn_win.py` (reescrito).
- Retirada limpia de restos al instalar: `RetirarRestosSoftEther()`
  en el instalador SOLO actúa si la clave de registro de la app
  lleva su marca (`SoftEtherServicioPropio`='1'): para y borra el
  servicio SEVPNCLIENT, retira del DriverStore el paquete cuyo INF
  sea Neo6_x64_VPN.inf (localiza su oemNN.inf) y borra la marca.
  Sin marca no toca nada (un SoftEther del usuario es suyo).
  [InstallDelete] retira `{app}\softether` y el registro viejo
  `softether-nic-instalacion.txt`. Todo queda anotado en
  `{app}\openvpn-instalacion.txt`.

## 2. OpenVPN incorporado y verificado

- OpenVPN Community **2.7.9-I002 amd64** oficial:
  `https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.9-I002-amd64.msi`
  — 5,939,200 bytes, SHA-256
  `d050efadc6cabc4e304eb810dd7fedfc54b859d34730ab9cdcb22d61eb86ab7a`.
  La CI lo descarga y lo verifica en cada compilación (tamaño,
  huella y firma Authenticode: «Valid — CN=OpenVPN Inc.,
  O=OpenVPN Inc., L=Pleasanton, S=California, C=US»).
- El instalador de la app lo deja en `{app}\openvpn` (es el
  instalador CONSERVADO que usa el auto-actualizador) y lo instala
  en silencio (`msiexec /i … /quiet /norestart`) SOLO si
  openvpn.exe no está ya presente; deja su servicio
  (OpenVPNServiceInteractive) y su tarjeta TAP-Windows. Si ya está
  (p. ej. porque el auto-actualizador lo subió de versión), no lo
  reinstala: su mantenimiento es del actualizador interno.

## 3. La app maneja OpenVPN en segundo plano (misma pantalla)

- `winapi/vpn_win.py` reescrito: lanza `openvpn.exe` oculto con el
  perfil .ovpn de cada servidor de VPN Gate (preparado por
  `preparar_perfil_vpngate`: credenciales «vpn»/«vpn» en archivo
  aparte, `data-ciphers-fallback` cuando el perfil trae `cipher`)
  y la interfaz de gestión en 127.0.0.1. El túnel solo se da por
  conectado cuando la interfaz dice **CONNECTED,SUCCESS**; la
  desconexión va por la interfaz (`signal SIGTERM`). El usuario no
  ve OpenVPN por ningún lado.
- Errores con causa REAL: si el proceso muere, el mensaje en
  español clasifica la causa del registro de OpenVPN por prioridad
  (autenticación → tarjeta TAP → TLS/red → error fatal), con la
  línea real en el detalle. Nada de textos inventados.
- La UX no cambia: misma lista (en vivo + semilla), fila conectada
  con «Conectado» verde + «Desconectar» rojo, globo terráqueo
  girando a 1 vuelta/s, IP pública y estado «VPN: …».
- **Botones «Conectar» cortados (reporte de la 1.0.9): CORREGIDO.**
  Causa: el tema pide ≈37 px de botón y la fila por defecto medía
  ~30 px. Ahora la tabla nace con `setDefaultSectionSize(42)` y
  `_repintar_servidores()` hace `resizeRowsToContents()` con suelo
  de 42 px por fila. Verificado con captura offscreen
  (`evidencia-v1010/vpngate-tabla-fila-conectada.png`: botones
  completos, sin corte) y con test geométrico (el botón cabe entero
  en su celda).

## 4. Auto-actualizador interno de OpenVPN (las 4 condiciones)

Nuevo `winapi/openvpn_update.py` (patrón del de SoftEther), con el
chequeo cada 3 días al abrir la app desde `ui/main.py`:

a. **Instalador interno:** la app conserva el MSI oficial vigente
   en `{app}\openvpn` y puede instalarlo/actualizarlo por sí misma
   (msiexec elevado en silencio; códigos 0/3010/1641 = éxito).
b. **Automático y silencioso:** chequeo al abrir si pasaron 3 días;
   fuentes oficiales (openvpn.net/community-downloads y la API de
   GitHub del repo OpenVPN/openvpn; manda la versión mayor; la
   descarga sale siempre de swupdate.openvpn.org). Sin avisos
   salvo el globito de la bandeja al aplicar.
c. **Sigue cumpliendo sus funciones:** tras aplicar, re-verifica la
   integración (exe localizado, versión ≥ la aplicada, servicio
   interactivo registrado, tarjeta TAP presente) y la conexión se
   sigue usando desde la misma pantalla; al desconectar se intenta
   aplicar lo que hubiera quedado diferido.
d. **Que no se rompa (la clave):** el paquete se verifica ANTES de
   quedar pendiente (tamaño contra el Content-Length oficial,
   magia MSI OLE y firma — ver la nota de firma abajo); si no pasa,
   se borra y NO queda pendiente. NUNCA se aplica con un túnel
   activo (se difiere hasta desconectar). Justo antes de aplicar
   se re-verifica tamaño+SHA-256 y se respalda el instalador
   anterior; tras aplicar se verifica la integración y, si falla,
   **REVIERTE** reinstalando el anterior y lo deja registrado con
   la causa real («…se REVIERTE a la versión anterior…»). Si
   msiexec falla, el pendiente se conserva para reintentar y no se
   toca la instalación vigente.

**Nota de firma (forense de CI, 6 corridas):** el MSI es válido y
está firmado por OpenVPN Inc. (probado por pwsh 7 en el paso 10 de
cada corrida). Pero bajo `powershell.exe` 5.1 —el de Windows 10—
`Get-AuthenticodeSignature` devuelve el objeto vacío/$null para
este MSI (corridas 45622879778, 45624087168, 45624972822) y la
cadena `X509Chain` de .NET Framework tampoco la procesa
(45626704138/45627582180: Build=False con ChainStatus vacío). Por
eso `firma_authenticode` tiene DOS métodos: (1) el cmdlet, con su
validación completa, cuando responde; (2) si devuelve vacío, un
respaldo con `X509Certificate.CreateFromSignedFile` (API clásica
que SÍ lee el certificado incrustado en 5.1) que exige firmante
OpenVPN y certificado dentro de su periodo de validez. En la
corrida buena, la verificación del actualizador contra el MSI
real pasó por este respaldo: «Firma Authenticode: {'valida':
True, 'firmante': 'CN=OpenVPN Inc., …'}».

## 5. Pruebas y compilación

- Suite local completa: **261/261** (la de la 1.0.9 era 259).
  Nuevas en `tests/test_v1010.py` (24): guardas de ausencia total
  de SoftEther en el paquete y de presencia/verificación de
  OpenVPN, altura de fila (código + geometría offscreen), motor
  simulado por sus dos puertas (perfil, CONNECTED,SUCCESS,
  AUTH_FAILED con causa real, desconexión por la interfaz) y el
  actualizador completo (versiones, cadencia, fuentes, paquete,
  firma, pendiente solo verificado, descarte por firma, diferido
  con túnel, aplicación OK, REVERSIÓN, msiexec fallido,
  re-sincronización). Cirugía mínima en test_v107,
  test_v107_refuerzos, test_v109 y test_bugs_v102 (las secciones
  de SoftEther se retiraron; se conservan Discos, Defender,
  bandeja, icono, la fila verde/roja, el radar y la guarda ISPP).
- CI: corridas fallidas 45622879778, 45624087168, 45624972822,
  45625950608 (esta corrió por error sobre el commit anterior),
  45626704138 y 45627582180 — TODAS por el mismo paso 11 (el
  ejercicio de la firma, ver la nota) y cada una dejó la evidencia
  que llevó al arreglo; el resto de pasos (suite, PyInstaller,
  Inno) pasó desde la primera. **Corrida buena: 45628199685
  SUCCESS** (commit `fcd01c10909af9a661401f593466bd954a70682f`;
  el código de la app es el del commit principal `77b90a6` más las
  correcciones de firma `844cd93`, `a3ad292`, `26c98b1b`,
  `2b16ddd` y `fcd01c1`). En CI: «261 passed», «OpenVPN oficial:
  5939200 bytes», firma del paso 10 «Valid — CN=OpenVPN Inc.» y
  «Auto-actualizador de OpenVPN OK contra el instalador oficial
  real». Registros completos en `build-nube-v1010/ci-*.log.txt`.

## 6. Instalador y canal

- Instalador: **Instalador-AntivirusHogarPC-1.0.10.exe**,
  45,193,489 bytes (la 1.0.9 pesaba 63,729,305: sale el payload de
  SoftEther y entra el MSI de 5.9 MB), MD5
  `9f7c5021da9eb29f1068340e163e3ab4`, SHA-256
  `32a3d58521aeeaccec94f5fbb38955db43184c49af027766d8df08ef33547117`.
  Zip: AntivirusHogarPC-Instalador-v1.0.10.zip, 44,683,008 bytes,
  MD5 `09cc2ac0b2a55303b647c61b650bf772`.
- Canal Drive EN SITIO (mismos IDs): exe
  `1zmtcu-NL-PvCbGisbAXbFwVwyBlI5_ql` → «Instalador-AntivirusHogarPC-1.0.10.exe»,
  zip `1ZHiCO9lInsLv6GJBCdCj6GtTMjGf6hTG` → «AntivirusHogarPC-Instalador-v1.0.10.zip»,
  version-pc.json `1Kfd_pELWJhp37fO1iaERdSIzpRkAqK4R` (versión
  1.0.10, URL del exe con `&confirm=t`, SHA-256 nuevo). Los tres
  verificados: anyoneWithLink=reader, trashed=false, tamaños y
  MD5 coincidentes con lo compilado.
- Copia visible NUEVA: «INSTALADOR Antivirus Hogar PC v1.0.10.zip»,
  ID `1NMQ-DHQcxDEfBm8LWGGJnNiDGD-EL0MU` (anyoneWithLink=reader).
  La copia visible de la 1.0.9 (`1_xfSG7tAFiCjANy2BK6Q-s09oS4CzraM`)
  quedó en la papelera (trashed=true verificado).
- **PUERTA FINAL ANÓNIMA SUPERADA** con el código real de la app
  (`build-nube-v1010/puerta-final.py`): desde 1.0.9 OFRECE la
  1.0.10; desde 1.0.10 «al día»; descarga completa por la URL del
  JSON con SHA-256 válido; corte forzado a 15,000,000 B y
  reanudación con SHA-256 válido.

## 7. Honestidad (lo no probado)

- El túnel REAL contra un servidor VPN Gate en vivo NO se ha
  probado: solo se prueba en la Toughbook del usuario al instalar
  la 1.0.10 y darle «Conectar» (la CI no tiene red VPN ni puede
  elevar). Lo probado: el motor por sus dos puertas con dobles
  fieles, la instalación silenciosa del MSI la hace el instalador
  oficial de OpenVPN (el mismo que instala medio mundo), y la
  retirada de restos sigue el mismo patrón marcado de la 1.0.7.
- La instalación del MSI de OpenVPN por el instalador de la app
  (msiexec en silencio) tampoco se ejecutó en una Windows real en
  esta entrega: la CI lo empaqueta y verifica su firma, no lo
  instala. Si algo fallara, `{app}\openvpn-instalacion.txt` guarda
  el código de msiexec y la causa.
- La primera conexión real puede tardar: VPN Gate mezcla
  servidores UDP/TCP y perfiles viejos; si un servidor no conecta,
  el mensaje trae la causa real de su registro y se elige otro.

## 8. Qué debe pasar ahora (en la Toughbook)

1. Actualizar desde el botón de la 1.0.9 (o instalar la copia
   visible de Drive): el instalador retira los restos de SoftEther
   e instala OpenVPN en silencio.
2. Abrir Red y VPN → VPN Gate y darle «Conectar» a un servidor: el
   botón debe ponerse verde «Conectado» con su «Desconectar» rojo.
3. Revisar `{app}\openvpn-instalacion.txt` si algo no cuadra: ahí
   queda la retirada de restos y el resultado de msiexec.
