# INFORME — Antivirus Hogar PC v1.0.6

**Fecha:** 2026-11-24 · **Orden del usuario:** llamada de voz ~14:50–15:13 EST
(«Empieza ya autorizado… que funcione y que entre por el botón»).
**Alcance:** bloqueador/hosts (tarea original) + notas 1 a 9 de su prueba
de la 1.0.5 en su Toughbook CF-54 real. **Condición de entrega suya:**
cada error reportado con causa raíz, corrección y test de regresión
superado; si alguna partida no quedaba verificada, no se entregaba.

## Entrega (números)

- **Suite:** 209 tests (168 de la 1.0.5 + 41 nuevos), verde en un solo
  proceso local y verde en CI sobre Windows.
- **GitHub Actions:** run final **45481319247 = SUCCESS** (suite completa
  en Windows + verificación de módulos y del icono dentro del .exe).
  Corridas previas de esta versión: 45476164035 SUCCESS (solo
  bloqueador), 45479571554 y 45480688678 FAILURE — la suite se abortaba
  a mitad en Windows; la causa se encontró y se corrigió (ver
  «Hallazgo durante la entrega»).
- **Instalador:** `Instalador-AntivirusHogarPC-1.0.6.exe`,
  40.619.617 bytes, MD5 `53437aba2d2ae10f42ca88f67b2eba2d`,
  SHA-256 `7b6c98e43636bfa92a5da171568c1c91d8390f83b6ef16e4161c8a945cf97f21`.
- **Zip del canal:** `AntivirusHogarPC-Instalador-v1.0.6.zip`,
  40.109.193 bytes, MD5 `3433c89a2635eaf8781f59a9a01503c8`.
- **Drive (en sitio, IDs conservados, anyoneWithLink=reader y
  trashed:false verificados listando la carpeta y los permisos):**
  zip `1ZHiCO9lInsLv6GJBCdCj6GtTMjGf6hTG`, .exe
  `1zmtcu-NL-PvCbGisbAXbFwVwyBlI5_ql`, version-pc.json
  `1Kfd_pELWJhp37fO1iaERdSIzpRkAqK4R` (URL del instalador con
  `&confirm=t`). MD5 de Drive = MD5 local en los tres.
  Copia visible nueva: «INSTALADOR Antivirus Hogar PC v1.0.6.zip»,
  ID `1PqJ6O7qjyZRbRvfH0KU7ELUstFV8qiEA`, pública, MD5 idéntico.
- **Evidencia visual:** 11 renders en `evidencia-v106/` (radar en dos
  instantes, muerte y renacimiento de los bichitos, iconos en dos
  instantes, borde de tarjeta en dos instantes, página de red con la
  VPN poblada, programador).

## PUERTA FINAL (anónima, con el código real de la app — core.updater)

- Desde **1.0.3**: ofrece la **1.0.6**. ✔
- Desde **1.0.5** (su app instalada; el camino real del botón): ofrece
  la **1.0.6**. ✔
- Desde **1.0.6**: «al día» (sin oferta). ✔
- Descarga completa n.º 1 por la URL del JSON: 40.619.617 bytes,
  SHA-256 válido. ✔
- Descarga completa n.º 2: 40.619.617 bytes, SHA-256 válido. ✔
- Corte forzado a 15.000.000 bytes y reanudación con el descargador
  resistente: completa a 40.619.617 bytes, SHA-256 válido. ✔

## Hallazgo durante la entrega (problema nuevo, reportado al aparecer)

La suite se **abortaba a mitad de proceso** en CI (y local en corrida
única): un hilo `QThread` destruido mientras aún corría tumba el
proceso entero. La descarga real de VPN Gate (o la lectura del informe
del Panel, que en Windows tarda por PowerShell) seguía viva cuando su
página/ventana ya se había destruido. Corrección de raíz en las tres
familias de páginas (Red, Panel y Seguridad): al destruirse la página,
los hilos en curso se **despadrean** y terminan solos, autoborrándose
al acabar (`finished → deleteLater`); nunca más se destruye un hilo
en curso. Con eso la suite corre entera en un solo proceso (209/209)
y la corrida de Windows salió SUCCESS. Es también un arreglo real de
la app: cerrar la ventana con trabajo en curso ya no puede tumbarla.

## LISTA DE VERIFICACIÓN — partida por partida

### 1. Bloqueador / hosts (tarea original)
- **Lo que pasaba:** con el bloqueo activo su PC quedó «conectado, sin
  internet» (la sección gigante en el hosts rompía la resolución) y el
  botón «Quitar bloqueo» falló con el error crudo de PowerShell
  («being used by another process»): el hosts estaba en uso y no había
  ni reintentos ni otra vía. La limpieza solo se logró desde el
  entorno de recuperación de Windows.
- **Corrección:** escritura y restauración robustas — 6 reintentos con
  espera ante archivo ocupado y, si sigue ocupado, **reemplazo
  programado para el reinicio** (MoveFileEx) con aviso claro en
  español («quedará aplicado al reiniciar»); el error crudo nunca
  llega a la pantalla (causa breve en español; detalle solo al
  registro). Al **activar**: flushdns + autocomprobación de resolución
  de dominios conocidos y **reversión automática al respaldo** si la
  navegación falla. **Autorreparación al abrir**: bloque propio dañado
  o restauración pendiente se deja limpio y se anota en la actividad.
  Solo se toca la sección propia, con respaldo previo, como siempre.
- **Test de regresión:** 21 tests (`tests/test_v106.py`): escritura con
  el archivo ocupado simulado (reintento y vía programada),
  autocomprobación con resolución fallida simulada → reversión al
  respaldo, autorreparación con bloque dañado simulado, y que el
  mensaje visible no contiene el error crudo. **Superados.**

### 2. Discos — «Optimizar volúmenes» sin causa y barra que se dispara
- **Lo que pasaba:** usted veía «La optimización de la unidad C no se
  completó. Causa de Windows: causa desconocida» y la barra saltaba de
  golpe al 100 %. Causas: (a) si el archivo de resultado no traía
  «OK»/«ERROR:», la causa caía en «causa desconocida» y el contenido
  crudo se perdía al borrarse la carpeta temporal; (b) el progreso no
  era gradual porque la salida verbose de PowerShell llegaba
  amortiguada y de golpe al final.
- **Corrección:** el script garantiza archivo de resultado (`finally`)
  y anexa el verbose **registro a registro** (AppendAllText), así el
  progreso avanza de verdad; un intérprete nuevo busca la causa en la
  cola del verbose y, si Windows no da causa, lo dice así y guarda el
  detalle completo (resultado crudo + cola) en el registro de
  actividad.
- **Test de regresión:** causa real extraída del verbose, resultado sin
  causa declarada, script con AppendAllText y sin la tubería
  amortiguada, y progreso gradual registro a registro. **Superados**
  (`tests/test_v106_paginas.py`).

### 3. Red — Wi-Fi «todavía sin leer» y botón muerto
### 4. Red — «Medir velocidad» muerto
### 5. Red — VPN Gate: desplegable vacío y botón muerto
- **Lo que pasaba (las tres, una sola causa raíz, demostrada con
  sonda):** la ventana principal conserva solo el *widget* que
  devuelve la factoría de la página; el objeto que lleva los botones
  y temporizadores de la página de Red quedaba **sin ninguna
  referencia viva y Python lo destruía** nada más crearse. Por eso ni
  siquiera salía el «cargando»: los botones quedaban conectados a un
  objeto muerto, la autocarga del Wi-Fi nunca corría («todavía sin
  leer») y la lista de respaldo de VPN Gate nunca poblaba el
  desplegable. Las demás páginas se salvaban por casualidad (las
  construían clausuras que sí quedaban referenciadas).
- **Corrección:** el objeto página queda **anclado a su propio
  widget** al crearse (`_conservar`), así vive mientras la página se
  ve — el mismo arreglo en la página de Actualizaciones, que tenía el
  mismo defecto latente.
- **Test de regresión:** la página construida como la construye la
  ventana sigue **viva tras pasar el recolector de basura**, la
  semilla puebla el desplegable sin red (9 países + «Todos», ≥30
  servidores) y los **tres botones se pulsan de verdad** y arrancan su
  trabajo con su feedback («Leyendo…», «Midiendo…», «Actualizando…»).
  **Superados** (`tests/test_v106_paginas.py`).

### 6. Programador de tareas global en «Desactivado» (las seis)
- **Lo que pasaba:** la misma familia de causa raíz: la tarjeta de
  programación de cada tarea era otro objeto Python sin padre que
  **moría al crearse**; «Guardar y aplicar» no ejecutaba nada y la
  etiqueta «Próxima ejecución» nunca se actualizaba — por eso pasaba
  en las SEIS programaciones a la vez. (Descartada la hipótesis del
  parseo en español: la existencia de la tarea se decide por el código
  de salida de schtasks, no leyendo su texto.) Defecto secundario
  real: la creación devolvía solo sí/no y **tiraba la salida de
  schtasks**, así que un rechazo de Windows era invisible.
- **Corrección:** las tarjetas quedan ancladas a su página; la
  creación devuelve ahora (sí/no, **causa breve en español**, detalle
  crudo): la página enseña la causa breve y el crudo va solo al
  registro de actividad.
- **Test de regresión:** ciclo guardar→consultar de las **SEIS**
  tareas con schtasks simulado en español y en inglés, y fallo de
  creación visible en la página sin texto crudo. **Superados**
  (`tests/test_v106_paginas.py`).

### 7. Iconos sin 3D ni animación + acabado visual de las secciones
- **Lo que pasaba:** en la 1.0.5 el animador solo movía la pestaña
  activa o la que tenía el ratón encima, y con una amplitud mínima
  (±5 %): el panel se veía congelado. No era un fallo de
  temporizadores; era una animación diseñada casi invisible.
- **Corrección:** iconos con 3D reforzado (canto oscuro extruido,
  gradiente de tres paradas y brillo de cristal) y **animación
  continua y visible en todos**: flotación suave desfasada por icono
  y una banda de brillo que cruza cada icono cada pocos segundos; la
  pestaña activa pulsa más y la de Actualizaciones gira. Las tarjetas
  de todas las secciones llevan vidrio siempre y un **borde con
  recorrido de color animado** (tenue en reposo, fuerte en la activa).
  Todo el movimiento cuelga de **UN solo reloj compartido de 50 ms**
  (rendimiento cuidado para su Toughbook) y lo gobierna el interruptor
  de Ajustes, que ahora se llama «Animaciones de la interfaz (iconos,
  bordes con movimiento y fondo del Panel)» y apaga todo al momento.
- **Test de regresión:** un icono **inactivo** cambia entre dos
  instantes (antes solo se movía el activo), con la puerta apagada no
  se mueve nada, el borde de una tarjeta difiere entre dos instantes,
  y hay un único temporizador compartido. Evidencia: renders del mismo
  icono y del mismo borde en dos instantes. **Superados**
  (`tests/test_v106_visual.py` + `evidencia-v106/`).

### 8. El icono del espartano cyborg no se veía en su PC
- **Lo que pasaba:** la 1.0.5 sí llevaba el espartano dentro del .exe
  (CI lo verificó), pero la app **nunca fijaba el icono de su ventana
  al ejecutarse**, y al actualizar encima, los accesos directos viejos
  y la **caché de iconos de Windows** seguían enseñando el icono
  anterior.
- **Corrección:** la app fija el espartano como icono de ventana (y de
  la barra de tareas) al arrancar, desde un `icono_app.ico` incluido
  en el paquete; el instalador 1.0.6 **borra los accesos directos
  viejos**, instala `icono.ico` junto al .exe, recrea los accesos
  apuntando a ese archivo y **refresca la caché de iconos de Windows**
  al terminar la instalación (SHChangeNotify).
- **Test de regresión:** el .ico viaja en los assets y coincide con el
  oficial, el código fija el icono de la aplicación, y el instalador
  contiene el borrado de accesos viejos, el `IconFilename` y el
  refresco de caché. **Superados** (`tests/test_v106_paginas.py`).
  La confirmación visual final —como en cada versión— es la suya tras
  instalar en su Windows real: es el único punto que no se puede ver
  desde aquí, y queda dicho tal cual.

### 9. Radar de Inicio (rediseño pedido por usted)
- **Lo que pasaba:** el barrido de la 1.0.5 «se veía un poco falso»:
  cuña corta que no cubría la imagen y franja dura sin desvanecido.
- **Corrección:** `ui/fondo_radar.py` reescrito — pantalla futurista
  premium: barrido **verde eléctrico con radio hasta la esquina**
  (cubre la imagen entera), **estela de fósforo** con 64 sectores y
  caída exponencial (nada de franja plana), **ondas de escaneo que se
  expanden**, cúpula de cristal 3D con bisel luminoso, scanlines y
  centelleo eléctrico sutil; anillos y marcas de rumbo conservados.
  Los bichitos (dibujos de siempre) **MUEREN al paso del haz**
  (destello blanco, anillo de choque, se encogen y desvanecen) y
  **RENACEN** en otro punto (crecen con halo), en ciclo continuo.
  Respeta el interruptor de animaciones.
- **Test de regresión:** el radio del barrido alcanza la esquina del
  lienzo, un bichito tocado por el haz entra en «muriendo» y luego
  «renaciendo», y con la animación apagada nada se mueve. Evidencia:
  renders del barrido en dos instantes, del instante de muerte y del
  renacimiento. **Superados** (`tests/test_v106_visual.py` +
  `evidencia-v106/`).

## Pendiente (del usuario, como en cada versión)
- Instalar la 1.0.6 desde el botón de su app (la puerta final probó
  ese camino anónimo con el código real: desde su 1.0.5 ofrece la
  1.0.6 y la descarga completa con SHA válido) y su veredicto en el
  Windows real, incluida la vista del icono espartano tras el
  refresco de accesos directos y caché.
