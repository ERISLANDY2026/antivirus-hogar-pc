# INFORME V1.0.11 — Arreglo del fallo VPN de la 1.0.10 (causa confirmada)

Fecha: 2026-11-25. Orden del usuario (09:58 EST, «si» a la pregunta
«¿arranco la 1.0.11?»): construir la corrección con el diagnóstico
ya CERRADO en `INVESTIGACION-VPN-V1010.md` y el plan cerrado de su
§4. Alcance exacto cumplido, sin tocar nada fuera de él (el
auto-actualizador de OpenVPN de la 1.0.10 queda como estaba).

## La causa (confirmada en su Toughbook y en el código fuente)

En la 1.0.10, conectar con VPN Gate fallaba con TODOS los
servidores: «El servidor X no respondió o cortó la conexión.
Suele ser un servidor apagado o saturado». La prueba manual del
usuario (openvpn.exe a mano, fuera de la app) lo decidió:
`Options warning: Bad backslash ('\') usage in …vpngate-activo.ovpn:221`
+ «Use --help for more information.» y el proceso terminaba ahí.

- La línea 221 del perfil generado es la que añade la app:
  `auth-user-pass "C:\Users\NEW USER\…\vpngate-credenciales.txt"`
  con barras SIMPLES (`preparar_perfil_vpngate`, vpn_win.py).
- En OpenVPN 2.7.9 (`options_parse.c`, `parse_line()` con nivel
  M_USAGE → `usage_small()` → exit), una barra dentro de un
  parámetro entrecomillado seguida de un carácter no escapable
  (la primera era `\U` de `C:\Users`) es un error FATAL de
  opciones: el proceso muere al parsear el perfil, ANTES de abrir
  su `--log-append` y antes de cualquier red. Por eso: muerte
  instantánea idéntica con los 9+ servidores probados, CERO log
  (`openvpn-conexion.log` no existía en su PC), CERO «Detalle
  técnico» en actividad.jsonl, y la app caía en su mensaje
  genérico de «servidor saturado», falso de principio a fin.
- La suite de la 1.0.10 no lo vio porque su propio test
  (test_v1010.py) EXIGÍA la ruta con barras simples.

## 1. La causa raíz, corregida

- `preparar_perfil_vpngate()` escribe la ruta ESCAPADA con barras
  DOBLES (`ruta.replace("\\", "\\\\")`), la forma literal de la
  documentación oficial de OpenVPN para rutas Windows en perfiles
  (y la que recomienda el propio mensaje de error).
- Test corregido (el que fijaba las barras simples ahora exige
  las dobles y prohíbe las simples) + guarda nueva que reproduce
  el perfil real de VPN Gate de 221 líneas y verifica que la
  línea añadida (la 221) queda escapada, sin ninguna barra simple
  «desnuda» que el parser pueda leer como escape.
- **Puerta NUEVA en CI (la que faltó en la 1.0.10):** un paso del
  workflow extrae el openvpn.exe REAL del MSI oficial (instalación
  administrativa, sin instalar nada) y le hace parsear el perfil
  que genera LA PROPIA APP desde su lista semilla, con la ruta de
  credenciales en una carpeta CON ESPACIO («NEW USER», como la
  del usuario). Si la salida trajera «Bad backslash»,
  «Options error» o «Use --help», la compilación falla. En la
  corrida buena, la salida del OpenVPN real fue: perfil parseado
  entero (la línea auth-user-pass con la ruta escapada), aviso
  informativo de DCO desactivado para AES-128-CBC, y fase de red
  alcanzada («TCP/UDP: Preserving recently used remote address:
  [AF_INET]128.211.249.131:1195»). Lo que esta puerta NO prueba:
  el túnel (en el runner no hay TAP instalada): eso sigue siendo
  la prueba de su Toughbook.

## 2. Estado «conectada» honesto

- `estado_openvpn()`: «conectado» SOLO si la interfaz de gestión
  de la sesión dice CONNECTED,SUCCESS. Eliminado el respaldo
  «proceso vivo + sesión anotada». La sesión nace con
  `estado: "conectando"` y solo pasa a «conectada» al confirmar.
- `procesos_openvpn()`: fuera la detección por subcadena — solo
  cuenta el ejecutable por nombre EXACTO `openvpn.exe`
  (openvpn-gui.exe, openvpnserv.exe y OpenVPNConnect.exe ya no
  cuentan como túnel; de ahí salió el «CONECTADA a un servidor»
  falso de la foto). `hay_tunel_openvpn()` conserva su nombre y
  sus usos legítimos (diferir la actualización de OpenVPN y
  respaldo de desconexión), con la semántica nueva documentada.
- `servicios_red.estado_vpn()`: «conectada» = solo la
  confirmación del motor. La página refresca el interruptor
  TAMBIÉN tras un fallo (antes solo si el resultado era ok, y el
  rótulo falso se quedaba puesto).
- **Timeout sin huérfanos:** si el túnel no se confirma a tiempo,
  la app ahora MATA el proceso y borra la sesión (la 1.0.10 lo
  dejaba reintentando en segundo plano para siempre: podía
  conectar después de que la app ya dijo que falló).

## 3. Nunca más un fallo sin causa

- `_lanzar_openvpn()` ya no lanza con stdout/stderr a DEVNULL sin
  red: la salida de arranque se captura a `openvpn-arranque.txt`
  y el código de salida del proceso se guarda y viaja en los
  datos del resultado. Si openvpn muere antes de abrir su
  registro, ESA salida es la causa (reproducido en test con la
  salida exacta de la Toughbook del usuario).
- Clasificador nuevo (`_clasificar_fallo_openvpn`): familias
  autenticación, error de opciones/bad backslash, tarjeta
  TAP/DCO, servicio interactivo, TLS/verificación y red. El texto
  «servidor apagado o saturado» SOLO se usa ya para causas reales
  de red/TLS. Causa vacía declarada como tal: «OpenVPN se cerró
  sin dejar registro (código de salida N)…», nunca disfrazada.
  Las prioridades de `_causa_del_registro` incluyen las marcas
  nuevas (bad backslash, options error, ovpn-dco, data channel
  offload, interactive service, verify error).
- `detalle_tecnico` VISIBLE en la página de Red y VPN: rótulo
  nuevo `_lbl_vpn_detalle` bajo el mensaje del intento, que pinta
  «Detalle técnico: …» en cada fallo (antes el detalle se
  calculaba y no se pintaba en todo el flujo VPN). Verificado con
  test de página offscreen.

## 4. Registro por intento, sin borrar

- Al empezar cada intento, el `openvpn-conexion.log` anterior
  ROTA a `openvpn-conexion-AAAAMMDD-HHMMSS.log` (se conservan los
  últimos 5) en vez de borrarse.
- En cada fallo, las últimas líneas COMPLETAS del registro (o de
  la salida de arranque si no hubo registro) van en el detalle
  del resultado y quedan volcadas en `actividad.jsonl` por la
  capa de servicios, no solo la línea elegida de 300 caracteres.

## 5. Pruebas y compilación

- Suite nueva `tests/test_v1011.py` (17): versión vigente, la
  guarda del perfil real de 221 líneas, filtro de procesos por
  nombre exacto, estado sin confirmación ≠ conectado (el falso
  de la foto) y confirmado por la interfaz, estado en la capa de
  servicios solo con confirmación del motor, muerte por opciones
  reproducida desde la salida capturada (con la salida real de
  su PC), muerte sin causa declarada con su código, muerte por
  red sí clasificada «saturado», timeout que mata el proceso y
  borra la sesión, clasificador de familias nuevas, rotación del
  registro (incl. conservar solo 5 y rotar al reintentar),
  volcado de últimas líneas a actividad y el detalle técnico
  pintado en la página. Cirugía mínima: test_v1010 (el test que
  fijaba el bug + firma del lanzador falso + el dict de estado
  con su campo nuevo «conectando»), test_v107/test_v109/
  test_v1010 (pines de versión vigente a 1.0.11) y test_bugs_v102
  (el test de estado de la era del cliente delegado ahora confirma
  por la interfaz, como manda la 1.0.11).
- Suite local: todo lo no-Qt pasa; los tests Qt no pueden ni
  importarse en esta VM (falta libEGL.so.1 en el sistema — fallo
  de entorno previo a esta versión, idéntico en las versiones
  anteriores). La suite COMPLETA corre en la CI de Windows.
- **CI: corrida 45641956647 SUCCESS a la primera** (commit remoto
  `69b5ead314836edbb98c8be39a190b25ed821b2c`, árbol del commit
  local `46951dc`): «278 passed» (261 de la 1.0.10 + 17 nuevos),
  módulos e icono dentro del ejecutable, OpenVPN oficial
  verificado (tamaño, SHA-256 y firma), el ejercicio del
  auto-actualizador contra el MSI real, la puerta nueva de
  parseo (arriba) y el instalador final con OpenVPN dentro.
  Registro completo en `build-nube-v1011/ci-45641956647-log.txt`.

## 6. Instalador y canal

- Instalador: **Instalador-AntivirusHogarPC-1.0.11.exe**,
  45,243,720 bytes, MD5 `4cdcf706fde4c646d7c37b54a0c1daf5`,
  SHA-256 `0b821db3417625013be802ffe520b29390f70681a9bf2a5807ce25721cf8b145`.
  Zip: AntivirusHogarPC-Instalador-v1.0.11.zip, 44,734,256 bytes,
  MD5 `3180b2ee8efbc88f37e05fc4e8290dc1`.
- Canal Drive EN SITIO (mismos IDs): exe
  `1zmtcu-NL-PvCbGisbAXbFwVwyBlI5_ql` → «Instalador-AntivirusHogarPC-1.0.11.exe»,
  zip `1ZHiCO9lInsLv6GJBCdCj6GtTMjGf6hTG` → «AntivirusHogarPC-Instalador-v1.0.11.zip»,
  version-pc.json `1Kfd_pELWJhp37fO1iaERdSIzpRkAqK4R` (versión
  1.0.11, URL del exe con `&confirm=t`, SHA-256 nuevo). Los tres
  verificados: anyoneWithLink=reader, trashed=false, tamaños y
  MD5 coincidentes con lo compilado.
- Copia visible NUEVA: «INSTALADOR Antivirus Hogar PC v1.0.11.zip»,
  ID `1m1LJZ05ND8Y4BE1b0M0esdi9agEhP4s4` (anyoneWithLink=reader,
  MD5 verificado). La copia visible de la 1.0.10
  (`1NMQ-DHQcxDEfBm8LWGGJnNiDGD-EL0MU`) quedó en la papelera
  (trashed=true verificado).
- **PUERTA FINAL ANÓNIMA SUPERADA** con el código real de la app
  (`build-nube-v1011/puerta-final.py`): desde 1.0.10 OFRECE la
  1.0.11; desde 1.0.11 «al día»; descarga completa por la URL del
  JSON con SHA-256 válido; corte forzado a 15,000,000 B y
  reanudación con SHA-256 válido.

## 7. Honestidad (lo no probado)

- El túnel REAL contra un servidor VPN Gate en vivo sigue sin
  probarse fuera de su Toughbook: se prueba al instalarla desde
  el botón de su 1.0.10 y darle «Conectar». Lo nuevo probado de
  verdad en esta entrega: el parseo completo del perfil por el
  openvpn.exe real en la CI (el punto exacto del fallo) y la
  llegada a la fase de red contra un servidor de la semilla.
- Si en su PC quedara algún otro fallo tras el parseo (TAP,
  servicio interactivo, TLS), esta versión lo mostrará con su
  causa real en la propia pantalla y en el registro, en vez del
  texto genérico de la 1.0.10: el diagnóstico ya no depende de
  ejecutar nada a mano.
- Los tests Qt de la suite no corren en esta VM por el entorno
  (libEGL ausente); corren y pasan en la CI de Windows (278/278).
