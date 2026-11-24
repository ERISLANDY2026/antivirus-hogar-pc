# Informe v1.0.2 — Interfaz viva, porcentajes reales y bugs corregidos

Construcción por carriles en paralelo con un solo integrador (patrón de la
v1.0.0): carril 1 = tema visual, carril 2 = Drivers/Sistema, carril 3 =
Panel/Red/Seguridad; el integrador unió, probó y compiló UNA sola vez.

## Punto por punto contra REQUISITOS-V102.md

1. **Porcentaje en TODAS las barras** — Nueva `BarraProgreso`
   (`ui/widgets_v102.py`): % REAL donde se puede contar (escaneo por
   archivos, limpieza por partidas, winget programa a programa, pasos de
   una operación). Donde Windows Update no expone % real, la barra
   muestra la ETAPA y el conteo de pasos («Paso 2 de 2 · Instalando con
   Windows Update (Windows no informa el porcentaje)») — nunca un %
   inventado (core/v102.py: `porcentaje`, `texto_porcentaje`,
   `texto_etapa`, con tests que exigen que el texto de etapa no lleve %).
   - Escaneo de drivers partido en 2 pasos reales (enumerar → contrastar).
   - Actualización de drivers en 2 pasos (punto de restauración →
     instalación); si el punto falla, no se instala (como antes).
2. **Colores, cromados, RGB, botones animados** — theme.py: botones con
   gradiente cromado metálico; primario cian, actualizar verde, peligro
   rojo (gradientes con hover/pressed). `BarraProgreso` pinta su chunk
   con gradiente RGB animado (timer 60 ms); `TarjetaAnimada` dibuja el
   borde RGB animado cuando la tarjeta está activa; `BotonPulso` da
   brillo al hover y pulso en la acción principal.
3. **Ventana de Drivers** — fuera `setStretchLastSection(True)` y
   `resizeColumnsToContents()`: Dispositivo=Stretch con elipsis y
   tooltip, Versión 150px, Fecha 110px, Estado 130px y **Acción fija de
   250px SIEMPRE visible** con sus botones Actualizar/Fuentes oficiales.
4. **Servicios nuevos aprobados**:
   - Medidores en vivo CPU/RAM/disco con % en el Panel (`Medidor`,
     refresco cada 2 s con los datos reales de psutil).
   - Registro de actividad (`core/actividad.py`, JSONL en la carpeta de
     datos): escaneos, limpiezas, papelera, drivers y arranque quedan
     anotados con fecha; tarjeta en el Panel con las últimas 8 entradas
     y botón «Exportar registro».
   - Gestor de inicio con impacto: cada programa lleva su impacto
     (alto/medio/bajo con motivo, `core/v102.clasificar_impacto_arranque`)
     coloreado; «Desactivar (reversible)» se mantiene.
   - Mapa de uso de disco por carpetas con % sobre el total medido
     (Descargas, Documentos, Escritorio, Imágenes, Vídeos, Música y
     temporales), con progreso real por carpeta.
   - Prueba de velocidad de internet (`core/velocidad.py`, descarga real
     contra speed.cloudflare.com: ping y Mbps con valoración) y estado
     VPN con números (clientes instalados, IP pública) en Red.

## Bugs de la v1.0.1 corregidos (verificado)

1. **Actualizaciones de la app siempre «revisa tu conexión»** — Causa: el
   version-pc.json nunca se publicó; config traía el id marcador
   `1BpcVersionJsonPendiente`. Corrección completa:
   - version-pc.json REAL publicado en la carpeta «Antivirus Hogar PC»
     de Drive, ID `1Kfd_pELWJhp37fO1iaERdSIzpRkAqK4R`, lectura pública.
   - `UPDATE_VERSION_URL` con ese ID real en config.py.
   - Errores clasificados (`core.updater.ErrorActualizacion`:
     sin_conexion / no_encontrado / respuesta_invalida) y mensajes
     distintos por causa en la página de Actualizaciones.
   - Evidencia en vivo: con el canal en 1.0.1, desde 1.0.1 → «al día»
     (sin falso error); tras actualizar el canal a 1.0.2, desde 1.0.1 →
     ofrece la 1.0.2 con su SHA-256, y desde 1.0.2 → «al día». Test en la
     suite que descarga la URL configurada real y la parsea.
   - El instalador 1.0.2 quedó también como archivo propio en Drive
     (ID `1zmtcu-NL-PvCbGisbAXbFwVwyBlI5_ql`, lectura pública) para que
     la descarga de la actualización sea directa y verificable por
     SHA-256, como manda el flujo de la app.
2. **VPN sin países** — La lista solo se descargaba a mano y un fallo la
   dejaba vacía en silencio. Corrección: carga automática al abrir la
   sección de Red/VPN; combo de países y tabla (País, Servidor,
   Velocidad, Ping, Sesiones, Acción) poblados desde la API de VPN Gate
   (User-Agent «AntivirusHogarPC», timeout 60 s); si la descarga falla o
   llega vacía, error VISIBLE en rojo con la causa y botón «Reintentar
   descarga». Tests: parseo del CSV con muestra real de formato (3
   servidores, países Japan/United States) y, con Qt offscreen, que la
   página puebla el combo, pinta las filas y cada fila lleva su botón
   «Conectar», más el estado de error con reintento.
3. **Sin forma de apagar la VPN** — Nuevo interruptor general en la
   sección VPN: muestra el estado real (hay proceso openvpn en marcha +
   último servidor/país entregado por la app) y el botón «Desconectar
   VPN». MECANISMO HONESTO: OpenVPN Connect/GUI no ofrecen un comando de
   desconexión para terceros, así que la app cierra el proceso openvpn
   del túnel (`winapi.vpn_win.terminar_procesos_openvpn`), que es lo que
   apaga la conexión; SoftEther usa su propio servicio y NO se toca (la
   app lo dice si es el caso). Tras desconectar, el estado pasa a
   «Desconectada», el estado guardado se limpia y la IP pública se
   refresca sola. Tests de la lógica sí/no y del flujo de desconexión
   con el backend simulado (monkeypatch de winapi).

## Verificación

- Suite local (Linux, sin Qt): **87 passed, 2 skipped** (los 2 tests Qt
  de la página VPN se saltan sin PySide6; en el runner de Actions, con
  PySide6 y plataforma offscreen, corren dentro de la suite del
  workflow). Suite anterior: 60 → total con los nuevos tests de v102 y
  de bugs.
- GitHub Actions run **45415944003**: `completed / success` — incluye la
  suite en Windows y el paso que verifica los 4 registros de módulos
  dentro del ejecutable (regresión v1.0.0).
  https://github.com/ERISLANDY2026/antivirus-hogar-pc/actions/runs/45415944003
- Código: commit local `fed5539`, commit remoto `cfc1fe3e63a360d2b2f7ffe6753fe044f0389c0b`
  (25 archivos por Git Data API).
- Instalador: `Instalador-AntivirusHogarPC-1.0.2.exe`, **39,742,488
  bytes**, PE32 GUI Windows (Inno Setup), MD5
  `f6ec2d14256fa2e16978cb3f12f68f42`, SHA-256
  `3bb21502f83f572dea9db17553d5a9fdc2c72672e9595972e349cc82088ba105`.
- Drive: `AntivirusHogarPC-Instalador-v1.0.2.zip` (39,187,871 bytes, MD5
  `73134aa752506238a407c2732fcaf7b0`, verificado contra el local) en la
  carpeta «Antivirus Hogar PC»:
  https://drive.google.com/file/d/1ZHiCO9lInsLv6GJBCdCj6GtTMjGf6hTG/view?usp=drivesdk

## Pendiente honesto

- El instalador v1.0.2 aún NO se ha ejecutado en el Windows real de
  Erislandy; la verificación automática (suite + registros dentro del
  .exe + canal en vivo) está pasada, pero la prueba final en su PC
  queda de su lado, como en la v1.0.1. La puerta sigue vigente: ÉL
  decide si lo instala. Nota: como el canal ya ofrece la 1.0.2, su app
  v1.0.1 también puede actualizarse sola desde «Actualizaciones →
  Buscar actualizaciones de la app».

---

# Segunda ronda (2026-11-24): bug 4, bug 5, fondo de radar y bug 6

Tras la primera entrega entraron cuatro trabajos más del usuario y el
instalador se reconstruyó con todo (misma versión 1.0.2; el zip y el
.exe de Drive se actualizaron en sitio, mismos ID y enlaces, y el
version-pc.json recibió el SHA-256 nuevo).

## Bug 4 — «Actualizar datos de Wi-Fi» sin feedback ✅ corregido

- **Feedback inmediato al pulsar:** el botón pasa a «Leyendo…»
  deshabilitado y aparece la barra de progreso con «Leyendo la red
  Wi-Fi…» (`modules/net/page.py::_cargar_wifi`).
- **Sello de hora:** al completar, «Actualizado a las HH:MM:SS»; si
  netsh falla, «No se pudo actualizar (HH:MM:SS)» y la causa real
  (mensaje + detalle técnico) en rojo en la tarjeta — nunca más la
  pantalla idéntica en silencio.
- **Test:** `test_wifi_flujo_leyendo_y_sello_de_hora` — pulsar →
  estado «leyendo» → datos repintados con sello de hora; y camino de
  error con causa. Verificado en local con Qt offscreen real (y en la
  suite de Actions, que es la misma que corre contra el código del
  ejecutable congelado; el flujo no usa nada específico de plataforma
  fuera de `netsh`, cuya salida ya trata `seguro()`).

## Bug 5 — El escaneo de drivers no funcionaba en su PC ✅ endurecido

Qué se encontró revisando el flujo completo (`escanear_drivers` paso a
paso → `winapi/drivers_win.py` → `winapi/powershell.py`) pensando en el
ejecutable congelado en un Windows 10 real:

1. **Decodificación frágil:** `subprocess.run(..., text=True)` sin
   `errors=` decodifica la salida de PowerShell/netsh con la página de
   códigos local en modo *strict*: un nombre de dispositivo con
   caracteres fuera de esa página podía **reventar la lectura**
   (UnicodeDecodeError) y matar el escaneo. → `errors="replace"` en
   `ejecutar_powershell` y `ejecutar_comando`.
2. **Vacío silencioso posible:** si la consulta CIM
   `Win32_PnPSignedDriver` no devolvía datos, el flujo podía acabar
   sin nada visible. → `enumerar_drivers()` ahora **lanza error con
   causa** si la consulta no devuelve ningún dato (en un Windows real
   siempre hay decenas de drivers; vacío = la consulta falló).
3. **Progreso por pasos determinados (3):** «Leyendo los drivers
   instalados (1/3) → Consultando fuentes oficiales / Windows Update
   (2/3) → Comparando versiones (3/3)». El servicio se partió en
   `escanear_drivers_paso2_buscar()` + `escanear_drivers_paso3_comparar()`
   (el envoltorio `escanear_drivers_paso2` se mantiene compatible).
4. **Error SIEMPRE visible con causa:** cualquier excepción en
   cualquier paso termina en la página con «⚠ No se pudo escanear:
   <causa>» en rojo y negrita, botón reactivado y apunte en el registro
   de actividad; nunca tabla vacía en silencio ni «escaneando» eterno.
5. **Vigía anti-cuelgue:** si un paso tarda más de 2 minutos (Windows
   Update ocupado es el caso típico en Windows 10), la pantalla lo
   dice: «Windows está tardando más de lo normal… el escaneo sigue en
   curso».
6. Que Windows Update no responda sigue **sin** ser fallo del escaneo:
   el paso 3 marca «sin confirmar», que es la verdad.

**Tests:** `test_drivers_paso1_excepcion_es_error_con_causa` (el fake
lanza y el servicio devuelve el error con la causa),
`test_drivers_pagina_muestra_el_fallo` (página real offscreen: se
pulsa «Escanear drivers» con el backend lanzando excepción y la página
pinta el fallo y reactiva el botón) y
`test_drivers_pasos_2_y_3_separados`.

## Fondo de inicio aprobado — barrido de radar ✅ implementado

- `ui/fondo_radar.py`: banda de fondo del Panel con **barrido de radar
  digital girando suave** detrás del anillo de salud (el anillo va
  ENCIMA, centrado), rejilla oscura en movimiento lento, **26
  partículas cian subiendo** y **resplandor cian/azul/morado que
  respira**.
- **Ligero a propósito:** QTimer de paso grueso (120 ms), una sola
  pasada de QPainter, y la animación se para sola cuando la banda no
  está visible — pensado para no cargar la CPU de su Toughbook.
- **Tarjetas cristal:** las tarjetas del Panel llevan la propiedad
  `cristal` → fondo translúcido `rgba(20, 27, 41, 205)` (regla en
  `theme.py`), con la legibilidad intacta.
- **Interruptor:** Ajustes → Vista → «Fondo animado del Panel (radar)»
  (campo `fondo_animado`, activado por defecto). Además se respeta
  «reducir animaciones» de Windows vía SPI_GETANIMATION
  (`panel/datos.animaciones_windows_permitidas()`): si Windows lo
  pide, el radar queda fijo aunque el interruptor esté encendido.
- **Tests:** `test_radar_se_crea_y_se_apaga`,
  `test_animaciones_windows_fuera_de_windows_no_rompe`.

## Bug 6 — Firmas abuse.ch: varios respaldos, no solo uno ✅ corregido

La actualización de inteligencia de amenazas ahora es una **cadena
multi-fuente que las intenta TODAS y fusiona resultados**
(`core/threats_update.py::actualizar_firmas_multifuente`), cada fuente
con su propio timeout (45 s) y su resultado contado por separado; la
UI muestra «Fuente X: N firmas · Fuente Y: falló (causa)» en la
tarjeta de la base y en el diálogo:

1. **abuse.ch (MalwareBazaar, huellas)** con la Auth-Key de Ajustes si
   existe; sin clave se intenta/registra con su causa exacta.
2. **URLhaus (dominios)** vía malware-filter.
3. **Phishing.Database** (GitHub, dominios de phishing).
4. **OpenPhish** (feed comunitario; URLs → dominios).
5. **CERT.PL** (lista oficial de dominios maliciosos).

La actualización se considera lograda si **al menos una** fuente
aporta; error total solo si caen todas, con las causas reales (nunca
«revisa tu conexión» como único texto). Las huellas van a
`firmas_extra.txt` (escáner) y los dominios a `dominios_extra.txt`,
que el bloqueador **suma a su base semilla** al activarse
(`seguridad.rutas_base_dominios`). La base local incluida queda como
respaldo final sin conexión, y la UI lo dice.

**Verificación de fuentes desde el entorno de construcción
(2026-11-24) y sustituciones, como se ordenó documentar:**

- Los **exports públicos de abuse.ch devuelven 410 Gone** (bazaar y
  urlhaus, comprobado con peticiones reales): abuse.ch los retiró en
  2025 y todo pasa por la API con Auth-Key gratuita. Sin clave, la
  fuente 1 reporta esa causa y la cadena sigue con las demás — ya no
  depende de una sola fuente.
- El **hostfile de URLhaus también murió (410)**: lo sustituye el
  proyecto **malware-filter** (curben), que republica los datos de
  URLhaus como lista de dominios — verificado 200 (287 KB).
- **Phishing.Database**: 200 (11 MB). **OpenPhish**: 200 tras
  redirección. **CERT.PL**: 200 (2,6 MB).
- **ET Open y Spamhaus DROP responden (200) pero son listas de
  IP/CIDR**: no sirven a un bloqueador por dominios ni como huellas de
  archivo; quedan fuera y su hueco lo cubre CERT.PL. **DigitalSide**
  no respondió desde el entorno (timeout): descartado.

**Tests:** `test_multifuente_fusiona_y_reporta_por_fuente` (fuentes
fake: una ok, una caída HTTP 500, una vacía; IPs descartadas;
abuse.ch sin clave con su causa),
`test_multifuente_todo_caido_es_error_total_con_causas` y
`test_parsear_dominios_de_urls`.

## Suite y reconstrucción (segunda ronda)

- Suite local completa con Qt offscreen real: **98 passed, 0 skipped**
  (primera ronda: 87 passed, 2 skipped sin Qt en local).
- Reconstrucción: commit y run de Actions y datos del instalador
  nuevo, en la nota de entrega de esta ronda (el zip de Drive y el
  version-pc.json se actualizaron en sitio con el SHA-256 nuevo).
