# INFORME — Antivirus Hogar PC v1.0.5

**Fecha:** 2026-11-24 · **Estado: COMPLETA Y ENTREGADA por el canal de
actualizaciones** (el botón interno de la app la encuentra y la descarga;
verificado de punta a punta, ver §16).
Autorización: «dale» del usuario (2026-11-24 10:21 EST) + sus órdenes de
voz de las 12:06–12:32 EST del mismo día.

**Instalador:** `Instalador-AntivirusHogarPC-1.0.5.exe` — 40.255.590 B ·
MD5 `bac19937623de9e16254b3658d2268a5` · SHA-256
`47928e8c94ad32f0ca8fc3d32a722fe1eb20dd5926ebe4da0b1d0aac3c9aff65`.
**Suite:** 168/168 (120 anteriores + 48 nuevos de la v1.0.5).
**CI:** GitHub Actions run 45452074036 **SUCCESS** (commit `05333e93`),
con la verificación de los 4 registros de módulos dentro del .exe y la
verificación NUEVA del icono espartano dentro del .exe, ambas en verde.

---

## 1. Iconos del panel izquierdo 3D, en colores modernos y animados

- Nuevo `ui/iconos_nav.py`: un icono PROPIO por pestaña, dibujado con
  QPainter (supersampling ×2) a **36 px lógicos**: Inicio, Escanear,
  Protección, Drivers, Limpieza, Discos, Actualizaciones, Red y VPN,
  Informes, Ajustes, Versión de la app y Programador de tareas.
- Paleta vibrante por icono (gradientes cian→azul, fucsia, verde neón,
  naranja, rosa→rojo, violeta, turquesa, dorado, índigo), con gloss 3D
  marcado (brillo superior) y sombra suave. Nada de glyphs planos.
- Animación sutil: pulso de brillo/escala al pasar el ratón y en la
  pestaña activa; el de Actualizaciones GIRA mientras es la activa.
  Respeta el interruptor de fondo animado de Ajustes (apagado =
  iconos estáticos, sin temporizador). Evidencia: `evidencia-v105/`.

## 2. Autocorrección del canal (deuda de la v1.0.4)

- `Ajustes.cargar()`: si la `url_actualizacion` guardada difiere de
  `config.UPDATE_VERSION_URL` o contiene «Pendiente», se sobreescribe
  con la del código y se guarda. Nadie más puede quedar atrapado con
  la URL marcador de la v1.0.1. Tests: 4 (limpio, envenenado, distinta,
  persistencia).

## 3. Descarga resistente

- `descargar_archivo`: hasta 3 intentos, reanudación con Range cuando
  hay parcial (206 añade, 200 reescribe, 416 descarta el parcial),
  errores 4xx (salvo 429) sin reintento inútil, y comprobación de
  longitud: si el flujo termina antes de lo anunciado, ya no pasa por
  descarga completa. El SHA-256 final se mantiene; el detalle técnico
  va al registro. Test con servidor local que corta la primera
  transferencia: completa por reanudación.

## 4. Discos — Optimizar volúmenes oculto con barra RGB precisa

- Optimize-Volume sigue siendo el motor (Shell), pero se lanza
  ELEVADO Y OCULTO (`Start-Process -WindowStyle Hidden`; el UAC es del
  sistema y puede aparecer) y vuelca su salida detallada a archivos
  que la app vigila.
- La página de Discos muestra la **BarraProgreso RGB** de la app: el
  porcentaje sale de la PROPIA salida del comando (pasadas con %); en
  fases sin % fiable, barra animada con el texto de la fase. Al
  terminar, resultado claro en la app; la causa técnica, al registro.
- Fallo cazado por la suite en CI (Windows): el archivo de resultado
  podía leerse vacío un instante tras crearse; ahora se espera y se
  relee con margen antes de juzgar.

## 5. Velocidad de internet real (Cloudflare), en vivo

- Fuente elegida: **speed.cloudflare.com** (`__down`/`__up`), público,
  sin clave, mantenido por Cloudflare (LibreSpeed depende de un
  servidor concreto que puede caer). Medición en hilo de fondo.
- EN VIVO: primero la descarga y después la subida, con los valores
  actualizándose DURANTE la medición (señal desde el hilo), números en
  colores RGB (ping cian, bajada verde, subida violeta) a 16 px.
  Sin conexión: mensaje claro en español y causa en el registro.

## 6. Wi-Fi interactivo

- La sección muestra el **SSID actual** en un botón-resumen; al
  tocarlo se despliegan los detalles: SSID, señal, banda, canal,
  frecuencia (calculada), velocidad de enlace, seguridad, IP local,
  puerta de enlace y DNS (netsh + Get-NetIPConfiguration, ocultos).
- Por cable o sin Wi-Fi se dice claro. «Actualizar datos de Wi-Fi»
  refresca de verdad y deja sello de hora.

## 7. VPN Gate corregido «ya de una» — causa raíz

- **Diagnóstico con evidencia:** la semilla SÍ iba en el ejecutable
  (verificada en el bundle), pero `descargar_lista_con_respaldo` NO
  tenía plazo total: 3 URLs × reintentos × timeout de socket podían
  estirarse sin fin en una red lenta, y la semilla solo entraba
  DESPUÉS de rendirse la cadena → el hilo nunca volvía y el
  desplegable quedaba vacío para siempre.
- **Corrección:** plazo total de 75 s en la cadena + **la semilla
  puebla el desplegable AL INSTANTE** al abrir la sección o pulsar el
  botón; la lista en vivo la reemplaza al llegar. Barrita de progreso
  temporal durante la actualización (desaparece al terminar) y aviso
  final con nº de servidores/países y fuente; si la red falla, aviso
  ámbar de respaldo con botón «Reintentar descarga». El desplegable
  NUNCA queda vacío. Fuentes: solo las 3 rutas oficiales del API de
  VPN Gate (sin espejos de terceros: la lista trae perfiles .ovpn y
  un espejo podría envenenarlos).

## 8. Radar de Inicio militar

- Fondo **verde eléctrico visión nocturna** con escáner barriendo;
  las bolitas son ahora **iconitos de amenazas** dibujados con
  QPainter (virus, bichito tipo alien, archivo roto) que derivan por
  el fondo y **se iluminan cuando el haz los toca**. La zona del
  escáner crece (280 px). Respeta el interruptor de animaciones.

## 9. Tema cristal general

- Adiós al azul oscuro plano: fondo con gradiente diagonal, paneles
  semitransparentes con brillo y bordes luminosos (glassmorphism) en
  TODAS las secciones, menú izquierdo cristalino con el movimiento de
  los iconos 3D. Contraste de textos mantenido. Evidencia:
  `evidencia-v105/` (Inicio, Protección, Red y VPN, Versión,
  Programador).

## 10. Icono de la app: el espartano aprobado

- La imagen aprobada por el usuario (espartano cyborg dorado en el
  escudo, fondo blanco) convertida a `packaging/icono.ico`
  multirresolución (16–256) y aplicada al ejecutable, al instalador
  (`SetupIconFile`) y a los accesos directos (icono del .exe).
- **Verificado dentro del .exe construido:** paso nuevo de CI
  (`scripts/verificar_icono.py`, pefile) que exige el recurso
  RT_ICON con entrada de 256 px y >50 KB de datos de icono. En verde.

## 11. Drivers: cadena de confirmación rápida + causa breve

- **Causa breve en la página** («Windows Update no respondió en el
  tiempo límite.»); el comando crudo y el detalle técnico SOLO en el
  registro de actividad. Nunca más el comando entero en pantalla.
- **Cadena nueva, en orden:** (a) **Catálogo de Microsoft** por
  Hardware ID — oficial y por dispositivo, mucho más rápido que el
  escaneo WU completo; (b) Windows Update COM con límite de 240 s
  (antes 900) + 1 reintento en segundo plano; (c) almacén local de
  drivers (pnputil) como fuente oficial local. Un driver se confirma
  «Al día»/«Hay uno más nuevo» en cuanto UNA fuente oficial lo
  confirme con datos reales; «Sin confirmar» solo si TODAS fallan.
- La instalación NO cambia: solo ruta oficial, punto de restauración
  y drivers firmados.
- Tests: el Catálogo confirma sin pasar por WU; WU agota el tiempo y
  la cadena sigue y confirma por Catálogo; todas caen → «Sin
  confirmar» con causa breve y SIN el comando crudo en la UI.

## 12. Entrada «Versión de la app»

- Bajo Informes, con su icono 3D dorado animado. Su pantalla muestra
  la versión actual, sus novedades, qué tiene y qué hace la app y el
  historial reciente (1.0.4, 1.0.3, 1.0.2), desde la estructura de
  datos `core/notas_version.py` (las futuras versiones solo añaden su
  entrada).

## 13. Arranque con Windows + rutina automática

- La app se registra en la clave Run de HKCU (estándar, reversible) y
  arranca minimizada con `--inicio-automatico`; entonces corre EN
  SEGUNDO PLANO la rutina: escaneo rápido (avisa solo si hay
  hallazgos; ante amenazas NO actúa sola), revisión de drivers por la
  cadena nueva, limpieza segura (temporales, cachés, papelera) y
  revisión de inicio. Resultados en el registro y resumen visible en
  Inicio («Rutina automática al arrancar»).
- Interruptores en Ajustes (arranque y rutina), **activados por
  defecto**; el de arranque aplica el cambio al momento.

## 14. «Programador de tareas» (nombre corregido por el usuario)

- Entrada con icono de calendario 3D tras «Versión de la app»;
  Ajustes queda al final. Seis programaciones reales: escaneo rápido,
  escaneo completo, revisión de drivers, limpieza segura,
  actualización de firmas y búsqueda de actualización de la app —
  cada una con frecuencia (diaria/semanal), día, hora, interruptor,
  próxima ejecución y última ejecución con su resultado.
- Mecanismo: **Programador de tareas de Windows** (schtasks), así las
  tareas corren AUNQUE LA APP ESTÉ CERRADA — la pantalla lo dice
  claro. La tarea de actualización descarga el instalador nuevo y lo
  deja listo; instalarlo lo confirma el usuario en la app.

## 15. Fallo cazado antes de compilar (humo del bundle local)

- El ejecutable empaquetado no arrancaba: `main.py` importaba
  `QTimer` desde QtWidgets (va en QtCore). Lo cazó la prueba de humo
  sobre el bundle local (la suite no llama a `main()`); corregido y
  con test de regresión que arranca `main()` en subproceso.

## 16. PUERTA FINAL — el botón encuentra y descarga (verificado)

Verificación ANÓNIMA (sin credenciales ni cookies) con el código real
de la app nueva, contra el canal publicado:

| Prueba | Resultado |
|---|---|
| Desde 1.0.3 | ofrece la **1.0.5** ✓ |
| Desde 1.0.4 | ofrece la **1.0.5** ✓ |
| Desde 1.0.5 | «al día» (sin oferta) ✓ |
| Ajustes envenenado (ID marcador) | la migración deja la URL buena y desde 1.0.4 ofrece la 1.0.5 ✓ |
| Descarga anónima nº 1 por la URL del JSON | **40.255.590 B**, SHA-256 `47928e8c…f65` válido ✓ |
| Descarga anónima nº 2 | **40.255.590 B**, SHA-256 válido ✓ |
| Corte forzado a 15.000.000 B | la descarga resistente **reanuda (Range) y completa**: 40.255.590 B, SHA válido ✓ |

**Canal Drive** (carpeta «Antivirus Hogar PC»
`1I7V-Zabmiov8ttDHMkuJL8dlP1GeukHM`), actualizado EN SITIO:
zip `1ZHiCO9lInsLv6GJBCdCj6GtTMjGf6hTG` → «AntivirusHogarPC-Instalador-v1.0.5.zip»
(39.745.340 B, MD5 `cb905bba28f7c1946bfca4e608beaa03`);
.exe `1zmtcu-NL-PvCbGisbAXbFwVwyBlI5_ql` → «Instalador-AntivirusHogarPC-1.0.5.exe»
(MD5 `bac19937623de9e16254b3658d2268a5`);
version-pc.json `1Kfd_pELWJhp37fO1iaERdSIzpRkAqK4R` → 1.0.5 con el SHA
nuevo y la URL del instalador **con `&confirm=t`**.
Los 3 con anyoneWithLink=reader y trashed:false verificados listando
la carpeta. Copia visible nueva: «INSTALADOR Antivirus Hogar PC
v1.0.5.zip» (ID `129vRbY1rW36E6nq5eGaLUlz_Oy9PvQxq`, también pública).

**Pendiente (del lado del usuario):** probarla en su Windows real; su
app instalada le ofrecerá la 1.0.5 por el botón de actualizaciones.
