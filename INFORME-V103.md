# Informe v1.0.3 — Huellas sin clave, progreso real, efectos en todo, drivers con causa y VPN con semilla

Cinco problemas reales reportados por Erislandy probando la v1.0.2 en su
Windows (con fotos), corregidos en una sola entrega. Autorización expresa
del usuario para procesar/ejecutar el código: «dale», 2026-11-24 10:21 EST.

## Problema 1 — Base de amenazas: «0 huellas» (abuse.ch exigía Auth-Key)

**Causa raíz:** en `core/threats_update.py` la ÚNICA fuente de huellas era
`_fuente_abusech()`; sin Auth-Key devolvía 0 con error y las otras 4
fuentes eran todas de dominios. La foto del usuario lo mostraba tal cual:
485.045 dominios fusionados y **0 huellas**.

**Corrección:**
- Nueva fuente de huellas SIN clave: **malicious-hash** (GitHub, licencia
  MIT, actualización horaria, agrega varias fuentes públicas), con sus
  dos archivos como fuentes separadas en la cadena multi-fuente:
  `full-hash-sha256-aa.txt` y `full-hash-md5-aa.txt`, parseados con el
  `parsear_export_hashes()` existente (ahora con etiqueta de fuente
  propia: «Malware conocido (malicious-hash)»).
- `_fuente_abusech()` sin clave pasa a estado **«opcional (sin clave; no
  se consultó)»** (nuevo campo `ResultadoFuente.opcional`): ya no cuenta
  como «falló» en `resumen()`. Con clave sigue consultándose y sumando.
- ThreatFox CSV quedó descartada (rastreo viejo con 0 entradas, no
  verificada como viva) y CyberCure dio HTTP 520: ninguna es principal.

**Evidencia (descargas reales, 2026-11-24):**
- Archivo SHA-256: 131.072 líneas, **130.905 SHA-256 válidas** contadas;
  archivo MD5: 4.128 líneas, **4.049 MD5 válidas**.
- Cadena completa ejecutada de punta a punta sin clave: **135.195
  huellas únicas fusionadas** y 485.045 dominios; resumen por fuente:
  malicious-hash (SHA-256) 131.072 · malicious-hash (MD5) 4.128 ·
  URLhaus-filter 2.091 · Phishing.Database 358.722 · OpenPhish 286 ·
  CERT.PL 123.969 · abuse.ch «opcional (sin clave; no se consultó)».

## Problema 2 — Escaneo rápido: barra en «Escaneando…» sin progreso

**Causa raíz (doble):**
1. `core/scanner.escanear()` emitía el callback de progreso **una vez
   por archivo, sin límite de frecuencia**. En un escaneo rápido real
   (miles de ejecutables resueltos desde la caché en microsegundos) la
   cola de eventos Qt se inundaba y la barra se quedaba con el texto
   inicial hasta saltar al 100 %. Además no había un primer aviso con
   el total conocido.
2. `_TrabajadorEscaneo.run()` (página Escanear) **no capturaba
   excepciones**: si `escanear()` lanzaba, la señal `terminado` nunca
   llegaba y la barra quedaba colgada para siempre.

**Corrección:**
- Tras recolectar se emite `progreso("", 0, total)`; después, como
  mucho cada 25 archivos o cada 100 ms, y **siempre el último (N de
  N)**. El conteo es de archivos procesados (revisados + errores), así
  la barra llega al total aunque algún archivo no se pueda leer.
- `run()` va en try/except: el error viaja dentro de
  `ResultadoEscaneo.error` (campo nuevo) y la página lo enseña
  («⚠ El escaneo no se pudo completar: …») en vez de colgarse.
- Tests: secuencia de progreso monótona 0 → total con ≤10 avisos para
  60 archivos (core, sin Qt) y página Qt offscreen que escanea una
  carpeta temporal y termina en 100 % con «Escaneo terminado».

## Problema 3 — Efectos visuales solo en Inicio

**Causa raíz:** el QSS del tema sí era global, pero `BotonPulso` **no se
usaba en ninguna página** (todos los botones eran `QPushButton` pelados
con solo el gradiente estático) y `TarjetaAnimada.fijar_activa(True)`
**nunca se activaba** fuera del Panel. Protección e Informes ni siquiera
tenían barra para sus operaciones largas.

**Corrección:**
- Nuevo helper `paginas_base.boton_principal(texto, objectName)`:
  `BotonPulso` con el pulso encendido conservando el objectName del
  tema («primario»/«verde»). Aplicado a la acción principal de cada
  página: Escaneo rápido (Escanear), Actualizar firmas (Protección),
  Generar informe (Informes), Escanear drivers y Analizar (Sistema:
  Drivers/Discos/Limpieza), Buscar programas/Windows y la app
  (Actualizaciones), Actualizar datos de Wi-Fi, Medir velocidad y
  Actualizar lista de servidores (Red), Guardar canal (Ajustes).
- `fijar_activa(True/False)` en la tarjeta en curso durante: escaneo,
  actualización de firmas, generación de informe, escaneo de drivers,
  análisis de discos, operaciones de limpieza (vía `_ocupado`), Wi-Fi,
  velocidad, descarga de servidores VPN, winget y Windows Update.
- `BarraProgreso` nueva en Protección (actualizar firmas, modo texto de
  etapa) e Informes (generar informe). Verificado por test: **ninguna
  `QProgressBar` que no sea `BarraProgreso`** en el código de la app.
- Test Qt offscreen por página (con fakes): cada página principal
  contiene ≥1 `BotonPulso` y ninguna barra pelada.

## Problema 4 — Drivers: todo «Sin confirmar» tras escanear al 100 %

**Causa raíz:** el contraste depende de `buscar_drivers_windows_update()`
(COM de Windows Update vía PowerShell). Ese script **no distinguía
«búsqueda completada sin novedades» de «búsqueda fallida»**: si el COM
fallaba o tardaba, PowerShell terminaba sin salida útil, el resultado
vacío se trataba como «sin datos» y el paso 3 marcaba **todos** los
drivers «sin confirmar», sin causa visible en ninguna parte. En la PC
del usuario eso pasaba con todos (foto: tabla completa en «Sin
confirmar», solo botón «Fuentes oficiales»).

**Corrección:**
- Script de búsqueda reescrito con try/catch y **JSON estructurado**
  `{ok, codigo, causa, actualizaciones}`: comprueba el `ResultCode`
  de la búsqueda (2/3 = completada). Completada → se devuelve la lista
  (vacía = sin novedades, la consulta SÍ se hizo). Fallida → se lanza
  `RuntimeError` con la **causa real** (mensaje/HRESULT de Windows).
- Semántica nueva de estados (`drivers_logic.contrastar_con_windows_update`
  con `consulta_completada`): consulta completada sin versión más
  nueva → **«Al día»**; con versión más nueva → **«Hay uno más nuevo»**
  con su botón «Actualizar» (ya existía vía `puede_actualizar`);
  **«Sin confirmar» SOLO si la consulta falló**. Sin marca de consulta
  completada, el comportamiento histórico se mantiene (lista vacía =
  sin datos): jamás se marca «al día» sin consulta exitosa real.
- La causa viaja: `escanear_drivers_paso2_buscar` devuelve `wu_causa`,
  el paso 3 la mete en el detalle de cada fila, en el mensaje y en los
  datos, y la página de Drivers la pinta en un **renglón rojo propio**
  bajo el estado («⚠ Windows Update no pudo confirmar los drivers.
  Causa: …»).
- Tests con backend simulado para los tres estados + página Qt
  offscreen que pinta la causa al fallar la consulta.

## Problema 5 — VPN: la sección sigue sin países ni servidores

**Causa raíz:** la v1.0.2 pedía la lista **una sola vez** al endpoint
HTTPS principal de VPN Gate (`descargar_lista_servidores(url)` sin
reintento ni respaldo). Si esa única petición cae —corte TLS/conexión,
lentitud de vpngate.net, respuesta irreconocible— la sección queda
vacía. **Evidencia desde el entorno de construcción (2026-11-24):** la
ruta HTTPS principal falló (conexión cortada, HTTP 000) mientras el
**mismo API por HTTP respondió 200** con la lista completa (99
servidores, 9 países en esa descarga): la ruta única era el problema.

**Corrección:**
- **Cadena con reintentos y respaldo** (`descargar_lista_con_respaldo`):
  prueba `config.VPNGATE_APIS` — HTTPS con www, HTTPS sin www y HTTP
  del mismo servicio oficial — 2 intentos por ruta, hasta que una
  devuelva servidores parseados. Verificado en vivo: la cadena real
  acertó por la ruta HTTP con **99 servidores / 9 países** tras fallar
  las HTTPS desde este entorno.
- **Lista SEMILLA incluida en la app** (`assets/vpngate_seed.csv`,
  471.907 bytes): 35 servidores REALES de la descarga de construcción
  del 2026-11-24 (el más rápido de cada país + los 30 más rápidos; 9
  países: Hungary, Japan, Korea Republic of, Romania, Russian
  Federation, Sweden, Thailand, United States, Viet Nam), con su
  perfil .ovpn en Base64 para que «Conectar» funcione igual. Si todas
  las descargas fallan, la página puebla combo y tabla con la semilla
  y enseña el aviso **«⚠ Lista de respaldo del 2026-11-24 (sin
  conexión con VPN Gate)»** con la causa concreta; el aviso no se
  pierde al filtrar por país, y el botón queda en «Reintentar
  descarga», que vuelve a lanzar la cadena completa y repinta.
- Tests: parseo contra la **fixture real** guardada de la API
  (`tests/fixtures/vpngate_api_real.csv`, 5 filas reales completas),
  cadena que cambia de ruta y acierta, fallo total con causa, semilla
  real incluida (≥30 servidores con .ovpn y fecha), servicio que cae
  en semilla con la causa en el mensaje, y página Qt offscreen que
  puebla combo+tabla tanto con la descarga como con la semilla.

## Verificación de la entrega

- Suite local completa (Qt offscreen real): **116 passed** (98 de la
  v1.0.2 + 18 nuevos de la v1.0.3), 0 fallos.
- GitHub Actions run **45427142623**: `completed / success` — suite en
  Windows + verificación de los 4 registros de módulos dentro del
  ejecutable (regresión v1.0.0).
  https://github.com/ERISLANDY2026/antivirus-hogar-pc/actions/runs/45427142623
- Código: commit local `8f51940`, commit remoto
  `6a6543b27ed6558bf62d25226e630a864d1cef6a` (19 archivos por Git Data API).
- Instalador: `Instalador-AntivirusHogarPC-1.0.3.exe`, **39.782.405
  bytes**, PE32 GUI Windows, MD5 `a476e2006e67b630f05b161e858c317c`,
  SHA-256 `b15f4abf0a0f13a2fd9dfe37d933f952e832122e44e75731418bd4dbc6d077be`.
- Drive actualizado EN SITIO (mismos ID y enlaces, verificado por
  tamaño y MD5 contra el local): zip `1ZHiCO9lInsLv6GJBCdCj6GtTMjGf6hTG`
  renombrado a `AntivirusHogarPC-Instalador-v1.0.3.zip` (39.225.522 B,
  MD5 `c2098e635cf69bcff1c7ac02b5287dba`) y .exe suelto
  `1zmtcu-NL-PvCbGisbAXbFwVwyBlI5_ql` renombrado a
  `Instalador-AntivirusHogarPC-1.0.3.exe` (MD5 idéntico al local).
  https://drive.google.com/file/d/1ZHiCO9lInsLv6GJBCdCj6GtTMjGf6hTG/view?usp=drivesdk
- Canal en vivo verificado con la lógica real de la app
  (`core.updater.comprobar_actualizacion` contra la URL de Drive):
  desde **1.0.2 → ofrece la 1.0.3** con su SHA-256; desde **1.0.3 →
  «al día»**.

## Pendiente honesto

- El instalador v1.0.3 aún NO se ha ejecutado en el Windows real de
  Erislandy; la verificación automática (suite + registros dentro del
  .exe + canal en vivo) está pasada, pero la prueba final en su PC
  queda de su lado, como en las versiones anteriores. La puerta sigue
  vigente: ÉL decide si lo instala. Su app v1.0.2 le ofrecerá sola la
  1.0.3 desde «Actualizaciones → Buscar actualizaciones de la app».
