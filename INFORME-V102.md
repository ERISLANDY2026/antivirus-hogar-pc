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
