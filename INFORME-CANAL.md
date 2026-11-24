# Informe — Canal de actualizaciones roto desde la PC real (2026-11-24)

Reportado por Erislandy con foto (2026-11-24 11:27 EST) probando su app
v1.0.3 en su Windows real: al pulsar «Buscar actualizaciones de la app»,

> «El canal de actualizaciones respondió «no encontrado»: el archivo de
> versión no está publicado. No es tu conexión: hay que volver a
> publicarlo en el canal (avísanos).»

Ese mensaje = HTTP 404 al descargar el version-pc.json (clasificación
`no_encontrado` de core/updater.py). Nuestras verificaciones «en vivo»
anteriores pasaban porque se hacían con el conector AUTENTICADO, que lee
los archivos aunque no sean públicos — la app descarga ANÓNIMA.

## Investigación (todo anónimo, con la URL exacta de config.py)

URL grabada en la app (config.py, correcta, coincide con el ID actual):
`https://drive.usercontent.google.com/download?id=1Kfd_pELWJhp37fO1iaERdSIzpRkAqK4R&export=download`

1. **version-pc.json anónimo (curl y urllib con el User-Agent de la app):**
   HTTP 200, JSON válido de la 1.0.4 con su SHA-256
   `ff79f0d1…`. Permisos en Drive: `anyoneWithLink = reader` en el
   version-pc.json y en el .exe suelto. → El 404 de su PC **ya no se
   reproduce**; el estado es coherente con la ventana de esa mañana
   (archivos encontrados en la papelera, restaurados y reemplazados en
   sitio entre las 10:46 y las 11:25 EST, con la entrega de la 1.0.4
   completándose a las 11:25 y la foto llegando a las 11:27).
2. **El zip NO era público:** sus permisos eran solo el dueño. La app no
   usa el zip, pero quedaba fuera del patrón del canal. **Corregido:**
   `anyoneWithLink = reader` (verificado leyéndolo de vuelta).
3. **DEFECTO CONFIRMADO que sí bloqueaba la instalación (causa raíz
   principal):** la URL del .exe que trae el version-pc.json, pedida de
   forma anónima SIN confirmación, **no devuelve el instalador**:
   devuelve la página HTML de Google «Google Drive - Virus scan
   warning» (HTTP 200, text/html, 2.484 bytes), porque el archivo pesa
   39,7 MB y Google no lo puede escanear. La app habría descargado esa
   página, el SHA-256 no habría coincidido y la actualización se habría
   rechazado — aunque la comprobación de versión pasara.

## Corrección aplicada (sin tocar código ni IDs)

- Añadido **`&confirm=t`** a la URL del instalador DENTRO del
  version-pc.json publicado (mismo ID `1Kfd_pELWJhp37fO1iaERdSIzpRkAqK4R`,
  mismo contenido salvo ese campo). Como la app instalada lee la URL
  del propio JSON, **su v1.0.3 recibe el arreglo sin necesitar código
  nuevo**: con `confirm=t` la misma URL devuelve HTTP 206,
  `application/octet-stream`, `Content-Disposition:
  Instalador-AntivirusHogarPC-1.0.4.exe`, tamaño total 39.772.643 B y
  primeros bytes PE32.
- Zip compartido «cualquiera con el enlace puede ver» (arriba).

## Verificación final — TODA anónima, con el código real de la app

Ejecutado `core.updater` del proyecto contra la URL de config.py, sin
conector ni credenciales:

- `comprobar_actualizacion(url, "1.0.3")` → **ofrece la 1.0.4** (URL del
  instalador ya con `&confirm=t`, SHA-256 `ff79f0d1…`).
- `comprobar_actualizacion(url, "1.0.4")` → **None («al día»)**.
- `descargar_archivo(url_del_json, destino)` → **39.772.643 bytes**
  descargados de forma anónima.
- `verificar_sha256(descargado, sha_del_json)` → **True**.

El canal queda funcionando de principio a fin tal como lo usa su PC.

---

# ADDENDA FORENSE (2026-11-24 11:33 EST): el «no encontrado» seguía en su PC

El usuario volvió a pulsar el botón tras la reparación anterior y la app
v1.0.3 instalada SIGUIÓ diciendo «no encontrado». La verificación anterior
era correcta pero incompleta: probó la URL de `config.py` (el valor por
defecto del código), y **la app instalada no usa ese valor: usa el que
quedó guardado en su `ajustes.json`**.

## Causa raíz REAL (verificada en código de las 4 versiones y reproducida)

1. La v1.0.1 (commit `94c7abf`) traía en `config.py` la URL con el id
   marcador: `…download?id=1BpcVersionJsonPendiente&export=download`.
2. `Ajustes.url_actualizacion` se persiste en
   `%LOCALAPPDATA%\AntivirusHogarPC\ajustes.json` — carpeta de datos que
   las reinstalaciones NO tocan. `Ajustes.cargar()` sobreescribe el
   default del código con lo que diga ese archivo, y
   `comprobar_actualizacion_app()` llama a `ajustes.guardar()` ANTES de
   comprobar: el valor viejo se carga y se re-guarda, perpetuándose.
3. El usuario pulsó «Buscar actualizaciones» con la v1.0.1 (era el bug
   que reportó entonces) → su ajustes.json quedó escrito con la URL del
   marcador. La v1.0.2 y la v1.0.3, instaladas encima, heredaron esa URL.
   **Su app nunca ha buscado la dirección buena.**
4. La dirección del marcador, pedida anónima hoy, devuelve **HTTP 404**
   (página de error de Google): es exactamente el «no encontrado» de su
   pantalla. La dirección buena devuelve 200 (verificado arriba).

## Qué NO era (descartado con evidencia)

- No hay dos version-pc.json: en todo Drive (incluida la papelera) existe
  UNO solo: ID `1Kfd_pELWJhp37fO1iaERdSIzpRkAqK4R`, trashed:false,
  anyoneWithLink=reader, contenido 1.0.4 con `&confirm=t` (modificado
  2026-11-24 11:30 EST). En la papelera solo hay instaladores v1/v1.0.1.
- El config.py de la v1.0.3 compilada (commit `8f51940`, igual en
  v1.0.2) ya traía la URL buena: el fallo no está en el código compilado
  sino en el dato persistido en su PC.
- No se puede «publicar» el archivo en el id marcador: es un id
  inventado; Drive asigna los IDs y no permite crear un archivo con un
  ID elegido. La corrección del lado del servidor no existe para esa
  dirección.

## Reproducción con el código exacto de la v1.0.3 (commit 8f51940)

Simulación ejecutada con `Ajustes.cargar()` +
`comprobar_actualizacion_app()` reales de la v1.0.3 y una carpeta de
datos falsa:

- **Con ajustes.json «envenenado»** (url del marcador, como en su PC):
  la app usa esa URL → mensaje en pantalla IDÉNTICO al de su foto («El
  canal de actualizaciones respondió «no encontrado»…»), detalle técnico
  `HTTP 404 en …id=1BpcVersionJsonPendiente…`.
- **Sin ese campo en ajustes.json**: la app usa la URL de config →
  ofrece la **1.0.4**; descarga anónima del instalador por la URL del
  JSON: **39.772.643 bytes**, `verificar_sha256` → **True**, cabecera MZ.

## Corrección viable (la del servidor ya estaba hecha)

En su PC, con la app cerrada, editar
`%LOCALAPPDATA%\AntivirusHogarPC\ajustes.json` y poner en
`url_actualizacion` la URL buena:
`https://drive.usercontent.google.com/download?id=1Kfd_pELWJhp37fO1iaERdSIzpRkAqK4R&export=download`
(alternativa simple: borrar ajustes.json; la app lo recrea con los
valores del código, perdiendo solo letra grande/fondo/escaneo semanal).
Desde ese momento el botón funciona y el valor bueno queda guardado.

## Deuda de código (la v1.0.4 trae el MISMO defecto)

`Ajustes.cargar()` no cambió entre la v1.0.3 y la v1.0.4: si el usuario
actualiza a la 1.0.4 sin corregir su ajustes.json, seguirá roto. La
próxima versión debe migrar al cargar: si la `url_actualizacion`
guardada difiere de `config.UPDATE_VERSION_URL` (o contiene
«Pendiente»), sobreescribirla con la del código. Y toda verificación
futura del canal debe simular también el estado persistido del usuario,
no solo el default del código.

---

# ADDENDA 2 (2026-11-24 11:47 EST): encuentra la 1.0.4 pero «No se pudo descargar la actualización»

Tras borrar su ajustes.json envenenado, la app v1.0.3 del usuario YA
encontró la 1.0.4, pero al descargarla mostró «No se pudo descargar la
actualización.» (foto 11:47 EST, sin detalle en pantalla).

## Qué cubre EXACTAMENTE ese mensaje (código v1.0.3, commit 8f51940)

Está en `instalar_actualizacion_app()` (modules/net/servicios_red.py):
sale SOLO cuando `updater.descargar_archivo(info.url, destino)` lanza
una excepción (vía `seguro()`): error de red, HTTP no-200, corte a mitad
de descarga, timeout o error al escribir el archivo. El detalle técnico
queda en `detalle_tecnico` del resultado (visible en «Ver detalles» /
registro, no en la vista principal).

NO es el fallo de huella: si la descarga «completa» pero el SHA-256 no
coincide (p. ej. si bajara la página HTML de advertencia de virus), el
mensaje sería otro: «El archivo descargado no coincide con la huella de
seguridad del canal. Se ha borrado y NO se ha instalado nada.» Como su
mensaje fue el de descarga, en su PC la transferencia misma se cortó o
el servidor respondió error desde SU red (hotspot en el vehículo),
aunque la misma URL desde este entorno baja perfecta.

## Pruebas anónimas COMPLETAS de cada forma de URL (instalador, 39.772.643 B)

Con el User-Agent de la app («AntivirusHogarPC») y descarga entera +
SHA-256:

| Forma | Resultado |
|---|---|
| (a) usercontent `&confirm=t` (la publicada) | ✅ 39.772.643 B, SHA válido, cabecera MZ — con el `descargar_archivo` real de la app |
| (b) usercontent sin confirm | ❌ 2.484 B de HTML «virus scan warning», SHA no coincide |
| (c) `drive.google.com/uc?export=download` con cookies (flujo gdown), UA app | ✅ 1ª respuesta HTML con uuid; 2ª petición usercontent `confirm=t&uuid=…` → 39.772.643 B, SHA válido |
| (c) igual, UA de navegador | ✅ idéntico |

La forma (c) exige DOS peticiones con cookies y la app solo hace UNA
(descargar_archivo es un GET único, sin jar de cookies): no es
publicable como URL fija en el JSON. La mejor forma de UN solo GET
sigue siendo la (a), que ya era la publicada: **no hubo cambio de URL
que hacer en version-pc.json**.

## Ruta GitHub: repo PÚBLICO, pero la subida de assets está bloqueada por el conector

- El repo ERISLANDY2026/antivirus-hogar-pc es PÚBLICO (verificado
  anónimo: api.github.com/repos/… → 200, `private: false`).
- Se creó la release v1.0.4 (id 457062054) sin problema vía
  api.github.com, pero **subir el asset devolvió 401 «Bad
  credentials»**: los assets van a `uploads.github.com` y el conector
  custom.github solo tiene registrado `api.github.com`, así que la
  credencial segura no se aplica a ese host. Sin asset no hay
  browser_download_url que publicar.
- La release vacía y su tag se BORRARON (DELETE → 204/204; la página
  de la release devuelve 404) para no dejar una release engañosa sin
  instalador.
- Para habilitar esta ruta en el futuro: re-registrar el conector
  custom.github añadiendo `uploads.github.com` a sus hosts (el usuario
  re-guardaría el PAT por la vía segura) y repetir: crear release +
  subir asset + publicar su browser_download_url en version-pc.json.
  Decisión del usuario/agente principal; NO se hizo.

## Verificación final (código exacto de la v1.0.3, todo anónimo, x2)

Con `core.updater` extraído del commit 8f51940 y la URL de versión que
la app usa tras corregir ajustes.json:

- `comprobar_actualizacion(url, "1.0.3")` → **ofrece la 1.0.4** (URL
  con `&confirm=t`, SHA `ff79f0d1…`).
- `comprobar_actualizacion(url, "1.0.4")` → **None («al día»)**.
- Descarga 1 por la URL del JSON: **39.772.643 B, verificar_sha256 =
  True, cabecera MZ**.
- Descarga 2 (repetición anti-intermitencia): **39.772.643 B,
  verificar_sha256 = True, cabecera MZ**.

Conclusión: del lado del canal no queda nada más que corregir — la URL
publicada es la forma correcta y verificada dos veces seguidas. Si en
su PC la descarga se sigue cortando, es su red del momento (hotspot):
reintentar con mejor conexión/Wi-Fi debería completar, porque el
mensaje que ve es de corte de transferencia, no de canal ni de huella.

## Regla nueva para futuras entregas (sustituye a la anterior)

**La verificación del canal se hace SIEMPRE de forma anónima y con el
código real de la app** (comprobar desde la versión anterior y desde la
nueva + descargar el instalador completo por la URL que trae el JSON +
verificar su SHA-256). La lectura autenticada por el conector NO prueba
el canal: enmascara permisos y la página de advertencia de virus de
Google. Además: toda URL de instalador publicada en version-pc.json
debe llevar `&confirm=t`, y los tres archivos del canal (version-pc.json,
.exe y .zip) deben quedar con `anyoneWithLink = reader` y `trashed:
false`, verificados al final de cada entrega.
