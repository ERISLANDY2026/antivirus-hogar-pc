# INFORME V1.0.9 — La solución del Error 31 de SoftEther + botones por fila + calificación fuera del radar

**Fecha:** 25/11/2026 · **Orden del usuario:** construir la solución probada del
Error 31; en espera parcial (07:05 EST) llegaron dos cambios más para la misma
versión —botones por fila en VPN Gate (cambio 1) y la calificación de salud
fuera del centro del radar (cambio 2)— y a las 07:08 EST el usuario ordenó
«Lánzala» con todo el alcance. **Entregada y publicada en el canal.**

## 1. El problema (evidencia del usuario)

En su Toughbook, el `softether-nic-instalacion.txt` de la 1.0.8 probó que,
incluso durante la instalación y ya elevado, `NicCreate VPN` devolvió
«Error occurred. (Error code: 31) — Installation of the Virtual Network
Adapter device driver failed» y NicList quedó vacío. Causa raíz: nuestro
instalador copiaba los 4 archivos del cliente y registraba el servicio, pero
**nunca instalaba el paquete del controlador de la tarjeta virtual (Neo6
x64) en el almacén de controladores de Windows (DriverStore)**. NicCreate lo
ejecuta el servicio SEVPNCLIENT (SYSTEM, sesión 0), que no puede mostrar el
aviso de confianza del editor para un controlador aún no almacenado: la
instalación del driver fallaba siempre. El instalador oficial de SoftEther
sí deja ese controlador almacenado al instalar.

## 2. Forense del controlador (punto 1 del encargo) — dónde estaba

En la corrida CI **45613046882** se enumeraron TODOS los recursos del
instalador oficial 4.44-9807 (evidencia: `evidencia-v109/forense-ci-45613046882.txt`).
Su carpeta `.rsrc\0\DATAFILE` trae exactamente 12 recursos: INSTALL_SRC.DAT
(25 B), RAW_HAMCORE.SE2 (23.209.854 B), VPNCLIENT_X64.EXE, VPNCLIENT.EXE,
VPNCMD_X64.EXE, VPNCMD.EXE, VPNCMGR_X64.EXE, VPNCMGR.EXE, VPNINSTALL.EXE,
VPNSETUP_X64.EXE, VPNSETUP.EXE y VPNWEB.CAB (206.497 B). **No existe ningún
recurso separado del controlador** (.inf/.sys/.cat): el paquete vive SOLO
dentro de `hamcore.se2`, en `DriverPackages\Neo6_Win10\x64\` (así está en el
árbol oficial de fuentes, `src/bin/hamcore`).

El formato `.se2` es propietario («HamCore», cabecera `48-61-6D-43-6F-72-65-00`
= «HamCore\0»): **7-Zip no puede abrirlo** («Cannot open the file as
archive», misma corrida). La vía real de incorporación, aplicada y
documentada en el workflow y en `packaging/softether/LEEME.md`: los tres
archivos del paquete se toman del **árbol oficial de fuentes de la misma
etiqueta exacta, `SoftEtherVPN_Stable v4.44-9807-rtm`** — el mismo árbol del
que se construye el hamcore de esa versión — y la compilación **exige** que
sus huellas SHA-256 coincidan con las fijadas; si no, falla. La extracción
desde el hamcore queda como primer intento en el workflow por si una
herramienta futura lo abre, con la misma verificación de huellas.

**El paquete incorporado** (Windows 10 x64, adaptador «VPN»):

| Archivo | Tamaño | SHA-256 |
|---|---|---|
| Neo6_x64_VPN.inf | 3.499 B | `8f049a53bab3f1a16f118c91c15569cceef4b2955905c8f7c70f7952f9c175b8` |
| Neo6_x64_VPN.sys | 37.824 B | `54e74a7906af47c2b07f0ea171973d6abb123549a1c66cf0cc6f24ec5e55a237` |
| Neo6_x64_VPN.cat | 19.633 B | `162c56608532ef7c699520194fd2231550bab6d0a32c1bbb6866f22da8c45aed` |

El .inf (leído completo en la forense): Class=Net, Provider «SoftEther
Corporation», DriverVer 02/04/2018 4.25.0.9658, CatalogFile
`Neo6_x64_VPN.cat` (catálogo firmado, PKCS#7), hardware ID **`NeoAdapter_VPN`**,
servicio `Neo_VPN`, DeviceDesc «VPN Client Adapter - VPN». Es exactamente el
paquete del primer adaptador «VPN», el que crea nuestra app.

En CI los tres archivos quedaron en `packaging\softether\client\driver\` y
anotados en `SOFTETHER-CLIENT.txt` con su origen; el registro de ISCC de la
corrida buena muestra el instalador final comprimiendo
`softether\client\driver\Neo6_x64_VPN.cat/.inf/.sys`: **el controlador va
físicamente dentro del instalador 1.0.9** (evidencia:
`evidencia-v109/compilacion-ci-45614633544.txt`).

## 3. La solución construida

**Instalador (`packaging/instalador.iss`)** — nuevo procedimiento
`PrepararTarjetaVirtualSoftEther`, tras registrar el servicio:

1. `InstalarControladorTarjetaVirtual`: si está
   `{app}\softether\driver\Neo6_x64_VPN.inf`, ejecuta
   `pnputil /add-driver "<inf>" /install` **VISIBLE (SW_SHOW, nunca
   SW_HIDE en este paso)**, captura su salida exacta y **verifica con
   `pnputil /enum-drivers`** que el paquete quedó almacenado (busca
   `Neo6_x64_VPN.inf` en la enumeración).
2. `CrearTarjetaVirtualSoftEther` (el de la 1.0.8): asegura el servicio,
   NicCreate y verificación con NicList.
3. Todo va a un registro **ACUMULADO** que se guarda de una vez en
   `{app}\softether-nic-instalacion.txt` (antes cada sección sobrescribía:
   ahora el archivo trae la sección de pnputil Y la de NicCreate).
4. El manifiesto `componentes.json` incluye los 3 archivos del controlador
   cuando están, para la comprobación de integridad al arrancar.

**App (`winapi/vpn_win.py`, `winapi/powershell.py`)** — respaldo al conectar:
si la tarjeta falta, `crear_nic_elevada` repite la receta completa en un
PowerShell elevado **INTERACTIVO** (nuevo `ejecutar_elevado_interactivo`,
**SIN `-NonInteractive`**, en la sesión del usuario, para que el aviso de
Windows pueda aparecer): primero `pnputil /add-driver` con el .inf que viaja
con la app y después NicCreate. La salida REAL de ambos se guarda en
`%LOCALAPPDATA%\AntivirusHogarPC\vpn\salida-crear-nic.txt` y su línea de
error va en el detalle que ve el usuario: nada se descarta en silencio.

## 4. Cambio 1 — botones por fila en VPN Gate

En `modules/net/page.py`, la celda «Acción» de cada fila es ahora un
contenedor: sin conexión, solo «Conectar»; con el túnel arriba en ESE
servidor, su botón se pone **VERDE y dice «Conectado»** (deshabilitado, es el
estado) y **a su derecha, en la misma fila, aparece el botón ROJO
«Desconectar»** (nuevo `theme.ROJO_BOTON` #D93025, pareja del VERDE_BOTON),
que baja el túnel por la vía general existente (que limpia el estado y
repinta). La columna se ensancha a un mínimo de 250 px cuando hay fila
conectada. Verificado en captura offscreen:
`evidencia-v109/vpngate-tabla-fila-conectada.png` (fila 1: Conectado verde +
Desconectar rojo; fila 2: Conectar; el globo sigue en su esquina).

## 5. Cambio 2 — la calificación fuera del radar

El «71» con «Salud del equipo» se dibujaba en el CENTRO de `AnilloSalud`,
encima del radar. Ahora el anillo **ya no dibuja texto** (solo arco, color y
punto orbital) y expone `texto_puntuacion()` + señal `valor_cambiado`; la
página de Inicio enseña la cifra en una etiqueta anclada al **borde inferior
izquierdo de la banda del radar** (rejilla de una celda: el anillo sigue
centrado y alineado con el radar; la etiqueta queda fuera del círculo). La
cuenta animada se sigue viendo, en la esquina, con su color semántico
(71 = ámbar, como manda la banda ≥50 de la app). Sin fijar enseña «…» y sin
datos «— / Sin datos de Windows». El radar y su animación **no cambian**.
Verificado en captura offscreen: `evidencia-v109/inicio-radar-esquina.png`
(el 71 abajo a la izquierda, el centro del radar libre).

## 6. Construcción y pruebas

- **Suite local: 259/259** (252 de la 1.0.8 + 7 nuevos de `tests/test_v109.py`:
  pnputil visible y antes de NicCreate, huellas del workflow, interactivo sin
  -NonInteractive en el proceso elevado, crear_nic_elevada con la receta en
  orden y con la salida real en el detalle, fila conectada verde+roja, anillo
  sin cifra central). Mantenimiento mínimo de históricos, como en la 1.0.8:
  pines de versión 1.0.8→1.0.9 en test_v107 y la celda de botones (ahora
  contenedor) en test_v107/test_bugs_v102.
- **Corrida CI 45613046882 — FAILURE en ISCC** (la suite y el paso de
  SoftEther, con la forense completa, pasaron): «Error on line 283: Unknown
  preprocessor directive». Causa: una línea de continuación de mi código
  Pascal empezaba por `#13#10`, e ISPP la toma por directiva. Corregido
  reordenando la expresión y con guarda nueva en test_v109 (ninguna línea
  del .iss puede empezar por `#` salvo directivas en columna 0).
- **Corrida CI 45614633544 — SUCCESS**: suite en CI, PyInstaller, icono,
  SoftEther con el controlador verificado, ISCC y artefacto.
- **Instalador:** `Instalador-AntivirusHogarPC-1.0.9.exe` — **63.729.305 B** ·
  MD5 `e46c9b4e5d25d93d26d82df5f6e0277b` · SHA-256
  `672934b4ea3b9acda4df70c6e0ab670fdc9516c7f3d49514aa75b4ba701d716c`.
- **Zip del canal:** 63.220.736 B · MD5 `94a674359c40a971155ff80bb01c12ef`.

## 7. Publicación en el canal (en sitio, mismos IDs)

- exe `1zmtcu-NL-PvCbGisbAXbFwVwyBlI5_ql` → «Instalador-AntivirusHogarPC-1.0.9.exe»
- zip `1ZHiCO9lInsLv6GJBCdCj6GtTMjGf6hTG` → «AntivirusHogarPC-Instalador-v1.0.9.zip»
- `version-pc.json` `1Kfd_pELWJhp37fO1iaERdSIzpRkAqK4R` → versión 1.0.9, URL
  con `&confirm=t`, SHA-256 del instalador y las notas de la versión.
- Los 3: **anyoneWithLink=reader y trashed:false** (verificado por API).
- Copia visible NUEVA: «INSTALADOR Antivirus Hogar PC v1.0.9.zip», ID
  `1_xfSG7tAFiCjANy2BK6Q-s09oS4CzraM`, en la carpeta
  `1I7V-Zabmiov8ttDHMkuJL8dlP1GeukHM`. La copia visible de la 1.0.8 fue a la
  papelera (patrón de limpieza de versiones viejas).

**Verificación anónima del canal (con el código real de la app,
`core.updater`, sin credenciales) — SUPERADA:**
1. Desde la **1.0.8** ofrece la **1.0.9** (SHA `672934b4…`).
2. Desde la **1.0.9**: «al día», sin oferta.
3. Descarga completa por la URL del JSON: 63.729.305 B, **SHA-256 válido**.
4. Corte a 15.000.001 B y reanudación con el descargador de la app:
   completa, **SHA-256 válido**.

## 8. Qué queda por probar en la Toughbook (solo puede hacerlo él)

El paso de pnputil **no tiene salida de CI que enseñar**: en el runner no se
instala nada; su salida real existirá solo en su PC, grabada en
`softether-nic-instalacion.txt`. Al instalar la 1.0.9 debe comprobarse:

1. Durante la instalación se ve trabajar la ventana de pnputil (visible a
   propósito); **si Windows enseña su aviso de instalación del controlador,
   hay que aceptarlo** (puede salir una sola vez).
2. `softether-nic-instalacion.txt` debe traer: la sección
   «pnputil /add-driver» con su salida, la línea «el controlador quedo
   ALMACENADO en el DriverStore» de la verificación /enum-drivers, y
   «NicList trae la tarjeta (VPN)».
3. Primera conexión en VPN Gate: el túnel sube y la fila queda con
   «Conectado» verde + «Desconectar» rojo.
4. En Inicio, la calificación se ve en la esquina inferior izquierda del
   radar.

Si el paso 2 no trae la tarjeta, el propio archivo trae la salida exacta de
pnputil y de vpncmd para reportarla: ya no hay ningún paso en silencio.

## 9. Resumen para memoria (MEMORY.md no es editable desde esta sesión)

**v1.0.9 ENTREGADA (2026-11-25):** solución del Error 31 construida como se
diseñó: el paquete oficial del controlador Neo6_x64_VPN (Windows 10 x64,
hardware NeoAdapter_VPN) viaja en `{app}\softether\driver` —incorporado en
CI desde el árbol oficial de la etiqueta v4.44-9807-rtm con huellas SHA-256
fijadas y verificadas, porque el controlador SOLO existe dentro de
hamcore.se2 y su formato propietario no lo abre 7-Zip (forense CI
45613046882: la enumeración completa de recursos DATAFILE no trae ningún
recurso de controlador separado)—; el instalador lo almacena en el
DriverStore con `pnputil /add-driver /install` VISIBLE antes de NicCreate,
lo verifica con /enum-drivers y deja el registro acumulado en
softether-nic-instalacion.txt; el respaldo al conectar va INTERACTIVO sin
-NonInteractive, repite pnputil + NicCreate y guarda la salida real. Cambio
1: fila conectada con «Conectado» verde + «Desconectar» rojo en la misma
fila. Cambio 2: la calificación de salud sale del centro del radar a su
esquina inferior izquierda (anillo sin texto; etiqueta sincronizada por
señal). Suite 259/259; CI 45614633544 SUCCESS (la anterior, 45613046882,
falló solo en ISCC por una línea que empezaba por «#»: corregido con
guarda en test). Instalador 63.729.305 B, SHA-256 `672934b4…d716c`. Canal
en sitio a 1.0.9 y verificado anónimo (desde 1.0.8 la ofrece, desde 1.0.9
«al día», descarga completa y reanudada con SHA válido); copia visible
nueva `1_xfSG7tAFiCjANy2BK6Q-s09oS4CzraM` y la de la 1.0.8 a la papelera.
**Pendiente: su prueba en la Toughbook** (aviso de Windows al instalar si
sale, softether-nic-instalacion.txt con pnputil OK + NicList con la
tarjeta, y primera conexión VPN Gate).
