# INVESTIGACIÓN — Fallo VPN de la v1.0.10: «no respondió o cortó la conexión» con TODOS los servidores + estado falso «CONECTADA»

Fecha: 2026-11-25. Disparador: foto del usuario (09:29 EST) probando la
v1.0.10 en su Toughbook CF-54. Solo investigación: no se construyó nada.

## Lo que muestra la foto (leída directamente)

- Red y VPN → VPN Gate. IP pública: 172.58.131.250 (rango de T-Mobile:
  su conexión es el hotspot del iPhone).
- Rótulo: «VPN: CONECTADA a un servidor» + botón rojo «Desconectar VPN»
  habilitado.
- Error bajo la lista: «El servidor vpn344602886 no respondió o cortó la
  conexión. Suele ser un servidor apagado o saturado: elige otro de la
  lista e inténtalo de nuevo.» (servidor #76, Japan, 56 Mbps, ping 7 ms,
  93 sesiones).
- El usuario confirma: pasa con CUALQUIER servidor.

## 1. De dónde sale ese mensaje (exacto, en el código)

`antivirus_hogar_pc/winapi/vpn_win.py`, `conectar_openvpn()`,
líneas 537–559. El bucle de espera (45 s) vigila el proceso:

- Si la interfaz de gestión dice `CONNECTED,SUCCESS` → éxito.
- **Si el proceso openvpn.exe TERMINA por sí solo antes de confirmar
  el túnel** (`_PROCESO.poll() is not None`) → se lee la causa del log
  con `_causa_del_registro()` y se clasifica SOLO por esa línea:
  - contiene «auth» → mensaje de autenticación;
  - contiene «tun/tap» o «tap» → mensaje de tarjeta TAP;
  - **cualquier otra cosa (o causa vacía) → el mensaje de la foto**
    («no respondió o cortó la conexión… servidor apagado o saturado»).

Consecuencias probadas por el código:

- El mensaje de la foto **NO significa** «servidor apagado o saturado».
  Significa únicamente «openvpn.exe se cerró solo y la línea de causa
  elegida no traía ni "auth" ni "tap"». Un servidor muerto de verdad
  NO produce este mensaje: con los perfiles de VPN Gate (proto tcp en
  el 94 % de la lista, `resolv-retry infinite`), OpenVPN reintenta sin
  salir, y la app cae en su OTRO mensaje, el de timeout a los 45 s
  («el túnel no se confirmó a tiempo»). Que salga el de la foto indica
  **error FATAL local, al arrancar o al inicio de la negociación**,
  idéntico para todos los servidores.
- La causa real SÍ se calcula (`detalle`), pero **la pantalla nunca la
  muestra**: `modules/net/page.py::_al_conectar()` pinta solo
  `r.mensaje`; el `detalle_tecnico` no se usa en todo el flujo VPN de
  la página (solo se usa en el detalle de Wi-Fi). El informe de la
  v1.0.10 decía «errores con causa REAL… con la línea real en el
  detalle» — el detalle existe, pero viaja invisible para el usuario.
  Donde sí queda: el registro de actividad (ver §5).
- `_causa_del_registro()` devuelve UNA sola línea (máx. 300 caracteres)
  elegida por una lista de prioridades (auth_failed → cannot open
  tun/tap → tun/tap → tls error → … → fatal error → error). Si la
  línea elegida no representa la causa (p. ej. un «TLS error» temprano
  tapa un error posterior), la clasificación también sale mal.

## 2. Por qué dice «CONECTADA» a la vez que todo falla (bug probado)

Cadena completa, con tres eslabones débiles:

1. `modules/net/servicios_red.py::estado_vpn()` (líneas 365–376):
   `conectada = hay_tunel_openvpn() OR estado_openvpn().conectado`.
2. `vpn_win.py::procesos_openvpn()` (líneas 131–149): cuenta como
   «proceso del motor» **cualquier proceso cuyo nombre contenga la
   subcadena «openvpn»** — eso incluye `openvpn-gui.exe` (si el GUI
   está abierto) y `openvpnserv.exe`/`openvpnserv2.exe` (el servicio
   interactivo/de OpenVPN, residente siempre tras instalar el MSI).
   No exige que sea el `openvpn.exe` de un túnel, ni mira su línea de
   comandos, ni la TAP, ni rutas. En una PC con OpenVPN recién
   instalado, esta detección puede dar «hay túnel» **siempre**.
3. `vpn_win.py::estado_openvpn()` (líneas 455–479): si la interfaz de
   gestión no confirma, cae al respaldo «proceso vivo + sesión
   anotada» → conectado. Y la sesión (`openvpn_sesion.json`) se guarda
   **al lanzar el intento, antes de confirmar nada** (líneas 533–535):
   durante cualquier intento en curso también dice «conectado».

La foto lo confirma por un detalle: el rótulo dice «CONECTADA a **un
servidor**», que es el literal por defecto de
`page.py::_estado_vpn_visto()` cuando `vpn_estado.json` NO tiene
hostname — y ese archivo solo se escribe tras un éxito confirmado
(`servicios_red.py::_guardar_estado_vpn`). Es decir: **no había
ningún éxito guardado; el «conectada» salió solo de la detección por
nombre de proceso**. Además, tras un intento fallido la página solo
refresca el interruptor si `r.ok` (`_al_conectar`), así que el rótulo
falso ni siquiera se corrige al fallar. El botón rojo «Desconectar
VPN» se habilita con ese mismo dato falso.

Bug hermano: en la rama de TIMEOUT (45 s), `conectar_openvpn()`
devuelve fallo **sin matar el proceso ni borrar la sesión**: openvpn
queda reintentando en segundo plano para siempre; si conecta después,
hay un túnel que la app dijo que falló (y más leña para el
«CONECTADA» fantasma).

## 3. Auditoría del perfil .ovpn (con la lista REAL de hoy)

Prueba hecha desde esta VM (2026-11-25 ~09:40 EST):

- Lista real de VPN Gate descargada (por HTTP; el endpoint HTTPS
  principal cortó la conexión también desde aquí, como ya pasaba en
  la 1.0.3): 96 servidores parseados con el propio `parsear_csv_vpngate`
  de la app. `vpn344602886` **ya no está en la lista** (rotación normal
  de VPN Gate): no se puede reproducir ese servidor exacto; se usaron
  equivalentes actuales.
- Los 96 perfiles son el perfil canónico que genera SoftEther:
  `dev tun`, `proto tcp` (90) / `proto udp` (6), `remote <IP> <puerto>`
  (443, 995 y puertos altos variados — el parseo de puerto/proto del
  CSV es correcto), `cipher AES-128-CBC` + `data-ciphers AES-128-CBC`
  + `auth SHA1`, CA incrustada (ISRG Root X1), `<cert>`/`<key>` dummy.
  **Sin** comp-lzo, sin fragment, sin remote-cert-tls: ninguna
  directiva incompatible con OpenVPN 2.7.9.
- `preparar_perfil_vpngate()` apenas toca el perfil: quita
  auth-user-pass/management/log propios, añade
  `auth-user-pass "<ruta credenciales>"` y `data-ciphers-fallback`
  solo si falta `data-ciphers` (en los perfiles actuales no falta:
  no se añade). Las credenciales «vpn»/«vpn» son las correctas de
  VPN Gate.
- Alcance TCP verificado desde la VM: `public-vpn-192`
  (219.100.37.209:443) y `vpn445617380` (47.153.119.84:1841)
  aceptan conexión TCP. Los servidores equivalentes están vivos.
- **No reproducible fuera de su Windows:** no hay binario openvpn en
  esta VM ni paquete instalable (apt sin el paquete), así que el
  handshake real no se pudo correr aquí; y TAP/servicio interactivo/
  UAC son comportamiento exclusivo de su Windows 10 (el INFORME-V1010
  §7 ya admitía que ni la instalación silenciosa del MSI ni el túnel
  real se probaron nunca en una Windows real).

Conclusión del §3: el perfil NO es el sospechoso. Es el mismo que
VPN Gate entrega para OpenVPN GUI y que funciona en clientes
normales. Lo que la app hace distinto de un cliente normal es:
lanzar openvpn.exe ella misma, sin elevar, confiando en el servicio
interactivo para TAP/rutas — y ahí es donde un fallo es GLOBAL.

## 4. Causas probables, ordenadas por evidencia

**#1 — Fallo local de OpenVPN al abrir el dispositivo de túnel o al
delegar en el servicio interactivo, con una línea de log que esquiva
el clasificador.** Es lo único coherente con «muere el proceso +
todos los servidores + mensaje genérico»:
- Si el log trajera «Cannot open TUN/TAP», la app mostraría su
  mensaje de TAP — no fue el caso. Pero OpenVPN **2.7.x prefiere el
  driver DCO** (OpenVPN Data Channel Offload) cuando está presente,
  y sus errores de dispositivo no tienen por qué contener «tap»;
  igual para un fallo del pipe con el servicio interactivo
  («interactive service») si este no quedó corriendo.
- Por qué podría estar mal el servicio/TAP en su PC: el instalador
  corre `msiexec /i … /quiet /norestart` sin parámetros extra
  (`packaging/instalador.iss::InstalarOpenVPN`) y solo verifica que
  `openvpn.exe` exista después. Si msiexec devolvió **3010/1641
  (reinicio pendiente)**, con `/norestart` el driver puede quedar a
  medio registrar hasta reiniciar — y nadie le pidió reiniciar.
  Nadie verificó en su PC: servicio interactivo corriendo, TAP
  presente, ni el código concreto de msiexec (quedó en
  `openvpn-instalacion.txt`).

**#2 — Causa real presente en el log pero invisible/mal clasificada.**
Con el clasificador actual, líneas fatales reales como «VERIFY
ERROR» (certificado), «Options error» o «Exiting due to fatal error»
caen todas en el mensaje genérico. Subcaso: si el log quedó vacío o
ilegible, causa = "" y también sale el genérico. Es seguro que, sea
cual sea la causa #1, este defecto de clasificación+visibilidad está
presente y es el que convierte un error diagnosticable en «elige
otro servidor».

**#3 — Error de opciones con lo único que la app añade: la ruta de
credenciales.** Su usuario de Windows es «NEW USER» (con espacio), y
la línea queda `auth-user-pass "C:\Users\NEW
USER\AppData\Local\AntivirusHogarPC\vpn\vpngate-credenciales.txt"`.
Va entrecomillada (forma estándar y debería valer), pero es idéntica
en todos los intentos y un «Options error» ahí mataría el proceso al
arrancar con cualquier servidor. Se confirma o se descarta con una
sola línea del log.

**#4 — Su red (hotspot de iPhone / T-Mobile) corta o filtra.** Puede
empeorar la conexión a puertos altos, pero produce reintentos y el
mensaje de timeout de la app, NO la muerte del proceso: no explica
el mensaje de la foto. Factor secundario, no la causa de este fallo.

**Descartado:** servidores caídos en general (falla con todos y los
equivalentes responden por TCP desde aquí), el perfil .ovpn (auditado
arriba), las credenciales vpn/vpn (son las de VPN Gate; un AUTH_FAILED
además daría el mensaje de autenticación), y el parseo del CSV
(verificado con la lista real: hostname/IP/puerto correctos).

## 5. Qué mirar en SU PC (un archivo lo decide)

Tras UN intento de conexión, en este orden:

1. **`C:\Users\NEW USER\AppData\Local\AntivirusHogarPC\vpn\openvpn-conexion.log`**
   — el registro COMPLETO de OpenVPN del último intento (la app lo
   borra al empezar cada intento: vale solo el último). Pedirle las
   últimas ~15 líneas. Líneas decisivas: `Cannot open TUN/TAP`,
   `ovpn-dco` / `Data Channel Offload`, `interactive service`,
   `AUTH_FAILED`, `Options error`, `VERIFY ERROR`, `TLS Error`,
   `Exiting due to fatal error`.
2. **`C:\Users\NEW USER\AppData\Local\AntivirusHogarPC\actividad.jsonl`**
   — la entrada del intento trae «Detalle técnico: …» con la única
   línea que el clasificador eligió.
3. **`C:\Program Files\Antivirus Hogar PC\openvpn-instalacion.txt`** —
   el código que devolvió msiexec al instalar OpenVPN (3010/1641 =
   reinicio pendiente: sospechoso #1).

La app SÍ guarda la causa real (log completo + línea en actividad),
así que el dato existe en su PC; el bug es que la pantalla no lo
enseña y el mensaje lo sustituye por un texto equivocado.

## 6. Plan concreto para la v1.0.11

1. **Estado honesto:** «conectada» SOLO si la interfaz de gestión de
   la sesión dice CONNECTED,SUCCESS. Eliminar `hay_tunel_openvpn()`
   por subcadena como prueba de túnel (si se conserva un respaldo
   tras reapertura: nombre exacto `openvpn.exe` + línea de comandos
   con el perfil de la sesión + TAP activa). La sesión se marca
   «conectando» al lanzar y solo pasa a «conectada» al confirmar.
   Refrescar el interruptor también tras un fallo. En timeout,
   matar el proceso y borrar la sesión (nada de túneles huérfanos).
2. **La causa real, en pantalla:** mostrar `detalle_tecnico` bajo el
   mensaje en la propia página. El texto «apagado o saturado» solo
   para causas de red/TLS de verdad. Ampliar el clasificador: DCO/
   device, interactive service/pipe, options error, verify error;
   si la causa viene vacía, decirlo («OpenVPN se cerró sin dejar
   registro») en vez de inventar la del servidor.
3. **Registro por intento:** no borrar `openvpn-conexion.log` al
   empezar (renombrar con fecha/hora y rotar), y copiar a
   actividad.jsonl las últimas líneas completas del log, no una
   sola línea de 300 caracteres elegida por prioridad.
4. **Puerta previa del motor:** antes de conectar, usar el ya
   existente `diagnostico_openvpn()` (exe, servicio interactivo,
   TAP): si falta algo, mensaje accionable en vez de un intento
   condenado. Lanzar con `--windows-driver tap-windows6` explícito
   (TAP probada de siempre) y, si el intento muere con error de
   dispositivo, reintento automático una vez con el otro driver.
5. **Instalador:** si msiexec devuelve 3010/1641, avisar de que hay
   que reiniciar para que la tarjeta quede lista (en vez de
   `/norestart` silencioso y a otra cosa); tras instalar, verificar
   y anotar en `openvpn-instalacion.txt` el estado del servicio
   interactivo y de la TAP (sc query + Get-NetAdapter), no solo la
   presencia de openvpn.exe.
6. **Prueba que falta (la de verdad):** con el log del §5 de su
   Toughbook en la mano, reproducir ESA línea de error y verificar
   la 1.0.11 contra ella antes de entregar; el túnel real solo se
   puede cerrar en su PC, pero esta vez con el error real a la
   vista en la propia pantalla si algo falla.

---

# SEGUIMIENTO — 2026-11-25 (tarde): msiexec = 0 y CERO log

Datos nuevos del usuario (su Toughbook, tras la primera ronda):

1. `openvpn-instalacion.txt`: SoftEther retirado (servicio +
   driver, pnputil código 0); **msiexec de OpenVPN código 0** —
   instalado limpio, NO 3010/1641. **El sospechoso «reinicio
   pendiente / TAP a medio registrar» del §4-#1 queda DESCARTADO.**
   Verificación del instalador: openvpn.exe presente en
   `C:\Program Files\OpenVPN\bin\openvpn.exe`.
2. Su `actividad.jsonl`: 9 intentos OpenVPN (JP/KR/RU/TH), todos
   con el mensaje genérico y **SIN «Detalle técnico»** — es decir,
   `_causa_del_registro()` devolvió "" en todos: el log estaba
   vacío o no existía al leerlo.
3. El usuario fue a la carpeta y lo confirmó a ojo:
   **`openvpn-conexion.log` NO EXISTE**, aunque
   `vpngate-activo.ovpn` y `vpngate-credenciales.txt` SÍ se
   escribieron hoy en esa misma carpeta.
4. Línea extra en su registro, tipo «openvpn»: «el chequeo no
   pudo con ninguna fuente oficial (1 fallos)».

## A. El lanzamiento, exacto (código)

`_lanzar_openvpn()` (vpn_win.py L348–356) + `conectar_openvpn()`
(L508–535). Argumentos COMPLETOS que recibe openvpn.exe:

```
openvpn.exe --config <…\vpn\vpngate-activo.ovpn>
            --management 127.0.0.1 <puerto libre>
            --log-append <…\vpn\openvpn-conexion.log>
```

- Nada más: SIN `--windows-driver` (queda el de por defecto de
  2.7: win-dco, con tap-windows6 de reserva), SIN `--service`,
  SIN `--verb`/`--mute` propios (el perfil trae `verb 3`), SIN
  `--auth-user-pass` en la línea de comandos (va DENTRO del .ovpn,
  añadido por `preparar_perfil_vpngate()` como
  `auth-user-pass "C:\Users\NEW USER\…\vpngate-credenciales.txt"`,
  entrecomillado).
- Proceso: `subprocess.Popen(argumentos, cwd=<carpeta vpn>,
  stdout=DEVNULL, stderr=DEVNULL, creationflags=CREATE_NO_WINDOW)`.
  Lista de argumentos (no cadena): en Windows, subprocess la
  convierte con list2cmdline y entrecomilla cada ruta con
  espacios («Program Files», «NEW USER») correctamente. La app
  corre SIN elevar, con el token normal del usuario, confiando en
  el servicio interactivo para lo privilegiado.
- El orden interno descarta salidas tempranas: los retornos por
  «sin hostname / exe no encontrado / perfil vacío» ocurren ANTES
  de escribir archivos. Que el perfil y las credenciales de hoy
  existan prueba que el flujo llegó hasta lanzar el proceso.
- **La app nunca lee el código de salida del proceso**: vigila
  `poll() is not None`, pero descarta `returncode`. Un exit 1 de
  «Options error» y un crash del cargador de Windows
  (0xC0000135, DLL no encontrada) son indistinguibles para ella.

## B. Qué muertes dejan CERO log (discriminado)

openvpn.exe abre su `--log-append` DESPUÉS de parsear TODAS las
opciones (línea de comandos + archivo de configuración). Por
fases:

- **Fase 0 — el proceso ni arranca (cargador de Windows):** DLL
  ausente/corrupta junto al exe, exe bloqueado. Exit NTSTATUS
  instantáneo, cero log, todo a la nada (DEVNULL). Poco probable
  con MSI código 0, pero la app no puede descartarlo porque no
  guarda el código de salida.
- **Fase 1 — error fatal de OPCIONES durante el parseo:** el
  mensaje («Options error: …») sale por stderr ANTES de que el
  log se abra → DEVNULL → cero log. Es la fase que mejor explica
  el cuadro completo. Sospechosos: no el cuerpo del perfil
  (re-auditado hoy desde el CSV real de VPN Gate: solo dev tun,
  proto tcp, remote, cipher AES-128-CBC, data-ciphers
  AES-128-CBC, auth SHA1, resolv-retry infinite, nobind,
  persist-key, persist-tun, client, verb 3 + bloques
  ca/cert/key — todo válido en 2.7.9), sino lo que la APP añade:
  la combinación `--management`/`--log-append` de su línea de
  comandos y la línea `auth-user-pass "<ruta con espacios>"`
  dentro del perfil.
- **Fase 2 — ya con el log abierto:** TODO lo demás SÍ deja
  línea: «Cannot open TUN/TAP», errores DCO, errores del pipe
  del servicio interactivo, TLS, AUTH_FAILED, «Exiting due to
  fatal error». **Conclusión dura: un fallo de TAP/DCO/servicio
  NO explica que no exista el archivo.** Si el log no nació, la
  muerte fue en fase 0 o fase 1.
- Subcaso fase 1: si openvpn no pudiera CREAR el propio archivo
  de log (ruta/permiso), ese error también saldría por stderr y
  tampoco habría log; la carpeta es del propio usuario y la app
  escribió en ella, así que es el subcaso menos probable.

¿Dónde más puede quedar el error en Windows? Visor de eventos →
Registros de Windows → Aplicación (un CRASH de openvpn.exe
quedaría como Error de aplicación/WER, ID 1000/1001; el servicio
interactivo anota lo suyo ahí como OpenVPNServiceInteractive).
La carpeta de logs de OpenVPN GUI
(`C:\Users\NEW USER\OpenVPN\log\`) NO aplica: la app no usa el
GUI. El log del servicio automático
(`C:\Program Files\OpenVPN\log\openvpnserv.log`) solo registra
conexiones que lanza ESE servicio, no esta.

## C. Qué garantiza (y qué no) el msiexec código 0

- Nuestro instalador corre el MSI SIN ADDLOCAL
  (`msiexec /i "…" /quiet /norestart`, instalador.iss L237): se
  instalan las features por defecto del MSI oficial 2.7.9-I002
  (núcleo, GUI, servicio interactivo y servicio automático,
  drivers TAP-Windows6 y win-dco). Código 0 = la transacción MSI
  terminó bien y openvpn.exe quedó (verificado).
- Código 0 NO garantiza: que el servicio
  OpenVPNServiceInteractive esté CORRIENDO ahora (registrado ≠
  en marcha; nadie lo comprobó en su PC — `diagnostico_openvpn()`
  lo mira con `sc query`, pero la app nunca lo usó como puerta
  antes de conectar), ni que el adaptador esté enumerado en ese
  momento (en 2.7 los adaptadores DCO se generan «on demand»;
  el TAP-Windows6 sí debería verse en ncpa.cpl como
  «TAP-Windows Adapter V9»). Ojo: por §B, aunque servicio o
  adaptador faltaran, eso produciría líneas EN el log — agrava
  el cuadro pero no explica el cero log.

## D. La línea del actualizador es RUIDO (con evidencia)

`openvpn_update.chequear()`: si las fuentes oficiales no
devuelven versión, anota ese mensaje y TERMINA — en esa rama no
descarga nada, no ejecuta msiexec y no toca el motor instalado
(aplicar un pendiente verificado es otra función y no había
pendiente). Su internet es el hotspot del iPhone y las fuentes
son openvpn.net/GitHub: el chequeo falló de red, sin relación
mecanística con la muerte del proceso al conectar. (Única
coincidencia: confirma que su red corta algunas conexiones
HTTPS, ya sabido y secundario según §4-#4.)

## E. Causas que quedan vivas, ordenadas

1. **Muerte en fase 1 (error de opciones al parsear, invisible
   por DEVNULL y porque el detalle nunca se pinta).** Única que
   explica a la vez: todos los servidores, muerte rápida, cero
   log, cero detalle técnico. Dentro de ella, lo añadido por la
   app es el sospechoso; el perfil canónico quedó re-auditado.
2. **Muerte en fase 0 (el exe no llega a correr: cargador/DLL).**
   Misma firma observable que la 1; solo se separa de ella con
   el código de salida o corriendo el exe a mano. Menos
   probable con MSI 0.
3. **Servicio interactivo parado o adaptador ausente:** sigue
   sin verificar en su PC y hay que comprobarlo, pero por §B
   NO explica por sí solo el cero log; quedaría como segundo
   fallo detrás del primero.
4. Sigue descartado: servidores, perfil, credenciales, red del
   hotspot como causa de ESTE mensaje, y ahora también el
   reinicio pendiente (msiexec 0) y el actualizador (ruido, §D).

## F. LA prueba que lo decide (paso único para el usuario)

Correr openvpn.exe A MANO, en una ventana de comandos normal
(sin administrador, las mismas condiciones de la app), con el
perfil que la app ya dejó escrito y SIN `--log-append`, para
que el error salga en la ventana en vez de perderse:

```
"C:\Program Files\OpenVPN\bin\openvpn.exe" --config "C:\Users\NEW USER\AppData\Local\AntivirusHogarPC\vpn\vpngate-activo.ovpn"
```

(una sola línea; las comillas cubren los espacios de
«Program Files» y de «NEW USER»). Tres desenlaces posibles y
cada uno decide: sale «Options error» y se cierra → causa 1,
con el texto exacto; avanza y muere con línea de TAP/DCO/
servicio → esa línea es la causa real; llega a «Initialization
Sequence Completed» → OpenVPN está sano y el fallo está en
CÓMO lo lanza la app. Riesgos, dichos claros: la prueba SÍ
intenta conectar con un servidor de voluntarios — si lo logra,
su tráfico sale por ese servidor mientras la ventana siga
abierta (nada de banca ni cuentas personales durante la
prueba) y se cierra con Ctrl+C o cerrando la ventana, lo que
limpia las rutas; si a los ~60 s sigue reintentando sin morir,
Ctrl+C y reportar las últimas líneas (eso también discrimina:
proceso vivo reintentando ≠ comportamiento dentro de la app).

Alternativa si la prueba manual se le hace frágil: abrir
ncpa.cpl y decir si aparece «TAP-Windows Adapter V9» (y/o
«OpenVPN Data Channel Offload»), y en services.msc si
«OpenVPN Interactive Service» está en ejecución. Si falta el
adaptador TAP pese al msiexec 0, la feature de driver no quedó
enumerada; si el servicio está parado, hay que arrancarlo y
reintentar una vez desde la app.

---

# CIERRE DEL DIAGNÓSTICO — 2026-11-25: CAUSA CONFIRMADA

La prueba manual del §F del seguimiento se hizo y decidió todo.

## La salida exacta del usuario (su Toughbook, a mano, sin la app)

```
"C:\Program Files\OpenVPN\bin\openvpn.exe" --config "C:\Users\NEW USER\AppData\Local\AntivirusHogarPC\vpn\vpngate-activo.ovpn"

2026-11-25 10:54:06 DEPRECATED OPTION: --persist-key option ignored. Keys are now always persisted across restarts.
Options warning: Bad backslash ('\') usage in C:\Users\NEW USER\AppData\Local\AntivirusHogarPC\vpn\vpngate-activo.ovpn:221: remember that backslashes are treated as shell-escapes and if you need to pass backslash characters as part of a Windows filename, you should use double backslashes such as "c:\\openvpn\\static.key"
Use --help for more information.
```

(y el proceso terminó ahí: no hubo ni una línea más).

## 1. La línea 221 ES la línea que añade la app (probado, reproducible)

- El perfil original de VPN Gate tiene **exactamente 221 líneas** y su
  línea 221 es la última, **vacía** (verificado hoy descargando la
  lista real y decodificando el `OpenVPN_ConfigData_Base64` de varios
  servidores: 221 líneas, línea 220 = `</key>`, línea 221 = vacía).
- `preparar_perfil_vpngate()` (vpn_win.py L263–298) elimina las
  líneas finales vacías (`while salida and not salida[-1].strip():
  salida.pop()`) y añade AL FINAL, en L295:
  `salida.append(f'auth-user-pass "{ruta_credenciales}"')`
  con la ruta Windows **con barras simples**, entre comillas.
- Reproducción con el código real de la app y un perfil real de hoy:
  el perfil generado tiene 221 líneas y **su línea 221 es**
  `auth-user-pass "C:\Users\NEW USER\AppData\Local\AntivirusHogarPC\vpn\vpngate-credenciales.txt"`.
  Es la ÚNICA línea con una ruta Windows que la app escribe en el
  perfil (el respaldo sin OpenVPN guarda el perfil crudo, sin esa
  línea; los argumentos `--config/--management/--log-append` van por
  argv, no por el parser de configuración, y no les afecta).

## 2. Por qué ese «warning» MATA el proceso (fuente oficial, v2.7.9)

En el código fuente oficial de OpenVPN 2.7.9
(`src/openvpn/options_parse.c`, `parse_line()`, L157–172): dentro de
un parámetro entrecomillado, una barra seguida de un carácter que no
sea `\`, `"` o espacio (aquí la primera es `\U` de `C:\Users`)
imprime el «Options warning: Bad backslash…» con el `msglevel` de la
llamada y **retorna 0 (la línea no se procesa)**. La cadena de
niveles lo convierte en salida inmediata:

- `openvpn.c` L208: `parse_argv(…, M_USAGE, …)`; `error.h` L107:
  `M_USAGE = M_USAGE_SMALL | M_NOPREFIX | M_OPTERR`.
- `add_option` de `--config` llama a `read_config_file()` con ese
  mismo nivel (options.c L5667); `parse_line()` solo limpia
  `M_OPTERR` (`msglevel &= ~M_OPTERR`), conserva `M_USAGE_SMALL`.
- `error.c` L371–374: si el flag trae `M_USAGE_SMALL`, tras imprimir
  llama a `usage_small()`, que imprime **«Use --help for more
  information.»** y hace `openvpn_exit(OPENVPN_EXIT_STATUS_USAGE)`.

Eso es EXACTAMENTE la salida del usuario, línea por línea (el aviso
`DEPRECATED OPTION: --persist-key` previo es del parseo normal de las
líneas anteriores: el proceso llegó vivo hasta la última línea del
perfil, la 221, y murió en ella). Y explica TODO el cuadro a la vez:

- **Muerte instantánea en fase 1 (parseo de opciones)**, antes de
  cualquier red: idéntica con los 9+ servidores (la línea es la
  misma en todos los intentos).
- **Cero log:** en la línea de comandos de la app, `--config` se
  procesa ANTES que `--log-append` y el proceso muere dentro del
  parseo del perfil; el archivo de log jamás se abre/crea (por eso
  `openvpn-conexion.log` no existe aunque el perfil sí se escribió).
- **Cero «Detalle técnico»:** no hay log que leer, `_causa_del_
  registro()` devuelve "" y la app cae en su mensaje genérico
  («servidor apagado o saturado») — que era falso de principio a fin.
- Quedan enterrados los sospechosos anteriores: TAP/DCO (ambos
  adaptadores presentes en su PC: «OpenVPN Data Channel» y
  «TAP-Windows Adapter V6»), servicio interactivo, msiexec
  (código 0), servidores, credenciales y la red del hotspot.

## 3. El arreglo exacto (mínimo)

En `preparar_perfil_vpngate()` (vpn_win.py L295), escapar la ruta al
escribirla, en la forma que manda la documentación oficial de
OpenVPN (man page, `doc/man-sections/generic-options.rst`:
«For example on Windows, use double backslashes to represent
pathnames: `secret "c:\\OpenVPN\\secret.key"`»; el propio mensaje
de error recomienda lo mismo):

```python
ruta_en_perfil = ruta_credenciales.replace("\\", "\\\\")
salida.append(f'auth-user-pass "{ruta_en_perfil}"')
```

El parser convierte cada `\\` en una sola `\` y el parámetro llega
íntegro a `fopen`, sin warning y sin salida. Alternativa también
válida y sin warning: barras hacia adelante
(`replace("\\", "/")`) — el parser no las trata como escape y las
API de archivo de Windows las aceptan; se elige la de barras dobles
por ser la forma literal de la documentación oficial. Añadir al
test de `preparar_perfil_vpngate` la aserción de que la línea sale
escapada (hoy el test de la v1.0.10, test_v1010.py L188–198, fija
justo lo contrario: exige la ruta con barras simples — ese test
hay que corregirlo, es parte de por qué el bug pasó la suite).

## 4. PLAN CERRADO de la v1.0.11

1. **LA CAUSA (arriba):** escapar la ruta de credenciales en
   `auth-user-pass` con barras dobles; corregir el test que fijaba
   las barras simples y añadir una guarda que reproduzca el perfil
   real de 221 líneas y verifique que la línea añadida no contiene
   ninguna `\` seguida de carácter no escapable.
2. **Estado honesto:** «conectada» SOLO con `CONNECTED,SUCCESS`
   real de la interfaz de gestión de la sesión. Fuera la detección
   por subcadena de procesos (`procesos_openvpn()` cuenta
   openvpn-gui/openvpnserv como túnel: de ahí salió el «CONECTADA
   a un servidor» falso de la foto). Sesión «conectando» al lanzar,
   «conectada» solo al confirmar; refrescar el rótulo también tras
   un fallo; en timeout, matar el proceso y borrar la sesión (sin
   túneles huérfanos).
3. **Nunca más un error invisible:** no lanzar openvpn.exe con
   stdout/stderr a DEVNULL sin red — capturar su salida (pipe o
   archivo de salida del arranque) y, si el proceso muere antes de
   que exista log, ESA salida es la causa. Guardar también el
   código de salida del proceso (`poll()` hoy se vigila pero el
   `returncode` se descarta).
4. **La causa real, en pantalla:** mostrar `detalle_tecnico` bajo
   el mensaje en la página de Red y VPN (hoy se calcula y no se
   pinta en todo el flujo VPN). El texto «apagado o saturado» solo
   para causas de red/TLS reales; clasificador ampliado (options
   error / bad backslash, DCO/device, interactive service, verify
   error) y, si la causa viene vacía, decirlo («OpenVPN se cerró
   sin dejar registro, código de salida N») en vez de inventar la
   del servidor.
5. **Log por intento, sin borrar:** no `os.remove()` del log al
   empezar; renombrar el anterior con fecha/hora y rotar (p. ej.
   conservar los últimos 5), y copiar a `actividad.jsonl` las
   últimas líneas completas del log/salida, no una sola línea de
   300 caracteres elegida por prioridad.
6. **Verificación antes de entregar:** suite con el test corregido
   + reproducción del fallo original (perfil real + ruta con
   espacios y barras simples muere; con el arreglo, el parseo pasa
   la línea 221) en la medida reproducible fuera de su Windows, y
   la prueba del túnel real en su Toughbook con la causa a la
   vista en pantalla si algo más fallara.

---

# PRUEBA v1.0.11 — 2026-11-25: el túnel SÍ abrió; fallaron las RUTAS (y un huérfano sujetó la TAP)

El usuario instaló la 1.0.11, le dio «Conectar» y fotografió la
pantalla. Lo primero que hay que decir: **las mejoras de la 1.0.11
funcionaron** — el rótulo dice «VPN: Desconectada» (nada de
«CONECTADA» falsa) y el detalle técnico real se ve en la propia
pantalla. Pero el titular pintado («OpenVPN no pudo abrir su
tarjeta virtual (TAP-Windows/DCO). Reinstala la app…») es FALSO
otra vez, por otra vía. Y una prueba manual elevada posterior
(11:33, hora de su PC) destapó un segundo problema: un proceso
huérfano sujetando el adaptador.

## 1. Qué pasó de verdad, línea por línea (foto 11:30:11, hora de su PC)

El detalle de la foto son las últimas 12 líneas del registro:

- `route.exe ADD 0.0.0.0 MASK 128.0.0.0 10.211.1.46` y
  `ADD 128.0.0.0 MASK 128.0.0.0 10.211.1.46`: son las DOS medias
  rutas /1 del `redirect-gateway def1` que empuja el servidor de
  VPN Gate (la forma de capturar todo el tráfico sin tocar la
  ruta por defecto original). La puerta del túnel es
  **10.211.1.46**: para intentar crear esas rutas, openvpn YA
  había completado el handshake TLS, recibido el PUSH_REPLY,
  abierto el adaptador y configurado su IP (las rutas se crean
  DESPUÉS de todo eso, en la fase final de la inicialización).
- `route addition failed using CreateIpForwardEntry: Access is
  denied. [status=5 if_index=60]`: **status=5 es el error 5 de
  Win32, acceso denegado** — crear rutas exige privilegios.
  `if_index=60` es el índice del adaptador virtual YA ABIERTO:
  la tarjeta existía y estaba operativa. El método IPAPI falló
  y el respaldo `route.exe` devolvió código 1 por lo mismo.
- Última línea: **`Initialization Sequence Completed`**. La
  inicialización terminó. En OpenVPN el fallo de rutas NO es
  fatal (hay registros públicos idénticos, línea por línea, en
  los que el proceso sigue conectado tras estos mismos errores):
  el proceso quedó, con toda probabilidad, VIVO con el túnel
  abierto.

Conclusión del §1: **el adaptador SÍ abrió, hubo handshake y el
túnel se inicializó. El único fallo es la creación de rutas por
falta de privilegios.** Y sin las dos rutas /1, el
`redirect-gateway` no se aplica: el tráfico del usuario NO sale
por la VPN (solo existiría la ruta a la subred del túnel). Túnel
«arriba» pero inútil para navegar con otra IP — por eso el
estado honesto no puede ser «conectada» a secas (ver §4).

¿Por qué sin privilegios? Porque la app lanza openvpn.exe con
`Popen` desde su proceso SIN elevar y SIN el Interactive
Service. El servicio solo delega privilegios en los procesos
que ÉL lanza (les pasa su tubo de servicio al nacer); un
openvpn lanzado por Popen no tiene tubo y hace las operaciones
privilegiadas en su propio proceso: abrir el dispositivo
TAP/DCO le salió (los ACL del dispositivo lo permiten), pero
CreateIpForwardEntry exige administrador → status=5.

## 2. Por qué la app lo dio por fallido y con ESE titular

Dos defectos encadenados, ambos en `vpn_win.py`:

**(a) El proceso terminó (o la app lo dio por terminado) durante
la espera, y la rama de «proceso muerto» es la única que
clasifica.** `conectar_openvpn()` solo produce ese titular
desde la rama `poll() is not None` (la de timeout devuelve otro
texto). La secuencia temporal aprieta: las rutas se crean ANTES
de «Initialization Sequence Completed» y el estado
CONNECTED,SUCCESS de la interfaz de gestión solo existe DESDE
ese instante; el bucle comprueba `poll()` ANTES que el estado
en cada vuelta de ~2 s. Si el proceso salió en esa ventana (o
la lectura de gestión llegó siempre un paso por detrás de un
proceso que ya se iba), la app nunca vio el CONNECTED y trató
la inicialización completa como una muerte más. Lo que el
detalle NO trae —porque la foto muestra las últimas líneas del
LOG, no el código de salida— es la línea posterior a
«Initialization…» que lo cerraría; el código de salida viajaba
en `datos` pero la página no lo pinta. Pendiente de confirmar
con el `openvpn-conexion.log` completo de su PC; no cambia el
arreglo (§5), porque las rutas denegadas ya condenan el intento.

**(b) El titular salió de la SELECCIÓN de causa, no del
detalle.** `_causa_del_registro()` → `_elegir_causa()` recorre
`_PRIORIDADES_CAUSA` con el bucle de marcas por FUERA: gana la
primera MARCA de la lista que aparezca en CUALQUIER línea del
registro completo, antes de mirar las demás líneas. Las marcas
`tun/tap`, `tap-windows`, `ovpn-dco`, `data channel` van MUY
por encima de `error` — y las líneas de rutas solo casan con
`error`, la última prioridad. En un registro de inicialización
normal hay líneas informativas del adaptador (apertura del
dispositivo TAP-Windows/DCO) que contienen «tap»/«dco»: esa
línea INFORMATIVA se convirtió en «la causa», y
`_clasificar_fallo_openvpn()` mapea cualquier causa con «tap»
al titular de tarjeta virtual + «reinstala la app». El detalle
visible (las últimas 12 líneas, mejora de la 1.0.11) decía la
verdad; el titular, calculado sobre otra línea, la contradecía
en la misma pantalla.

## 3. DATO NUEVO (11:33): la prueba manual ELEVADA no pudo ni abrir el túnel

El usuario corrió a mano, como administrador, el mismo
`vpngate-activo.ovpn`. Handshake TLS OK (VERIFY OK, PUSH_REPLY
con ifconfig 10.211.1.17/10.211.1.18 y redirect-gateway def1;
su puerta local 172.20.10.1, el hotspot). Pero:

```
open_tun
CreateFile failed on tap-windows6 device: \\.\Global\{79BE79B2-…}.tap: General failure (ERROR_GEN_FAILURE) (errno=31)
create_adapter: could not talk to service: The handle is invalid. [6]
All tap-windows6 adapters on this system are currently in use or disabled.
Exiting due to fatal error
```

Interpretación:

- A las 11:33 el ÚNICO adaptador tap-windows6 **no se podía
  abrir**: el propio mensaje de OpenVPN da las dos opciones,
  «en uso o deshabilitado». Tres minutos antes, a las 11:30,
  ese mismo adaptador SÍ abrió (if_index=60, rutas intentadas
  sobre él) y el usuario lo había visto presente en ncpa.cpl
  en la ronda anterior → **«deshabilitado/dañado» queda
  descartado como explicación principal**; un adaptador
  deshabilitado no abre a las 11:30. Queda **«en uso»**: algo
  lo tenía abierto a las 11:33.
- `create_adapter: could not talk to service: The handle is
  invalid [6]` + `interactive service msg_channel=0`: ni
  siquiera el lanzamiento ELEVADO a mano usa el Interactive
  Service — sin tubo de servicio no pudo pedirle que creara/
  buscara otro adaptador y cayó al dispositivo existente, que
  estaba ocupado. (La elevación y el iservice son mecanismos
  DISTINTOS; a mano no se obtiene el segundo.)
- **Explicación más probable del ocupante: un openvpn.exe
  huérfano del intento de la app de las 11:30.** El proceso de
  las 11:30 abrió el adaptador y, como el fallo de rutas no es
  fatal (§1), lo esperable es que siguiera vivo sujetándolo.
  Que la app lo diera por fallido sin dejarlo cerrado es
  posible por las rutas de salida SIN limpieza de
  `conectar_openvpn()` (auditadas en el código de la 1.0.11):
  1. **Sin try/finally:** la limpieza existe solo en la rama
     de proceso-muerto (ya está muerto: nada que limpiar) y en
     la de timeout (terminate→wait→kill). Cualquier otra
     salida —una excepción dentro del bucle de espera la
     captura `seguro()` en servicios_red y la convierte en
     «fallo»— deja el proceso VIVO y sin dueño.
  2. **Sin guarda de un solo intento:** la página lanza cada
     «Conectar» en un QThread nuevo (`_lanzar` no comprueba si
     ya hay un trabajo en curso) y `conectar_openvpn()` usa el
     global `_PROCESO` y el MISMO archivo de sesión/perfil/
     registro para todos: un segundo clic sobrescribe el
     mango y el primer proceso queda inalcanzable para siempre
     (ni la desconexión puede encontrarlo: la sesión ya es del
     segundo).
  3. **Éxito o cierre de la app:** si el intento «conecta», el
     proceso queda vivo a propósito; si el usuario cierra la
     app (o la página) con un intento en curso, el hilo se
     despawnea (`_soltar_trabajos`) pero el openvpn hijo es un
     proceso independiente que SOBREVIVE sin que nadie lo
     cierre, sujetando la TAP.
  La desconexión actual solo lo rescataría por el respaldo
  bruto `terminar_procesos_openvpn()` (mata TODOS los
  openvpn.exe, también los ajenos) y solo si se pulsa
  «Desconectar» con la sesión detectable.
- Alternativa que no se puede excluir al 100 % sin su PC: que
  el adaptador quedara «clavado» tras una terminación dura
  (TerminateProcess del timeout) — el driver TAP-Windows puede
  quedar en un estado en el que CreateFile devuelve
  ERROR_GEN_FAILURE hasta deshabilitar/habilitar el adaptador
  o reiniciar. Ambas explicaciones exigen el mismo arreglo:
  control de ciclo de vida + verificación de adaptador libre
  (§5), y una acción de reparación del adaptador si está
  clavado sin proceso que lo sujete.

## 4. Arreglo del clasificador (reglas nuevas)

1. **Las líneas de ERROR mandan sobre las informativas:** al
   elegir causa se ignoran las líneas sin marca de error/
   fatal/warning (una línea de apertura de adaptador nunca
   puede ser «la causa» de un fallo). O, equivalente, la
   familia rutas/privilegios se evalúa ANTES que la de
   adaptador y con marcas propias.
2. **Familia nueva «rutas/privilegios»:** `route addition
   failed`, `route add command failed`, `CreateIpForwardEntry`
   + `Access is denied`/`status=5`/`requires elevation` →
   mensaje: «OpenVPN abrió el túnel pero Windows le negó
   crear las rutas (falta de privilegios): el tráfico no
   saldría por la VPN. No es la tarjeta ni el servidor: es
   cómo la app lanza OpenVPN; queda corregido lanzándolo a
   través de su servicio (o elevado).» NUNCA «tarjeta virtual»
   y nunca «reinstala la app» para esta familia.
3. **«Initialization Sequence Completed» + rutas fallidas:**
   estado honesto intermedio — «túnel abierto pero sin rutas:
   tu tráfico NO está saliendo por la VPN» — y la app debe
   bajar ese túnel limpiamente (SIGTERM por la interfaz de
   gestión y verificación de salida), no dejarlo vivo ni
   pintarlo como éxito ni como fallo de tarjeta.
4. La familia tarjeta queda SOLO para `Cannot open TUN/TAP`,
   `CreateFile failed on tap`, `All tap-windows6 adapters…`,
   errores DCO de apertura — cuando de verdad no se abrió.
5. Pintar también el **código de salida** del proceso en el
   detalle de la pantalla (ya viaja en `datos` y nadie lo ve).

## 5. VÍA ELEGIDA para la v1.0.12: lanzar a través del OpenVPN Interactive Service

**Qué hace el GUI oficial (documentación oficial del
Interactive Service, community.openvpn.net):** el GUI corre
como usuario normal; se conecta al tubo con nombre
`\\.\pipe\openvpn\service` del servicio
OpenVPNServiceInteractive (que corre con privilegios de
sistema) y le envía UN mensaje de arranque: tres cadenas
UTF-16 separadas por nulos —directorio de trabajo, opciones
de openvpn SIN argv[0], y el contenido de stdin—. El servicio
valida al usuario y las opciones, **lanza openvpn.exe COMO EL
USUARIO** conservando un tubo de servicio con él, y cuando
openvpn necesita una operación privilegiada (rutas, IP, DNS)
la pide por ese tubo y la ejecuta el servicio (que además
limpia si openvpn muere). La propia documentación recomienda
vigilar el proceso con la **Management Interface**: nuestro
`--management 127.0.0.1 <puerto>` viaja como una opción más,
así que **confirmar CONNECTED,SUCCESS y desconectar por
SIGTERM funcionan igual que hoy**. Detalles a respetar: el
stdout del proceso lanzado por el servicio va a NUL → hay que
pasar `--log-append` (ya lo hacemos); el servicio devuelve un
mensaje con el PID (o un mensaje de error con código Win32)
que hay que leer de la respuesta del tubo.

**Requisito de autorización (el punto que hay que resolver en
el instalador):** el servicio solo acepta configuraciones
fuera de su `config_dir` (registro HKLM\SOFTWARE\OpenVPN,
por defecto `C:\Program Files\OpenVPN\config`) si el usuario
pertenece a **Administradores** o al grupo de
`ovpn_admin_group` (**«OpenVPN Administrators»** por
defecto). Nuestro perfil vive en
`%LOCALAPPDATA%\AntivirusHogarPC\vpn` → fuera del config_dir.
Arreglo de UNA vez, en el instalador (que ya corre elevado):
crear el grupo si falta y **añadir al usuario actual a
«OpenVPN Administrators»**, anotándolo en
`openvpn-instalacion.txt`, y verificar que el servicio
interactivo está registrado y corriendo (sc query; si está
parado, arrancarlo en la instalación). Desde ahí, conectar no
necesita elevación ni muestra UAC nunca.

**Implementación:** cliente del tubo en Python con ctypes
(CreateFileW sobre `\\.\pipe\openvpn\service`,
SetNamedPipeHandleState a modo mensaje, WriteFile con el
mensaje completo en UNA llamada, ReadFile para el PID/error)
— sin dependencias nuevas. Sustituye a `_lanzar_openvpn()`
como vía principal; la sesión guarda el PID que devuelve el
servicio.

**Vía de RESERVA: lanzar openvpn.exe ELEVADO** (ShellExecuteEx
con verbo `runas`) si el tubo/servicio no responde o el
usuario no está autorizado. En la Toughbook del usuario la
elevación no muestra aviso (su cuenta eleva en silencio,
probado en la era SoftEther), así que la reserva es viable
allí; en otra PC mostraría un UAC por conexión — aceptable
como reserva, no como vía principal. La interfaz de gestión
sigue funcionando igual (es TCP local); la desconexión por
SIGTERM no necesita elevación. Descartada como principal
porque el proceso correría como administrador completo (el
iservice mantiene openvpn como usuario y solo delega las
operaciones concretas: mejor postura) y porque con otra
cuenta administradora distinta cambiarían perfil/entorno.

**Descartado: que la app entera exija administrador.**
Convertiría TODO el antivirus (escaneos, limpieza, bandeja,
actualizador) en un proceso elevado permanente por una sola
función: peor seguridad, fricción en cada arranque y no
arregla el ciclo de vida. Solo serviría como diagnóstico
puntual, no como diseño.

## 6. Plan concreto v1.0.12 (ciclo de vida incluido)

1. **Lanzamiento por iservice** (§5) con su cliente de tubo;
   reserva elevada si el servicio no está disponible; puerta
   previa con `diagnostico_openvpn()` ampliado: servicio
   interactivo corriendo, usuario en «OpenVPN
   Administrators», adaptador presente.
2. **Un solo intento a la vez:** guarda en la página (botones
   «Conectar» deshabilitados durante un intento) y en el motor
   (si ya hay sesión «conectando/conectada», el nuevo intento
   primero cierra la anterior limpiamente).
3. **Limpieza garantizada:** `conectar_openvpn()` con
   try/finally — TODA salida que no sea éxito confirmado cierra
   el proceso (SIGTERM por gestión → espera → terminate →
   kill, en ese orden) y verifica `poll()` antes de devolver;
   la sesión solo sobrevive en estado «conectada».
4. **Barrido previo de huérfanos PROPIOS:** antes de conectar,
   si hay openvpn.exe cuya línea de comandos contiene NUESTRO
   perfil (`vpngate-activo.ovpn`) o cuyo PID consta en una
   sesión anterior de la app, se cierra (gestión si responde;
   proceso si no) y se anota en actividad. Un openvpn AJENO
   (del GUI del usuario, con otro perfil) NO se mata: si la
   TAP está ocupada por un proceso ajeno, se dice en pantalla
   («otro OpenVPN está usando la tarjeta virtual: ciérralo o
   desconéctalo y vuelve a intentarlo»).
5. **Verificación post-cierre:** tras desconectar o fallar,
   comprobar y anotar: proceso muerto + adaptador libre. Si
   el adaptador sigue sin poder abrirse y NO hay proceso que
   lo sujete (adaptador clavado), ofrecer la reparación
   guiada: deshabilitar/habilitar el adaptador TAP-Windows
   (elevado, una vez) o reiniciar el equipo — nunca en
   silencio.
6. **Clasificador nuevo** (§4) + código de salida visible en
   pantalla + estado «túnel abierto sin rutas» tratado como
   en §4.3 (se baja limpio y se reporta como fallo de rutas,
   no como éxito ni como tarjeta).
7. **Instalador:** grupo «OpenVPN Administrators» + usuario
   añadido + servicio interactivo verificado/corriendo, todo
   anotado en `openvpn-instalacion.txt`; si el usuario se
   añade al grupo, avisar de que el primer uso puede requerir
   cerrar sesión una vez (la pertenencia a grupo se evalúa
   al iniciar sesión; el servicio la comprueba contra el
   token del llamante).

## 7. Qué se puede verificar en CI y qué no

**SÍ en CI (sin su Windows):**
- El protocolo del tubo contra un servicio FALSO: mensaje de
  arranque byte a byte (UTF-16, tres campos, una sola
  escritura), lectura del mensaje de PID y de los mensajes
  de error del servicio (códigos 0x20000000+ y Win32).
- El clasificador con ESTE registro real de la foto: rutas
  denegadas + Initialization Completed → familia
  rutas/privilegios, jamás tarjeta; y la selección de causa
  ignorando líneas informativas del adaptador.
- El ciclo de vida con procesos falsos: excepción en el
  bucle, segundo intento concurrente, timeout y cierre de
  app dejan CERO procesos y la sesión borrada; el barrido
  solo mata procesos con nuestro perfil/PID, nunca ajenos.
- La guarda de parseo de la 1.0.11 se mantiene (el perfil
  sigue pasando el openvpn.exe real), y el instalador: los
  comandos de grupo/servicio quedan fijados por test de
  contenido del script.

**NO en CI (solo en su Toughbook):**
- La delegación real del iservice (que las rutas se creen
  sin admin con su usuario en el grupo), el primer arranque
  tras añadirlo al grupo (puede pedir re-login), la reserva
  elevada en su política de UAC, la contienda real por la
  TAP con un huérfano y el desbloqueo del adaptador si está
  clavado. Como en las versiones anteriores: la prueba del
  túnel completo —esta vez con rutas y con la IP pública
  cambiando de verdad— se cierra en su PC.

---

## CIERRE v1.0.12 (2026-11-25, entregada)

La v1.0.12 se construyó con el plan de la §5–§6 de esta
investigación y quedó ENTREGADA el mismo día (INFORME-V1012.md):
lanzamiento por el Interactive Service con reserva elevada,
puerta previa con grupo «OpenVPN Administrators» y detección de
sesión sin refrescar, instalador que crea el grupo y verifica el
servicio (grupo_openvpn.ps1), un solo intento con limpieza
try/finally, barrido de huérfanos propios, verificación
post-cierre y clasificador nuevo (rutas antes que tarjeta; las
informativas nunca son causa). Suite CI 307/307 (run
45650309495 SUCCESS, a la segunda: la primera, 45649876905,
falló con 12 pruebas por UNA causa — la puerta previa bloqueaba
en duro al no detectar el adaptador TAP en el runner, donde
OpenVPN aún no está instalado al correr las pruebas; la
detección por nombre pasó a ser aviso, no bloqueo). Canal Drive
en sitio a 1.0.12 y puerta final anónima superada. Pendiente
honesto de siempre: la delegación real del servicio, el posible
re-login único y el túnel con rutas solo se prueban en su
Toughbook al instalar desde el botón de su 1.0.11.

---

# PRUEBA v1.0.12 — 2026-11-25: la propia app mata el intento en su primer segundo (SIGTERM por gestión)

La prueba de la 1.0.12 en la Toughbook REFUTÓ la conexión con un
patrón nuevo, probado con TRES registros reales de
`openvpn-conexion.log` fotografiados por el usuario. La causa está
en el código de la propia app, no en los servidores ni en la red.

## 1. La evidencia (tres registros reales, carpeta `vpn`)

- **12:44:45** (UDP, 27.130.33.137:1974): arranque, gestión
  escuchando en 127.0.0.1:64124, «TLS: Initial packet from
  [AF_INET]27.130.33.137:1974» — y EN EL MISMO SEGUNDO:
  «MANAGEMENT: Client connected from [AF_INET]127.0.0.1:64125» →
  «MANAGEMENT: CMD 'signal SIGTERM'» → «SIGTERM[hard,] received,
  process exiting».
- **12:47:47** (TCP, 110.163.142.88:5555): «TCP connection
  established» y en el mismo segundo gestión conectada (64180) →
  «CMD 'signal SIGTERM'» → salida.
- **12:50:29** (TCP, 113.23.60.86:995): idéntico — TCP
  established, gestión conectada (64201→64202), SIGTERM
  inmediato, salida.

En cada registro hay UNA SOLA conexión de gestión y su único
comando es el SIGTERM: la app ni siquiera llegó a enviar un
`state` en esos intentos. Los registros rotados de estos intentos
pesan 1–2 KB (muerte al nacer), frente a los 14 KB del intento de
las 12:17:56. El usuario confirmó que no tocó «Desconectar» ni
cerró la app. El titular de la app clasificó los tres como
«cortó la conexión al comprobar los certificados (error TLS):
servidor caído o saturado» — falso en los tres.

## 2. Quién envía el SIGTERM (auditoría completa, sospechosos en orden)

En TODO el código solo hay dos literales `signal SIGTERM`:
`winapi/vpn_win.py:1377` (en `_cerrar_proceso`, vpn_win.py:1364)
y `winapi/vpn_win.py:1731` (en `desconectar_openvpn`).

- **(d) Un segundo cliente de gestión vigilante: NO EXISTE.** El
  único otro comando que la app envía a la interfaz es `state`
  (`estado_openvpn`). Nadie envía SIGTERM «de sondeo».
- **(b) El barrido de huérfanos: EXONERADO por mecanismo.**
  `_barrido_huerfanos` (vpn_win.py:1464) corre ANTES del
  lanzamiento y mata por PID con `psutil.terminate()` =
  TerminateProcess: esa muerte no deja línea de gestión ni
  salida limpia («SIGTERM[hard,] received, process exiting» es
  la despedida ordenada de un SIGTERM por gestión). La firma del
  registro no es la del barrido.
- **(c) La guarda de un solo intento: EXONERADA.**
  `_cerrar_intento_previo` (vpn_win.py:1413) también corre antes
  del lanzamiento y apunta al puerto de la sesión ANTERIOR; el
  SIGTERM de cada registro llegó al puerto NUEVO de ese intento
  en su primer segundo.
- **`desconectar_openvpn` (1731): EXCLUIDO** — solo se alcanza
  desde los botones «Desconectar» (modules/net/page.py:697 y
  1051) y el usuario no los tocó.
- **EL REMITENTE: el `finally` de `conectar_openvpn`**
  (vpn_win.py:1705), que al no haber éxito confirmado llama a
  `_cerrar_proceso(proceso, puerto)` (vpn_win.py:1709–1710) y
  este envía el SIGTERM (vpn_win.py:1377). `cerrar_intento_en_curso`
  usa el mismo `_cerrar_proceso`, pero solo se dispara al
  destruirse la página o al salir la app — no fue el caso.

## 3. Por qué el finally saltó en el primer segundo: poll() declara muerto a un proceso vivo

El bucle de espera de `conectar_openvpn` comprueba PRIMERO
(vpn_win.py:1609) `proceso.poll() is not None`. Que el usuario
viera el titular TLS prueba que el bucle salió por esa rama (el
titular nace ahí, de `_mensaje_familia` sobre
`_analizar_registro`): una excepción habría llegado a la pantalla
como «No se pudo completar…» vía `seguro()`. Es decir: **poll()
declaró muerto al proceso en la primera iteración, con el
handshake recién empezado**.

El mango de la vía servicio es `_ProcesoPorPid` (vpn_win.py:676)
y su `poll()` (vpn_win.py:692) se fía de `_pid_vivo()`
(vpn_win.py:589): `OpenProcess(0x1000)` +
`GetExitCodeProcess == STILL_ACTIVE (259)`. CUALQUIER fallo —
handle NULL o GetExitCodeProcess fallido— se colapsa en «no
vivo» con `except Exception: return False` y SIN leer
GetLastError: el código no distingue «muerto» de «no pude
mirarlo». El mecanismo más probable: el Interactive Service
lanza openvpn ELEVADO (token de administrador, integridad alta)
y la app corre con integridad media; si `OpenProcess` sobre ese
proceso es denegado, `_pid_vivo` devuelve False para un proceso
vivito. Acto seguido, `poll()` fija
`returncode = _codigo_salida_pid(pid)` (vpn_win.py:620) **o 0 si
no se pudo leer** (vpn_win.py:697–699): de ahí el «Código de
salida de OpenVPN: 0» que pintó la pantalla sobre un proceso que
segundos después respondió al SIGTERM con una salida limpia. El
0 es fabricado (misma familia de defecto que el «código de
salida 0» anotado en INFORME-V1012 §5.4 para la 1.0.11).

Agravante de diseño: `puerta_previa_openvpn` (vpn_win.py:1919)
calcula la vía de la sesión («elevado» cuando el grupo aún no se
refleja — el caso típico tras instalar la 1.0.12 sin cerrar
sesión), pero `conectar_openvpn` NUNCA pasa `puerta["via"]` a
`_lanzar_openvpn` (vpn_win.py:924), que siempre prueba el
servicio primero. Y si el lanzamiento acabó en la reserva, el
mango `_ProcesoElevado.poll()` (vpn_win.py:736,
WaitForSingleObject sobre el handle de ShellExecuteEx) repite el
mismo patrón: lo indeterminado se convierte en «muerto» con
código 0. Compartan la vía que compartan los tres intentos, el
defecto es el mismo: **un veredicto de muerte instantáneo, sin
periodo de gracia y sin contrastar con la interfaz de gestión,
que SÍ estaba respondiendo**.

Por qué la CI no lo cazó: `tests/test_v1012.py` sustituye
`_lanzar_openvpn` por procesos falsos con `poll()` ideal
(`_ProcVivo`, línea 366) y el kernel32 falso solo ejercita el
protocolo del tubo hasta recibir el PID (línea 195). Ninguna
prueba corrió `conectar_openvpn` contra un `_ProcesoPorPid` real
ni contra `_pid_vivo`; el workflow usa el openvpn.exe real solo
para la puerta de parseo del perfil (build-windows.yml:139–157).
La costura de «¿sigue vivo?» quedó sin doble en la frontera del
SO: el proceso falso jamás pudo estar «vivo pero no abrible».

## 4. Por qué el titular dijo «TLS» (reproducido ejecutando el código)

`_analizar_registro` (vpn_win.py:1107) toma en su primera pasada
la primera «línea de error» (contiene warning/error/fatal/
failed/denied/cannot/unable) con familia conocida. Las marcas de
la familia **tls** (`_FAMILIAS_REGISTRO`, vpn_win.py:1085–1086)
incluyen la palabra suelta **«certificate»**. Y TODOS los
intentos anotan al arrancar la línea rutinaria «WARNING: No
server certificate verification method has been enabled…»: es
warning (→ línea de error) y contiene «certificate» (→ familia
tls), y precede a cualquier error real en un registro truncado.

Reproducido en esta investigación con las líneas reales de las
12:44:45: `_analizar_registro` → familia «tls», causa = ese
WARNING; `_mensaje_familia` → exactamente el titular que vio el
usuario. El clasificador no vio ningún fallo TLS: vio un
handshake truncado por el SIGTERM de la propia app y nombró el
primer warning que encontró. Falta la familia que este registro
grita: «detenido por la propia app» — un registro que termina en
«MANAGEMENT: CMD 'signal SIGTERM'» + «SIGTERM[hard,] received»
prueba que lo detuvo la app, y esa familia debe ir POR DELANTE
de todas las de red.

## 5. Por qué el detalle quedó congelado en las 11:31

La rama de proceso-muerto construye el detalle con
`ultimas = _ultimas_lineas(ruta_log) or _ultimas_lineas(ruta_salida)`
(vpn_win.py:1615) y el análisis con
`lineas = _lineas_archivo(ruta_log) + _lineas_archivo(ruta_salida)`
(vpn_win.py:1612), donde `ruta_salida` es
`openvpn-arranque.txt` (vpn_win.py:1585).

En la 1.0.12 **nadie escribe openvpn-arranque.txt**: por las
vías servicio/elevado el stdout va a NUL y `_lanzar_openvpn`
conserva el parámetro solo «por compatibilidad» —
`_SALIDA_ARRANQUE_FH` nunca se abre. El archivo conserva la
captura del ÚLTIMO intento de la 1.0.11 (foto de la carpeta:
modificado 11:31, 4 KB, el intento de la TAP ocupada). Como el
fallo se declara en t≈0 —antes de que el openvpn lanzado por el
servicio haya creado el nuevo `openvpn-conexion.log` (el
anterior acababa de rotarse)—, `_ultimas_lineas(ruta_log)`
vuelve «» y el respaldo sirve el arranque fosilizado de las
11:31 como si fuera el detalle de este intento, con el «Código
de salida de OpenVPN: 0» añadido. Las dos lecturas (análisis y
últimas) son aperturas separadas en plena carrera con el proceso
que crea su registro: así conviven en un mismo resultado un
titular TLS (de las primeras líneas del registro nuevo) y un
detalle fosilizado (del arranque viejo).

## 6. PLAN CONCRETO v1.0.13 (sin construir — pendiente de orden)

1. **Vida en tres estados.** `_pid_vivo` devuelve
   vivo/muerto/no-comprobable, leyendo GetLastError y anotando
   el fallo en actividad.jsonl; «no comprobable» JAMÁS cuenta
   como muerte. `_ProcesoPorPid.poll()` y `_ProcesoElevado.poll()`
   solo declaran muerte con prueba positiva (código de salida
   leído de verdad / WAIT_OBJECT_0 con código real). Desaparece
   el returncode fabricado 0: código desconocido = None y la
   pantalla dice «código de salida desconocido».
2. **Gracia y contraste en el bucle.** Ningún veredicto de
   muerte en los primeros segundos del intento, y antes de
   declarar muerto hay contraste: si la interfaz de gestión
   responde `state` (aunque sea CONNECTING), el proceso está
   vivo, punto. Muerte exige dos pruebas positivas separadas en
   el tiempo.
3. **La limpieza no se disfraza de fallo de red.** Si el
   finally detiene un proceso cuya muerte no se probó, el
   resultado dice «la app detuvo el intento» y no se clasifica
   como fallo del servidor. El clasificador gana la familia
   PRIORITARIA «detenido por la app» (marcas: «MANAGEMENT: CMD
   'signal SIGTERM'», «SIGTERM[hard,] received») y la familia
   tls pierde la marca suelta «certificate» (quedan «tls error»,
   «verify error», «tls handshake failed», «tls key negotiation
   failed»); el WARNING «No server certificate verification
   method» queda marcado como informativo expreso.
4. **Detalle del intento en curso.** Fuera el respaldo a
   openvpn-arranque.txt en las vías servicio/elevado (o se
   trunca al empezar el intento, como el registro); el detalle
   sale SOLO del registro de este intento, leído tras la salida
   confirmada con una breve espera de asentamiento, y si el
   registro no existe el detalle lo dice («OpenVPN no llegó a
   crear su registro en este intento»).
5. **Puerta coherente y vía observable.** `conectar_openvpn`
   honra `puerta["via"]` (si la puerta dice «elevado», se lanza
   elevado primero) y cada intento anota en actividad.jsonl: vía
   usada, aviso de la puerta, resultado del primer poll() y el
   GetLastError de `_pid_vivo` cuando falle — el próximo fallo
   debe poder diagnosticarse desde actividad.jsonl sin fotos.
6. **CI que caza ESTE fallo:**
   - Regresión con los registros reales 12:44/12:47/12:50: la
     familia esperada es «detenido por la app», jamás tls; y el
     WARNING de certificado a solas no produce familia.
   - `conectar_openvpn` con un proceso falso cuyo poll()
     simule «vivo pero no comprobable» y una gestión que
     responde `state` en CONNECTING: prohibido enviar SIGTERM
     antes del timeout real y prohibido clasificar TLS.
   - `poll()` con OpenProcess fallando por acceso denegado
     (monkeypatch) devuelve None (no 0); imposible fabricar el
     código de salida 0.
   - Detalle hermético: con un openvpn-arranque.txt fosilizado
     con texto marcador, el resultado de un intento por la vía
     servicio no puede contener ese marcador.
   - En el runner Windows: humo con el OpenVPN REAL del MSI
     (ya se extrae para la puerta de parseo) — lanzar un
     proceso real tras `_ProcesoPorPid` con una configuración
     contra un oyente local tonto y afirmar que poll() sigue en
     None mientras vive: ejercita la costura del SO que los
     falsos ocultaron. La delegación completa del Interactive
     Service sigue siendo prueba de la Toughbook, como siempre.

## 7. Qué NO fue (descartado con mecanismo)

Ni los servidores (tres distintos, UDP y TCP, misma firma en su
primer segundo), ni el barrido (mata por PID, sin línea de
gestión), ni la guarda de un intento (actúa antes del
lanzamiento y sobre el puerto anterior), ni un segundo cliente
de gestión (no existe tal código). El patrón completo —SIGTERM
propio en t≈0, titular TLS sobre un WARNING rutinario y detalle
fosilizado de las 11:31— lo explican tres defectos encadenados
de la 1.0.12: veredicto de muerte sin prueba (§3), clasificador
que nombra «certificate» como TLS (§4) y detalle alimentado de
un archivo que la versión ya no escribe (§5).
