# Informe v1.0.4 — Fallo del escaneo: SQLite usado desde otro hilo

Un solo problema, reportado por Erislandy con foto probando la v1.0.3
en su Windows real (2026-11-24 10:57 EST): al darle a «Escaneo rápido»,

> «El escaneo falló — ⚠ El escaneo no se pudo completar: SQLite objects
> created in a thread can only be used in that same thread. The object
> was created in thread id 5944 and this is thread id 8588.»

Autorización expresa del usuario para procesar/ejecutar el código:
«dale», 2026-11-24 10:21 EST, y la orden directa de esta reparación al
mostrar el error.

## Causa raíz (verificada en el código)

La caché de escaneo `CacheEscaneo` (core/scancache.py) es el ÚNICO
objeto SQLite de la app. Su conexión se creaba UNA vez, en el
constructor, y la instancia nace en el hilo principal de la ventana
(`ServiciosApp.__init__` en ui/services.py, y la auto-prueba de
ui/main.py). El escaneo corre en el QThread `_TrabajadorEscaneo`
(modules/security/page.py) y usa ESA misma conexión vía
scanner.escanear(cache.buscar/guardar/confirmar). sqlite3 de Python
prohíbe usar una conexión en un hilo distinto al que la creó
(check_same_thread por defecto) → ProgrammingError y escaneo abortado.

Nota: en la v1.0.2 el mismo fallo quedaba tragado (la barra se quedaba
en «Escaneando…»); la v1.0.3 lo hizo visible con el try/except nuevo.
La corrección ataca la CAUSA, no el mensaje.

Alcance revisado: la base de firmas (core/signatures.py) es en memoria
(diccionarios, solo lectura durante el escaneo) y analizar_archivo /
la vigilancia de instalaciones no tocan SQLite; el registro de
actividad es JSONL y la cuarentena es sistema de archivos. El único
cruce de hilos era la caché — y todos los modos de escaneo (rápido,
completo y por carpeta) pasan por el mismo trabajador y la misma
caché, así que la corrección los cubre todos.

## Corrección

1. **Conexión por hilo en CacheEscaneo:** cada hilo tiene su propia
   conexión (threading.local) sobre el mismo archivo, creada
   perezosamente la primera vez que ese hilo la pide — la conexión
   nace en el hilo que la usa, que es lo que sqlite exige. Un Lock
   serializa las escrituras (guardar/confirmar) entre hilos, la
   conexión usa timeout de 30 s y modo WAL como mejora de
   concurrencia. La API pública (buscar/guardar/confirmar/total/
   cerrar) no cambia; cerrar() cierra todas las conexiones
   registradas tolerando las ajenas.
2. **Mensaje al usuario en español claro:** nuevo
   core/textos_error.py::mensaje_para_usuario(). El trabajador de
   escaneo ahora enseña una frase comprensible («La base de datos
   interna de la app chocó con otra tarea en curso…» para el error de
   hilos/SQLite, con equivalentes para permiso denegado y archivo no
   encontrado) y el detalle técnico crudo se guarda SOLO en el
   registro de actividad («Error técnico del escaneo: …»).

## Prueba de regresión (obligatoria, tests/test_v104.py)

- test_escaneo_desde_otro_hilo_completa_con_cache_creada_en_principal:
  crea BaseFirmas y CacheEscaneo en el hilo principal (como
  ServiciosApp) y ejecuta escanear() en un hilo distinto (como el
  QThread de la UI) sobre una carpeta temporal con 2 ejecutables, uno
  con huella sembrada en la base: el escaneo COMPLETA sin
  ProgrammingError, revisa 2, detecta el hallazgo, la caché queda
  escrita (total 2) y un segundo escaneo en un tercer hilo reutiliza
  la caché (archivos_desde_cache == 2).
- test_cache_uso_cruzado_directo_entre_hilos: guardar/confirmar en un
  hilo, buscar/total en el principal.
- Dos tests de mensaje: el texto exacto del error de la foto se mapea
  a español sin inglés técnico, y un OperationalError genérico de
  SQLite también.

## Verificación de la entrega

- Suite local completa (Qt offscreen real): **120 passed** (116 de la
  v1.0.3 + 4 nuevos), 0 fallos.
- GitHub Actions run **45435933145**: `completed / success` — suite en
  Windows + verificación de los 4 registros de módulos dentro del
  ejecutable (regresión v1.0.0). El workflow se disparó por
  workflow_dispatch (solo salta por dispatch o tags v*).
  https://github.com/ERISLANDY2026/antivirus-hogar-pc/actions/runs/45435933145
- Código: commit local `1174281`, commit remoto
  `caba8e0f493d45d503aa9c7abf1d89641e7fbdf0` (8 archivos por Git Data
  API).
- Instalador: `Instalador-AntivirusHogarPC-1.0.4.exe`, **39.772.643
  bytes**, PE32 GUI Windows (Inno Setup), MD5
  `4622e144edbaef376eb5440462b1fb26`, SHA-256
  `ff79f0d1600ca72e8e64a33b9de539e04cf6e339bd5beda1469461835e461470`.
- Drive actualizado EN SITIO y verificado leyendo los metadatos de
  vuelta: zip `1ZHiCO9lInsLv6GJBCdCj6GtTMjGf6hTG` renombrado a
  `AntivirusHogarPC-Instalador-v1.0.4.zip` (39.221.836 B, MD5
  `df8d313c052a0ece497258613b5ed297`, idéntico al local) y .exe suelto
  `1zmtcu-NL-PvCbGisbAXbFwVwyBlI5_ql` renombrado a
  `Instalador-AntivirusHogarPC-1.0.4.exe` (MD5 idéntico al local);
  version-pc.json `1Kfd_pELWJhp37fO1iaERdSIzpRkAqK4R` a 1.0.4 con el
  SHA-256 nuevo. **Verificación anti-papelera (lección del 2026-11-24):
  los tres archivos leen `trashed: false` y aparecen visibles al
  listar la carpeta «Antivirus Hogar PC».**
  https://drive.google.com/file/d/1ZHiCO9lInsLv6GJBCdCj6GtTMjGf6hTG/view?usp=drivesdk
- Canal en vivo verificado con la lógica real de la app
  (core.updater.comprobar_actualizacion contra la URL de Drive):
  desde **1.0.3 → ofrece la 1.0.4** con su SHA-256; desde **1.0.4 →
  «al día»**.

## Addenda (2026-11-24, tras la prueba en su PC real)

Su v1.0.3 recibió un 404 («no encontrado») al buscar actualizaciones y
la descarga del instalador por la URL publicada devolvía la página de
advertencia de virus de Google, no el .exe. Corregido y verificado de
forma ANÓNIMA con el código real de la app (la verificación «en vivo»
de arriba se había hecho autenticada y no era válida como prueba del
canal). Detalle completo y regla nueva de verificación:
**INFORME-CANAL.md**.

## Pendiente honesto

- El instalador v1.0.4 aún NO se ha ejecutado en el Windows real de
  Erislandy; la verificación automática (suite con el test de
  regresión entre hilos + registros dentro del .exe + canal en vivo)
  está pasada, pero la prueba final en su PC queda de su lado, como en
  las versiones anteriores. Su app v1.0.3 le ofrecerá sola la 1.0.4
  desde «Actualizaciones → Buscar actualizaciones de la app».
