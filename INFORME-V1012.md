# INFORME V1.0.12 — La VPN por el Interactive Service, sin huérfanos

Fecha: 2026-11-25. Orden del usuario (10:37 EST, «Sí, arma la
1.0.12 con ese plan»): construir la corrección con el plan cerrado
de la sección «PRUEBA v1.0.11» (§5–§6) de
`INVESTIGACION-VPN-V1010.md`. Alcance exacto cumplido; intactos el
arreglo de barras dobles y su puerta de parseo en CI, el estado
honesto de la 1.0.11 y el auto-actualizador de OpenVPN.

## El diagnóstico que la motiva (cerrado en la investigación)

La 1.0.11 ya parseaba y el túnel llegaba a «Initialization
Sequence Completed», pero:

1. La app lanzaba openvpn.exe por Popen SIN privilegios y SIN el
   Interactive Service → Windows negó las rutas del
   redirect-gateway (`route addition failed using
   CreateIpForwardEntry: Access is denied. [status=5]`) y el
   túnel quedó abierto pero inútil.
2. Ese fallo de rutas NO es fatal para OpenVPN y el intento dejó
   un openvpn.exe HUÉRFANO vivo sujetando la TAP (confirmado por
   el usuario en el Administrador de tareas):
   `conectar_openvpn()` no tenía try/finally ni guarda de un
   solo intento.
3. El clasificador convirtió una línea INFORMATIVA del adaptador
   en el titular falso «no pudo abrir su tarjeta virtual…
   reinstala la app».

## 1. Vía principal: OpenVPN Interactive Service

- Cliente del tubo `\\.\pipe\openvpn\service` con ctypes
  (CreateFileW en modo mensaje, WaitNamedPipe ante
  ERROR_PIPE_BUSY): UNA sola escritura con el mensaje oficial de
  arranque —tres cadenas UTF-16 terminadas en nulo: directorio de
  trabajo, opciones SIN argv[0] (entrecomilladas con
  list2cmdline) y stdin vacío— y lectura de la respuesta de tres
  cadenas separadas por LF: código 0 → PID («0x»+hex) y el
  proceso queda vigilado por PID (poll/wait por
  GetExitCodeProcess); código ≠ 0 → error Win32 o propio del
  servicio (0x2000000x), con su causa.
- El servicio ejecuta las operaciones privilegiadas (rutas, IP,
  DNS) por su tubo y openvpn sigue corriendo como el usuario. La
  interfaz de gestión `--management 127.0.0.1 <puerto>` viaja
  como opción más: CONNECTED,SUCCESS y el SIGTERM de desconexión
  quedan como en la 1.0.11. La sesión guarda el PID devuelto por
  el servicio y la vía usada.
- Reserva ELEVADA (ShellExecuteEx «runas», mango vigilado) si el
  servicio no responde o no autoriza; en su Toughbook la
  elevación no muestra UAC. Si tampoco, causa honesta en
  pantalla con ambos errores.

## 2. Puerta previa e instalador (el grupo)

- `puerta_previa_openvpn()`: servicio interactivo corriendo;
  membresía EFECTIVA del grupo «OpenVPN Administrators» en la
  sesión (`whoami /groups`); si el usuario consta en el
  directorio (`net localgroup`) pero la sesión aún no lo
  refleja, la app lo dice («CIERRA SESIÓN una vez…») y ofrece la
  reserva elevada para ese intento; si no consta, aviso y
  reserva elevada. El diagnóstico (`diagnostico_openvpn`) trae
  las claves nuevas: servicio_interactivo, grupo_sesion,
  grupo_directorio, via.
- Instalador: `packaging/grupo_openvpn.ps1` nuevo (patrón del de
  Defender): crea el grupo local si falta, añade al usuario de
  la SESIÓN interactiva (Win32_ComputerSystem.UserName, no la
  cuenta elevada del instalador), verifica/arranca
  OpenVPNServiceInteractive y deja su resultado en ASCII; Inno
  lo vuelca a `openvpn-instalacion.txt` con el aviso del posible
  re-login. El script va en [Files] y en el manifiesto de
  componentes.

## 3. Ciclo de vida: ningún huérfano más

- UN solo intento a la vez: guarda en el motor
  (`_cerrar_intento_previo`) y en la página (`_vpn_conectando`).
- Limpieza con try/finally: TODA salida que no sea éxito
  confirmado cierra el proceso (SIGTERM por gestión → espera →
  terminate → kill, verificando poll()) y borra la sesión; la
  sesión solo sobrevive como «conectada».
- Barrido previo de huérfanos PROPIOS (línea de comandos con
  nuestro `vpngate-activo.ovpn` o PID de sesión), anotado en
  actividad.jsonl. Un openvpn AJENO no se mata: si sujeta la
  TAP, la conexión ni se lanza y la pantalla dice «Otro OpenVPN
  está usando la tarjeta virtual en este equipo (no es de esta
  app): ciérralo y vuelve a intentarlo».
- Al cerrar la app (atexit) o destruirse la página de Red, un
  intento aún «conectando» se baja; un túnel confirmado no se
  toca. Desconexión con verificación post-cierre (proceso
  muerto + sin propios vivos), anotada.

## 4. Clasificador nuevo

- `_analizar_registro()` (puro): una línea informativa NUNCA es
  causa (solo error/fatal/warning/failed/denied/cannot, con
  respaldo por familias para eventos sin palabra de error como
  «Connection reset»); la familia «rutas/privilegios»
  (route addition failed, CreateIpForwardEntry, Access is
  denied, status=5) se evalúa ANTES que la de adaptador, con su
  mensaje propio («Windows negó crear las rutas del tráfico: no
  es la tarjeta ni el servidor»); la familia «tarjeta» solo casa
  con fallos REALES de apertura (Cannot open TUN/TAP, CreateFile
  failed on tap, All tap-windows6 adapters…).
- «Initialization Sequence Completed» + rutas fallidas = estado
  «túnel abierto pero sin rutas: tu tráfico no sale por la VPN»,
  tanto si el proceso muere como si la gestión confirma: ese
  túnel se baja limpio por el finally. El detalle de pantalla
  incluye «Código de salida de OpenVPN: N».

## 5. Problemas durante la construcción (con su causa)

1. **Primera CI fallida (run 45649876905, 12 pruebas, UNA
   causa):** en el runner de Windows la puerta previa corre de
   verdad y su detección del adaptador TAP por nombre
   (Get-NetAdapter) devuelve «ausente» porque en ese paso
   OpenVPN aún no está instalado — el bloqueo duro dejaba sin
   conectar a toda la suite del motor (viejas y nuevas). La
   detección por nombre es falible (DCO con otro nombre,
   permisos): pasó a ser AVISO, no bloqueo; el único bloqueo que
   queda es la ausencia del ejecutable. Si la tarjeta falta de
   verdad, openvpn muere con su error real de apertura y el
   clasificador lo reporta como familia «tarjeta». Segunda CI
   (run 45650309495): SUCCESS.
2. **El dispatch del workflow por la API devolvió 500** (dos
   intentos): la corrida se disparó por la otra vía prevista en
   el propio workflow, el tag `v1.0.12` sobre el commit remoto
   (movido al commit de la corrección en la segunda corrida).
3. **Dato nuevo tras la entrega (foto del usuario, intento de
   la 1.0.11 de las 11:31:14, servidor vpn312735118):** el
   registro de ESE intento terminó en `CreateFile failed on
   tap-windows6 device … General failure (ERROR_GEN_FAILURE)
   (errno=31)` + `All tap-windows6 adapters on this system are
   currently in use or disabled.` — la TAP OCUPADA por el
   huérfano de las 11:30 (mismo GUID que en la prueba elevada de
   las 11:33; el usuario mató el huérfano ~11:35 y ambos fallos
   quedan explicados). La 1.0.11 lo clasificó MAL OTRA VEZ como
   TLS («cortó la conexión al comprobar los certificados…
   servidor caído o saturado») cuando su TLS fue fino.
   **Verificación contra el clasificador de la 1.0.12 (el código
   ya entregado, ejecutado sobre ese registro real): familia
   «tarjeta», causa = la línea del CreateFile, jamás TLS ni
   servidor.** El matiz «en uso» lo ataja además la capa de
   ciclo de vida antes de lanzar (barrido del huérfano propio;
   aviso «Otro OpenVPN está usando la tarjeta…» si el que la
   sujeta es ajeno). El caso quedó como test de regresión en
   `tests/test_v1012.py`
   (`test_clasificador_registro_real_1131_tap_ocupada`, añadido
   tras la entrega: corre en local, 30/30, y correrá en la
   próxima CI; el instalador entregado no cambia).
4. **El «Código de salida de OpenVPN: 0» de ese mismo intento
   (defecto de captura de la 1.0.11, fuera de alcance ya):** en
   el código de la 1.0.11 ese rótulo literal NO existe — el
   código solo viajaba en `datos["codigo_salida"]` y el detalle
   pintado eran las líneas del registro—, así que el 0 no sale
   de una lectura directa del proceso muerto en la rama de
   muerte (esa lee `returncode` tras `poll()`). Los mecanismos
   compatibles con un 0 junto a un registro fatal son los del
   propio defecto de ciclo de vida de la 1.0.11: (a) la rama de
   TIMEOUT, que terminate()a el proceso ella misma y reporta el
   código de SU terminación, no el de la muerte real; y (b) los
   intentos simultáneos compartiendo el global `_PROCESO` y el
   MISMO archivo de registro: la app podía estar midiendo el
   proceso de UN intento (terminado en 0 o aún vivo) mientras el
   registro visible lo escribía OTRO. No es reproducible desde
   el código sin su PC; queda anotado. En la 1.0.12 el código se
   lee del MISMO proceso lanzado, en la misma rama que detecta
   su muerte, con un solo intento posible y cierre verificado
   en el finally: ambas vías quedan cerradas por diseño.

## 6. Verificación

- Local (sin Qt, límite conocido de esta VM): subconjunto
  v1010+v1011+v1012, 66/66; comparación de la suite completa
  contra el árbol pristine: los mismos 27 fallos de entorno
  (libEGL) con y sin cambios — cero regresiones locales.
- **CI de Windows (run 45650309495) SUCCESS: suite 307/307**
  (278 de la 1.0.11 + 29 nuevos de test_v1012.py: protocolo del
  tubo byte a byte contra un servicio falso con kernel32
  sustituido —mensaje exacto en UNA escritura, PID y errores
  Win32/propios—, clasificador con el registro REAL de rutas de
  la Toughbook, ciclo de vida sin huérfanos con procesos falsos
  —excepción, doble clic, timeout, cierre—, barrido que solo
  cierra propios, puerta previa y contenido del instalador).
  La puerta de parseo con el openvpn.exe REAL se mantiene y
  pasó (el perfil generado llegó a la fase de red sin «Bad
  backslash»). Registro en `build-nube-v1012/`.
- Instalador: **Instalador-AntivirusHogarPC-1.0.12.exe**,
  45,228,393 bytes, MD5 `7419297d38bd508feeabc5c1331efd35`,
  SHA-256 `7431744cc083ef4ea27636b09f00db5174abaea1a64be5ee47293a665f15561e`.
  Zip: AntivirusHogarPC-Instalador-v1.0.12.zip, 44,719,027
  bytes, MD5 `e99e24416d84bb105051cdda9ee53eb5`.
- Canal Drive EN SITIO (mismos IDs): exe
  `1zmtcu-NL-PvCbGisbAXbFwVwyBlI5_ql` → «…-1.0.12.exe», zip
  `1ZHiCO9lInsLv6GJBCdCj6GtTMjGf6hTG` → «…-v1.0.12.zip»,
  version-pc.json `1Kfd_pELWJhp37fO1iaERdSIzpRkAqK4R` (versión
  1.0.12, URL del exe con `&confirm=t`, SHA-256 nuevo). Los tres
  verificados: anyoneWithLink=reader, trashed=false, tamaños y
  MD5 coincidentes con lo compilado.
- Copia visible NUEVA: «INSTALADOR Antivirus Hogar PC
  v1.0.12.zip», ID `1fQmyY-jpIPmu-SFcE73MHn8mTx9et4hK`
  (anyoneWithLink=reader, MD5 verificado). La copia visible de
  la 1.0.11 (`1m1LJZ05ND8Y4BE1b0M0esdi9agEhP4s4`) quedó en la
  papelera (trashed=true verificado).
- **PUERTA FINAL ANÓNIMA SUPERADA** con el código real de la
  app (`build-nube-v1012/puerta-final.py`): desde 1.0.11 OFRECE
  la 1.0.12; desde 1.0.12 «al día»; descarga completa por la URL
  del JSON con SHA-256 válido; corte forzado a 15,000,000 B y
  reanudación con SHA-256 válido.

## 7. Honestidad (lo no probado)

- La delegación REAL del Interactive Service (que el servicio
  acepte el perfil en %LOCALAPPDATA% con el usuario en el
  grupo), el posible cierre de sesión único tras la instalación,
  la reserva elevada con su UAC, la contienda real por la TAP y
  el túnel CON rutas solo se prueban en su Toughbook al instalar
  desde el botón de su 1.0.11 y darle «Conectar»: ver la IP
  pública cambiar de verdad. La instalación silenciosa del MSI
  tampoco se ejecuta en una Windows real en CI (se empaqueta y
  se verifica).
- Si el adaptador quedara «clavado» tras una terminación dura
  (ERROR_GEN_FAILURE sin ningún proceso sujetándolo), la
  reparación es guiada y manual (deshabilitar/habilitar la TAP
  con paso elevado visible), nunca en silencio: no se automatizó
  en esta versión.
