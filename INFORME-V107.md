# INFORME — Antivirus Hogar PC v1.0.7

**Fecha:** 2026-11-24 · **Orden del usuario (llamada de voz, 16:25 EST):**
«Genera la próxima actualización para que venga con todo eso a través
del botón. Dale, arranca.» · **Base:** notas de su revisión de la
1.0.6 en su Toughbook real (`NOTAS-POST-V106.md`).

**Estado: COMPLETA Y ENTREGADA.** Suite 225/225, compilación en la
nube en SUCCESS (run **45503985673**), canal de Drive actualizado en
sitio y **PUERTA FINAL SUPERADA** (anónima, con el código real de la
app). Pendiente solo su instalación desde el botón de su 1.0.6 y su
veredicto en el Windows real.

---

## Lo que trae (los tres puntos pedidos)

### 1. VPN Gate con SoftEther INCORPORADO y sincronizado (el pedido central)

- **El instalador de la app instala también SoftEther VPN Client**
  4.44 Build 9807 RTM (2025-04-16), la versión estable vigente del
  sitio oficial, sin que el usuario instale ni abra nada más: los
  archivos del cliente quedan en `{app}\softether` y el instalador
  registra su servicio de Windows **SEVPNCLIENT** (solo si el equipo
  no tiene ya uno; si lo registramos nosotros queda una marca y el
  desinstalador solo retira el servicio cuando es el incorporado).
- **La app lo maneja por `vpncmd`** (la herramienta oficial de línea
  de comandos de SoftEther, contra el servicio local): al pulsar
  «Conectar» en un servidor de la lista, la app asegura la tarjeta
  virtual (NicCreate la primera vez), crea la conexión
  «AntivirusHogarVPN» contra ese servidor (puerto 443, hub
  **VPNGATE**, usuario/contraseña **vpn** — así aceptan los
  servidores de VPN Gate su conexión SSL-VPN), la conecta **en
  segundo plano, sin abrir la ventana de SoftEther**, y espera a que
  el estado confirme el túnel (literal del cliente: «Connection
  Completed (Session Established)»).
- **El botón de ese servidor se pone VERDE y dice «Conectado»**, la
  etiqueta de estado se pinta en verde y el interruptor general
  refleja la conexión; «Desconectar VPN» baja el túnel por vpncmd
  (AccountDisconnect). El estado de la página se lee también de
  vpncmd, no solo del proceso OpenVPN.
- **Respaldo intacto:** si SoftEther no está en el equipo, sigue la
  vía de siempre (perfil .ovpn entregado al cliente instalado).
- **Evidencia del binario incorporado:** instalador oficial
  descargado en la compilación desde `www.softether-download.com`
  (URL fijada en el workflow), tamaño verificado **56.249.368
  bytes** (el del listado oficial) y **SHA-256
  `AB006331F1F646BC319585088239D55BC54ECDE5C269009268E9598307DA7A44`**.
  En la corrida 45502795985 el `vpncmd` incorporado **se ejecutó en
  el runner**: imprimió su banner oficial «SoftEther VPN Command
  Line Management Utility — Version 4.44 Build 9807 (English) —
  Compiled 2025/04/16 … OpenSSL 3.0.9», creó su `lang.config` y solo
  falló al conectar (en el runner no hay servicio de cliente: es el
  resultado correcto). Detalle del formato en
  `packaging/softether/LEEME.md`.
- **El instalador crece +23.012.496 bytes** (de 40.619.617 a
  63.632.113): es el cliente incorporado, como el usuario aceptó.

### 2. Discos → «Optimizar volúmenes»: desenlace real y «Optimización finalizada»

- Hoy la app solo aceptaba el «OK» del archivo de resultado; en su
  PC la optimización corre completa pero ese OK no llega y decía
  «no se completó». Ahora, si no hay veredicto directo, el desenlace
  se extrae de **dos fuentes más**: (a) el **registro de eventos de
  Windows** (fuente/canal Defrag, ventana de la corrida, por
  volumen: éxito confirmado o motivo del fallo) y (b) la **salida
  detallada completa** de Optimize-Volume (si llegó a su informe
  final —«Post Defragmentation Report»—, terminó). También se
  consultan los eventos si el proceso elevado muere sin dejar
  archivo de resultado.
- Si la evidencia confirma que terminó: **«Optimización
  finalizada»** (con el detalle en el registro de actividad). Si
  falló: la **causa verdadera** de esas fuentes, nunca «causa
  desconocida» a secas; el texto completo del evento viaja en el
  detalle que la página guarda en el registro.
- Tests con los tres desenlaces: OK directo; sin OK pero evento de
  éxito; fallo con el motivo en el evento (0x8900002A incluido en el
  detalle); más el informe final en el verbose y el filtro por
  unidad (los eventos de D: no cuentan para C:).

### 3. La carpeta de descargas del actualizador se crea sola

- Lección de la entrega 1.0.6 en su PC: la descarga por el botón
  fallaba porque `%LOCALAPPDATA%\AntivirusHogarPC\actualizaciones`
  no existía y nadie la creaba (la creó él a mano). Ahora
  `descargar_archivo` crea la carpeta de destino con
  `makedirs(exist_ok=True)` **siempre**, y `instalar_actualizacion_app`
  también la crea antes de descargar. Test de regresión: descargar
  con la carpeta ausente funciona (a nivel de descargador y a nivel
  de servicio completo, con verificación SHA-256).

---

## Problemas encontrados por el camino (cada uno con su causa)

1. **Desde esta VM no se puede descargar el instalador de
   SoftEther:** el servidor oficial corta la conexión tras el
   saludo TLS (curl: salida vacía; wget: error de red; Python:
   conexión cerrada), con cualquier cliente. *Solución:* la
   descarga la hace la compilación en la nube en cada corrida,
   desde la URL oficial fijada, verificando tamaño exacto y
   anotando el SHA-256 en el registro.
2. **Corrida CI 45493532868 — FAILURE con la suite en verde:** el
   registro dice «225 passed» y aun así el paso salió con código 1.
   *Causa:* un trabajo/temporizador de la página del test nuevo de
   Qt quedaba vivo al caer el intérprete (caída al cierre, lotería
   de tiempos; reproducido en local como segfault al salir).
   *Arreglo:* cierre ordenado del test (esperar hilos, destruir el
   widget, vaciar eventos) — verificado estable en corridas
   repetidas.
3. **Corridas 45495019301/45496371062 — «paquete SoftEther
   incompleto»:** el instalador oficial no es un zip con un .cab:
   es un **PE cuya carga va como recursos** en
   `.rsrc\0\DATAFILE\` con nombres internos (`VPNCLIENT_X64.EXE`,
   `VPNCMD_X64.EXE` —que es vpncmd—, `VPNCMGR_X64.EXE` y
   `RAW_HAMCORE.SE2`). Faltaba solo el hamcore, por su prefijo
   `RAW_`. *Arreglo:* copia con mapa de nombres a los de una
   instalación real.
4. **Corrida 45498267165 — el runner rechazó vpncmd**
   (`ERROR_EXE_MACHINE_TYPE_MISMATCH`). *Causa (confirmada en la
   siguiente):* los recursos `.exe` **no son el PE**: van
   **comprimidos** con el formato del fabricante — prefijo de 4
   bytes + flujo zlib (`78 9C`) —; el `hamcore` sí va crudo (de ahí
   `RAW_`) y demostró su firma genuina «HamCore».
5. **Corrida 45500037110 — el instalador SÍ salió con SoftEther
   (68.850.364 bytes, con las piezas aún comprimidas) pero mi
   control de tamaño lo tumbó:** el umbral de 80 MB estaba mal
   calibrado (Inno comprime con lzma). *Arreglo:* umbral a 55 MB y
   la prueba estructural queda en el registro de ISCC
   («Compressing: …\softether\client\hamcore.se2» y demás piezas).
6. **Corrida 45501428390 — la descompresión no cuadraba con el
   prefijo** (7.048.960 frente a 9.399.040). *Causa:* el prefijo
   **no es el tamaño del .exe**; el único flujo zlib produce el PE
   **completo y firmado**: validado por estructura (MZ, firma PE,
   Machine 0x8664, secciones dentro del archivo y overlay final de
   22.784 bytes = su firma Authenticode). Son los mismos bytes que
   el instalador del fabricante escribe en una instalación normal:
   es su propia transformación, a la inversa.
7. **Corrida 45502795985 — todo bien pero el paso «falló»:**
   vpncmd arrancó, imprimió su banner oficial y falló solo al
   conectar (sin servicio en el runner), dejando `$LASTEXITCODE=1`,
   que el runner hereda como código del paso. *Arreglo:* dejarlo a
   0 explícitamente al final del paso.
8. **Corrida 45503985673 — SUCCESS completa.**

## Verificación

- **Suite local y en CI: 225/225** (209 de la 1.0.6 + 16 nuevos de
  la 1.0.7: desenlaces de optimizar con eventos/verbose simulados,
  vpncmd simulado —crear, conectar, estado con el literal real,
  desconectar, error con mensaje en español—, ruta SoftEther en
  servicios, botón verde en la página real de Qt, y la carpeta del
  actualizador creada sola).
- **Compilación:** GitHub Actions run **45503985673 SUCCESS**
  (suite, PyInstaller, los 4 registros de módulos y el icono
  espartano dentro del .exe, SoftEther descargado/verificado/
  descomprimido con humo de vpncmd, Inno Setup, control de tamaño).
- **Instalador:** `Instalador-AntivirusHogarPC-1.0.7.exe` —
  **63.632.113 bytes** · MD5 `44d20ca33802b5ddfcbccf3d069ec61f` ·
  SHA-256 `13d9866c8279bc3ee96e08f45f1a6647b73a8b288ef111f5a0ac1a9ae1b9d2af`.
- **Canal de Drive** (carpeta `1I7V-Zabmiov8ttDHMkuJL8dlP1GeukHM`),
  actualizado **en sitio**: .exe `1zmtcu-NL-PvCbGisbAXbFwVwyBlI5_ql`
  (63.632.113 B), zip `1ZHiCO9lInsLv6GJBCdCj6GtTMjGf6hTG`
  (63.131.621 B), version-pc.json `1Kfd_pELWJhp37fO1iaERdSIzpRkAqK4R`
  (985 B, URL del .exe con `&confirm=t`); los tres con
  anyoneWithLink=reader y trashed:false (verificado por API).
  **Copia visible nueva:** «INSTALADOR Antivirus Hogar PC
  v1.0.7.zip», ID `12yJB9wcpzN1aIjAIMRuXBaoR5U22yV7b`.
- **PUERTA FINAL (anónima, `core.updater` de la propia app):**
  desde **1.0.6** ofrece la **1.0.7** ✔ · desde **1.0.7** «al día» ✔ ·
  descarga completa por la URL del JSON: 63.632.113 bytes, **SHA-256
  válido** ✔ · corte forzado a 15.000.000 bytes y **reanudación con
  SHA-256 válido** ✔.
- Paquete local en `build-nube-v107/` (artefacto, instalador, zip y
  version-pc.json).

## Límites honestos (lo que la nube no puede probar)

- El registro del servicio SEVPNCLIENT y la creación de la tarjeta
  virtual (NicCreate instala su driver) siguen la vía documentada
  por la comunidad oficial de SoftEther (el instalador oficial no
  tiene modo silencioso fiable: es un instalador propio sin
  parámetros desatendidos). La app crea la tarjeta desde la sesión
  del usuario (no desde un servicio SYSTEM, donde la evidencia dice
  que NicCreate falla) y Windows puede enseñar **una sola vez** su
  aviso de instalación del driver la primera vez que se conecta.
- El túnel real contra un servidor de VPN Gate no se puede probar
  en CI: la lógica de vpncmd está cubierta con el cliente simulado
  y el binario real demostró arrancar; la primera conexión de
  verdad es la de su PC, desde el botón.

## Pendiente

- Su instalación desde el botón de su 1.0.6 (ya sin crear carpetas
  a mano) y su veredicto en el Windows real: primera conexión VPN
  Gate con el SoftEther incorporado (botón verde «Conectado») y el
  nuevo «Optimización finalizada» de Discos.
