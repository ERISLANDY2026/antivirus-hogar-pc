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
