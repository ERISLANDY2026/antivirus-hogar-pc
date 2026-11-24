# INFORME — Antivirus Hogar PC v1.0.7

**Fecha:** 2026-11-24 · **Orden del usuario (llamada de voz, 16:25 EST):**
«Genera la próxima actualización para que venga con todo eso a través
del botón. Dale, arranca.» · **Base:** notas de su revisión de la
1.0.6 en su Toughbook real (`NOTAS-POST-V106.md`).

**Estado: COMPLETA Y ENTREGADA, con los REFUERZOS 4–7 incluidos.**
La 1.0.7 se entregó primero con los tres puntos de la orden de las
16:25 EST (suite 225/225, run **45503985673**) y, ANTES de que el
usuario la instalara, se reconstruyó con los cuatro refuerzos que
pidió en la misma llamada (16:31–17:04 EST): protección
anti-falso-positivo de Defender, bandeja del sistema, icono sin
fondo blanco, auto-actualizador de SoftEther con re-sincronización
y la puerta de diagnóstico VPN. **La versión entregada y vigente es
el build de los refuerzos:** suite **252/252**, compilación en la
nube en SUCCESS (run **45510314938**), canal de Drive actualizado
en sitio y **PUERTA FINAL SUPERADA** (anónima, con el código real
de la app). Como Defender borró su 1.0.6 instalada, el usuario
instalará esta 1.0.7 **manualmente desde la copia visible del zip
de Drive**. Pendiente solo esa instalación y su veredicto en el
Windows real.

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

## Los refuerzos (puntos 4–7, pedidos en la misma llamada)

### 4. Protección anti-falso-positivo de Defender (16:31 EST)

Windows Defender **borró la 1.0.6 instalada** en la PC real del
usuario (falso positivo clásico: ejecutable PyInstaller sin firmar
que toca hosts/PowerShell elevado y descarga-y-ejecuta su
actualizador). La 1.0.7 lo ataca en la instalación y al arrancar:

- **El instalador** (ya corre como admin) ejecuta
  `packaging/exclusion_defender.ps1`, versionado y declarado:
  `Add-MpPreference -ExclusionPath` SOLO para las dos carpetas
  propias —la de instalación y `%LOCALAPPDATA%\AntivirusHogarPC`—
  y **verificación leyéndola de vuelta** con `Get-MpPreference`.
  El resultado queda en `{app}\defender-exclusion.json`
  (`{app, datos, ya_estaban, error}`): constancia, nada oculto.
- **La app, al abrir** (`defender.comprobar_al_arranque`, gancho en
  `ui/main.py`): lee ese resultado, lo anota en el registro de
  actividad y, si la exclusión quedó **bloqueada** (Protección
  contra alteraciones o política), avisa con el paso manual mínimo
  (Seguridad de Windows → Exclusiones). Nunca finge que quedó
  puesta: sin resultado del instalador, el estado es «sin_datos» y
  no se afirma nada.
- **Integridad propia al arranque:** el instalador deja
  `{app}\componentes.json` (lista de componentes que deben existir:
  el .exe, el icono, el script de exclusión y las 4 piezas de
  SoftEther) y la app comprueba que siguen en su sitio; si un
  antivirus se llevó algo, queda registrado y se avisa.
- Tests: interpretación del resultado (aplicada / ya estaba /
  bloqueada con aviso / sin datos), rutas (solo las dos propias),
  integridad con manifiesto (todo presente / .exe borrado
  detectado) y el aviso de arranque según el estado.

### 5. Bandeja del sistema (16:55 EST, «Sí. Mételo.»)

- Módulo nuevo `ui/bandeja.py` (QSystemTrayIcon, sin dependencias
  nuevas): al arrancar —también con `--inicio-automatico`— la app
  vive junto al reloj. **Doble clic** abre/restaura la ventana;
  menú corto **Abrir / Escaneo rápido / Salir**; «Escaneo rápido»
  llama a la MISMA función que el botón de la página del escáner.
- **Cerrar la ventana ya no cierra la app:** se oculta a la bandeja
  (con un globito la primera vez por sesión que lo explica); salir
  de verdad es «Salir» del menú.
- **Globitos:** al terminar la rutina automática de arranque y
  cuando un escaneo termina **con hallazgos** (gancho en
  `ServiciosApp.registrar_escaneo`). La app sigue sin actuar sola
  ante amenazas: el globito avisa y decidir es del usuario.
- Tests con Qt offscreen: textos y disparo de las 3 acciones,
  doble clic sí / clic simple no, y el cierre de la ventana real
  (se oculta, avisa una vez; «Salir» cierra de verdad).

### 6. Icono del espartano sin fondo blanco (16:55 EST)

- El arte (`packaging/icono-espartano.webp`) es un emblema de
  escudo sobre blanco: el blanco EXTERIOR se quitó por relleno
  desde los bordes (el campo blanco INTERIOR del escudo es parte
  del diseño y se mantuvo), con mate suave y descontaminación del
  halo blanco; la figura llena el cuadro (recorte a su caja).
  Resultado: esquinas con alfa 0 y **31,7 % de píxeles
  transparentes**. Regenerados `packaging/icono.ico`,
  `assets/icono_app.ico` (16→256) y `packaging/icono.png`.
- Evidencia visual en `evidencia-v107/`
  (`icono-antes-despues.png` sobre damero y fondo oscuro —sin halo
  apreciable— e `icono-borde-zoom.png`).
- `scripts/verificar_icono.py` ampliado: la comprobación que CI
  hace del icono dentro del .exe ahora exige además esquinas
  transparentes y ≥10 % de transparencia en la imagen de 256 (con
  decodificador PNG propio, sin dependencias). Tests: el icono
  nuevo pasa y un PNG opaco de control es rechazado.

### 7. Auto-actualizador de SoftEther + re-sincronización (17:03–17:04 EST)

Módulo nuevo `winapi/softether_update.py`. Cada **3 días** (al
abrir la app, en segundo plano, sin bloquear la interfaz; el
estado vive en `softether_update.json` de la carpeta de datos):

- **Fuentes OFICIALES verificadas en vivo el 2026-11-24 antes de
  cablearlas** (si una falla, se pasa a la siguiente):
  1. GitHub del proyecto, repo **SoftEtherVPN_Stable**, etiquetas:
     `https://api.github.com/repos/SoftEtherVPN/SoftEtherVPN_Stable/tags?per_page=5`
     → la más nueva, `v4.44-9807-rtm`. (Ojo verificado: su
     «último release» de GitHub está atrasado en 4.41; las
     etiquetas sí van al día, por eso se usan etiquetas.)
  2. Historial oficial: `https://www.softether.org/5-download/history`
     → primera entrada «4.44 Build 9807 RTM (April 16, 2025)».
  3. Listado oficial `https://www.softether-download.com/files/softether/`
     → aporta versión **y** la carpeta con fecha, imprescindible
     para construir la URL de descarga.
  4. El listado de la carpeta del cliente de esa versión → nombre
     exacto del instalador y su **tamaño** para verificar.
- Si hay versión más nueva: descarga el instalador oficial, lo
  verifica (tamaño del listado + estructura: los archivos del
  cliente se extraen de sus recursos DATAFILE con un **lector PE
  propio en Python puro** —el mismo formato verificado en la
  compilación— y cada .exe debe descomprimir a un PE x64 válido y
  el hamcore llevar su firma) y lo deja preparado.
- **Aplicación sin molestar y sin cortar conexiones:** si hay un
  túnel VPN activo, la actualización queda DIFERIDA (anotada) y se
  aplica al cerrar la conexión (gancho en la desconexión de la
  app) o en el siguiente arranque sin túnel. Aplicar = parar
  SEVPNCLIENT, sustituir los archivos de `{app}\softether` y
  rearrancar, vía UN script elevado: pide **una** confirmación de
  administrador (UAC), que es el mínimo honesto en Windows para
  tocar un servicio y Archivos de programa; si se deniega, queda
  pendiente y registrado, sin fingir.
- **Re-sincronización tras cada actualización** (complemento de
  las 17:04): la app re-detecta `vpncmd` en su ruta (pudo
  cambiar), verifica que responde, que el servicio SEVPNCLIENT
  quedó registrado (parsers de `sc query`/`sc qc`), que la tarjeta
  virtual y la conexión de VPN Gate siguen vivas —si la
  actualización las borró, las **recrea sola** igual que en la
  instalación inicial (la cuenta, contra el último servidor
  usado)— y corre la mini-diagnóstico. Queda en el registro
  «SoftEther actualizado a X y re-sincronizado con la app» o el
  detalle exacto de lo que no se pudo; globito solo cuando
  actualiza, o si la re-sincronización falló.
- Si las fuentes fallan todas: se anota y se reintenta en el
  siguiente ciclo, sin mensajes repetidos.
- Tests: parsers de versión de las 3 clases de fuente, comparación
  (mayor/igual/menor), cadencia (antes de 3 días no, después sí),
  cadena de fuentes con fallos simulados hasta la que responde y
  con todas caídas, `datos_descarga` desde el listado, el
  extractor PE contra un instalador SINTÉTICO con recursos
  DATAFILE reales, la aplicación diferida con túnel activo (no se
  eleva ni se toca nada) y la re-sincronización en 4 escenarios
  (perfil intacto / perfil borrado que se recrea / vpncmd en ruta
  nueva / servicio sin registrar, que se reporta y no se finge).
  **Y en CI, contra el instalador oficial REAL** recién descargado:
  paso nuevo del workflow que ejecuta `preparar_cliente` y exige
  las 4 piezas con sus tamaños exactos (7.048.960 / 7.055.104 /
  7.240.448 / 23.209.854 B) — pasó en las corridas 45508739880 y
  45510314938.

## Diagnóstico VPN (puerta pedida a las 16:59 EST)

Evidencia, separando lo probado en automático de lo que solo se
puede probar en la PC real:

**Probado en automático (suite 252/252 + CI):**

1. **El instalador final contiene SoftEther de verdad:** en el
   registro de ISCC de la corrida SUCCESS 45510314938 constan las
   líneas «Compressing: …\softether\client\vpnclient_x64.exe /
   vpncmd_x64.exe / vpncmgr_x64.exe / hamcore.se2 /
   SOFTETHER-CLIENT.txt / lang.config» y también
   «Compressing: …\packaging\exclusion_defender.ps1»; el paso
   «Verificar que el instalador lleva SoftEther» del workflow
   (tamaño ≥55 MB con la estructura dentro) pasó.
2. **La lógica de instalación queda ejercitada en tests:** qué se
   instala (los archivos del cliente en `{app}\softether`), dónde,
   y cómo se comprueba que el servicio quedó registrado/arrancable
   (`estado_servicio_softether` con los parsers de `sc query` y
   `sc qc` probados: registrado/corriendo/inicio auto-manual, y el
   error 1060 = no registrado).
3. **vpncmd localizado desde la ruta REAL de instalación:** la
   detección busca en `{app}\softether`, en las rutas de Programa
   de SoftEther y en el PATH (test con ruta simulada: diagnóstico
   completo con NIC y cuentas; test con ruta ausente: `instalado`
   falso y mensaje claro, sin inventar rutas).
4. **Ciclo completo con vpncmd falso pero fiel** (el de la suite,
   que aserta `/SERVER:host:443`, `/HUB:VPNGATE`, `/USERNAME:vpn`,
   `/NICNAME:VPN`): crear la conexión VPNGATE → conectar → el
   botón de la página se pone VERDE y dice «Conectado» → 
   desconectar → estado limpio. Y los **errores típicos con su
   mensaje específico en español** (refuerzo de esta puerta; antes
   eran genéricos): servicio caído → «El servicio de SoftEther no
   responde: parece caído o sin arrancar…»; autenticación
   rechazada → «El servidor rechazó el inicio de sesión
   (autenticación)…»; servidor que no responde → «El servidor X no
   respondió o cortó la conexión…». (El test heredado que esperaba
   el mensaje genérico se actualizó a este contrato nuevo.)
5. **La lista de servidores sigue poblando** (semilla + cadena de
   fuentes, como en la 1.0.6) y cada servidor lleva lo que vpncmd
   necesita: hostname no vacío, puerto 443, hub «VPNGATE»,
   usuario/contraseña «vpn» (test sobre la semilla real).
6. **Mini-diagnóstico de integración** (`diagnostico_softether`):
   vpncmd localizado, servicio, tarjeta virtual y cuentas en una
   sola pasada — es la misma lógica que usa la re-sincronización
   del punto 7.

**Lo que SOLO se puede probar en su PC real (no afirmado aquí):**

- Levantar el **túnel de verdad** contra un servidor VPN Gate en
  vivo (en CI no hay VPN real ni servicio SoftEther corriendo): la
  primera conexión desde el botón, con el aviso único de Windows
  al instalar el driver de la tarjeta virtual.
- Que el servicio SEVPNCLIENT, registrado por nuestro instalador
  vía `sc create`, arranque en su Windows 10 y que vpncmd hable
  con él allí.
- La exclusión de Defender aplicada en su equipo (depende de su
  Protección contra alteraciones) y el ciclo real del
  auto-actualizador cuando SoftEther publique la próxima versión.

**No se escribe «VPN verificada funcionando» más allá de esta
evidencia:** lo de arriba es lo probado; el túnel real queda
pendiente de su primera conexión en la Toughbook.

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
9. **La primera corrida de los refuerzos (45508739880) falló en
   Inno Setup: «Error on line 185: 'BEGIN' expected».** *Causa:*
   el comentario Pascal `{ … }` del punto 4 en `instalador.iss`
   llevaba dentro la constante `{app}` — y la llave de cierre de
   la constante **cerraba el comentario** a mitad de frase; el
   resto del comentario quedó como código y el compilador se
   descompuso hasta la declaración siguiente. *Arreglo:*
   comentario reescrito sin constantes entre llaves (commit
   16a580d); la corrida siguiente, **45510314938, SUCCESS
   completa**. Todo lo demás de la corrida fallida había pasado:
   suite, PyInstaller, icono y el paso nuevo del extractor.
10. **La suite local no podía importar Qt (libEGL.so.1 ausente).**
    *Causa:* la VM de trabajo se recreó y perdió los paquetes de
    sistema que la sesión anterior había instalado por apt; los
    tests de páginas/bandeja fallaban al importar PySide6 con
    `ImportError: libEGL.so.1`. No era el código: la restauración
    automática de paquetes de la propia VM la repuso y la suite
    local cerró **252/252**. (En CI, con Windows real, la suite
    pasó desde la primera corrida de los refuerzos.)
11. **El resumen de contexto describía la integridad del punto 4
    con hashes; el código real usa manifiesto-lista.** Al retomar
    el trabajo se comprobó el código y el instalador: ambos
    concuerdan entre sí (el instalador escribe `componentes.json`
    como lista de rutas y la app verifica su existencia). Los
    tests se escribieron contra el código real, no contra el
    resumen.

## Verificación

- **Suite local y en CI: 252/252** (209 de la 1.0.6 + 16 de los
  puntos 1–3 + **27 de los refuerzos** en
  `tests/test_v107_refuerzos.py`: Defender —interpretación,
  rutas, integridad, aviso—, bandeja —menú, acciones, cierre a la
  bandeja—, icono transparente, auto-actualizador —versiones,
  fuentes, cadencia, extractor PE, diferido, re-sincronización— y
  diagnóstico VPN —sc query/qc, diagnóstico con ruta simulada y
  ausente, errores típicos en español, datos por servidor—).
- **Compilación:** GitHub Actions run **45510314938 SUCCESS**
  (suite, PyInstaller, los 4 registros de módulos y el icono
  espartano —ahora con la transparencia comprobada— dentro del
  .exe, SoftEther descargado/verificado/descomprimido con humo de
  vpncmd, **el extractor del auto-actualizador ejercitado contra
  el instalador oficial real**, Inno Setup, control de tamaño).
  La entrega de los puntos 1–3 fue la corrida 45503985673, también
  SUCCESS; este build la sustituye por completo.
- **Instalador (build vigente, el de los refuerzos):**
  `Instalador-AntivirusHogarPC-1.0.7.exe` — **63.688.882 bytes**
  (+56.769 sobre el build de los puntos 1–3: el script de
  exclusión, la bandeja, el auto-actualizador y el icono nuevo) ·
  MD5 `1c39e0ba03e02d4e8b6ef2276b5325c2` · SHA-256
  `4f2402dd7c8cd2e9696e75f7e6bac52fa745ab961a393595951f1e42e0f72cd0`.
- **Canal de Drive** (carpeta `1I7V-Zabmiov8ttDHMkuJL8dlP1GeukHM`),
  actualizado **en sitio**: .exe `1zmtcu-NL-PvCbGisbAXbFwVwyBlI5_ql`
  (63.688.882 B), zip `1ZHiCO9lInsLv6GJBCdCj6GtTMjGf6hTG`
  (63.179.636 B), version-pc.json `1Kfd_pELWJhp37fO1iaERdSIzpRkAqK4R`
  (1.661 B, con las notas de los 7 puntos y la URL del .exe con
  `&confirm=t`); los tres con anyoneWithLink=reader y
  trashed:false (verificado por API, permisos leídos uno a uno).
  **Copia visible nueva:** «INSTALADOR Antivirus Hogar PC
  v1.0.7.zip», ID `1ahTzOaE3KqBZSCnqHqeERpDBNAucBBHA`
  (63.179.636 B); la copia visible del build anterior
  (`12yJB9wcpzN1aIjAIMRuXBaoR5U22yV7b`, sin refuerzos) quedó
  **en la papelera** para que no se instale por error.
- **PUERTA FINAL (anónima, `core.updater` de la propia app,**
  script en `build-nube-v107/puerta-final.py`): desde **1.0.6**
  ofrece la **1.0.7** ✔ · desde **1.0.7** «al día» ✔ · descarga
  completa por la URL del JSON: 63.688.882 bytes, **SHA-256
  válido** ✔ · corte forzado a 15.000.000 bytes y **reanudación
  con SHA-256 válido** ✔.
- Paquete local en `build-nube-v107/` (instalador, zip,
  version-pc.json y el script de la puerta) y el artefacto de CI
  en `build-nube-v107-refuerzos/`.

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

- **Su instalación MANUAL desde la copia visible del zip de
  Drive** («INSTALADOR Antivirus Hogar PC v1.0.7.zip», ID
  `1ahTzOaE3KqBZSCnqHqeERpDBNAucBBHA`): su 1.0.6 ya no está en la
  PC (Defender la borró), así que esta vez no entra por el botón.
  Las siguientes versiones sí entrarán por el botón desde esta.
- Su veredicto en el Windows real: primera conexión VPN Gate con
  el SoftEther incorporado (botón verde «Conectado»), el nuevo
  «Optimización finalizada» de Discos, la exclusión de Defender
  (que en su equipo quede aplicada o el aviso con el paso manual)
  y la vida en la bandeja junto al reloj.
