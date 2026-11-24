# VERIFICACIÓN — Antivirus Hogar PC v1

Fecha de la verificación de integración: **2026-11-24**.
Puerta del usuario: verificar el código y, cuando exista, el ejecutable de
Windows 10; solo si todo está correcto y va a funcionar, avisarle para que
él decida si se pone en uso.

## Veredicto

- **Código: VERIFICADO** en esta máquina (Linux) en todo lo que se puede
  verificar sin Windows: sintaxis completa, suite automática de la lógica
  pura, descubrimiento de módulos sin interfaz y degradación honesta fuera
  de Windows.
- **Ejecutable (.exe): PENDIENTE** de compilación en Windows. PyInstaller no
  compila cruzado desde Linux; el instalador se produce con
  `Construir-en-Windows.bat` en la PC o con el workflow de GitHub Actions
  (`.github/workflows/build-windows.yml`, listo; se dispara a mano o con un
  tag `v*`). Nada de este paquete debe presentarse como «.exe verificado»
  hasta que esa compilación exista y se pruebe en un Windows real.

## 1. py_compile de todo el proyecto

- `python3 -m py_compile` sobre **todos** los `.py` del proyecto (paquete
  `antivirus_hogar_pc`, `tests/` y `AntivirusHogarPC.py`): **OK, sin
  errores**.
- `python3 -m compileall` sobre el paquete, los tests y el lanzador:
  **OK**.
- No se encontró ningún error de integración (imports o rutas rotas) que
  hubiera que corregir en esta fase.

## 2. Suite completa de pruebas (`tests/`)

Entorno: venv desechable con `pytest 9.2.0` (Python 3.12.3).
Comando: `python -m pytest tests/ -v`
Resultado: **57 pasadas, 0 fallidas** (0,51 s).

| Archivo | Pruebas | Resultado |
|---|---|---|
| test_drivers_logic.py | 9 | ✅ 9/9 |
| test_hashing.py | 7 | ✅ 7/7 |
| test_health.py | 6 | ✅ 6/6 |
| test_hosts_blocker.py | 9 | ✅ 9/9 |
| test_registro.py | 7 | ✅ 7/7 |
| test_scancache.py | 9 | ✅ 9/9 |
| test_signatures.py | 2 | ✅ 2/2 |
| test_vpngate.py | 8 | ✅ 8/8 |
| **Total** | **57** | ✅ **57/57** |

Qué cubre: huellas SHA-256/MD5 y caché incremental del escáner (incl.
detección de la firma EICAR y re-hash al cambiar el archivo), generación y
retirada del bloque marcado del archivo hosts sin tocar el resto, parser
CSV de VPN Gate (campo Message con comas, Base64 en la última columna,
generación del `.ovpn`), comparación de versiones de drivers y cadena de
fuentes oficiales, puntuación de salud con los pesos congelados
(Defender 30, firewall 15, Windows 15, CFA 10, hallazgos 15, disco 10,
arranque 5) y registro de módulos.

Pruebas propias de los carriles (ejecutadas por cada carril en su fase, no
forman parte de la suite): Carril B, 23/23 comprobaciones del core de
seguridad; Carril C, 58 comprobaciones de drivers/SMART/limpieza.

## 3. Descubrimiento headless del registro y smoke de contratos

- `descubrir_modulos()` sin Qt: **9 módulos**, IDs únicos, orden ascendente
  correcto: panel (10), escaner (20), proteccion (30), drivers (40),
  limpieza (50), discos (60), actualizaciones (70), red (80),
  informes (90).
- Versión de contratos: **1.0-ola0** (congelada). Los fakes de cada módulo
  devuelven exactamente los dataclasses del contrato (cubierto por
  test_registro.py).
- Activo de dominios: `assets/dominios_fusionados.txt` con **100.776**
  líneas útiles (StevenBlack ∪ semilla Android). Por defecto el bloqueador
  usa la semilla de 19.563: Windows se degrada con decenas de miles de
  líneas de hosts; la fusionada queda como opción con aviso.

## 4. Degradación honesta fuera de Windows

- La capa `winapi` fuera de Windows lanza la excepción controlada
  `WindowsNoDisponible` («PowerShell solo está disponible en Windows»),
  verificada aquí llamando a `winapi.defender`; los servicios de la app la
  convierten en el sobre `ResultadoModulo(ok=False, …)`, nunca en un
  cuelgue ni en datos inventados.
- La lógica pura (escáner, hosts, VPN, drivers, salud) funciona y está
  probada en Linux; las páginas Qt se verificaron por py_compile y, en el
  carril B, con un PySide6 simulado.

## 5. Límites declarados (de los carriles y de la investigación)

- **La UI Qt no se renderizó en esta VM** (no hay PySide6 instalable aquí;
  falta el entorno gráfico/libEGL). El primer pintado real de las pantallas
  será en Windows, al compilar y abrir la app.
- **La base de huellas de fábrica trae solo EICAR** (1 huella de prueba).
  La detección plena depende de la actualización de firmas de abuse.ch
  (URLhaus/OpenPhish públicos; MalwareBazaar puede exigir la Auth-Key
  gratuita que el usuario guarda en Ajustes). El motor en tiempo real
  sigue siendo Microsoft Defender, por diseño.
- **Solo puede probarse en un Windows real:** escritura del archivo hosts
  con elevación UAC y su restauración, escaneos de Defender
  (Start-MpScan/MpCmdRun), lectura SMART de discos físicos (pySMART/
  smartctl y Get-PhysicalDisk), contraste e instalación de drivers vía
  Windows Update con punto de restauración, tarea semanal del Programador
  de tareas, `winget upgrade` real, y la delegación VPN a
  SoftEther/OpenVPN con un servidor de VPN Gate.
- La protección al instalar es vigilancia en modo usuario bajo demanda
  («Revisar ahora»), no un vigilante residente ni tiempo real de kernel;
  así está declarado en la propia pantalla.
- El contraste de drivers extrae la versión del título de Windows Update
  cuando no hay versión estructurada; la fila muestra siempre el detalle
  de lo que WU ofrece. La instalación de drivers vía WU es todo-o-nada.
- El instalador no lleva firma digital: Windows mostrará el aviso de
  SmartScreen la primera vez («Más información» → «Ejecutar de todas
  formas»).

## 6. Entrega

- Paquete: `antivirus-hogar-pc-v1.zip` (fuente completa, tests, packaging
  con `.spec` e `instalador.iss`, `Construir-en-Windows.bat`, `LEEME.md`,
  este `VERIFICACION.md` y los activos de dominios).
- Repositorio git inicializado con commit inicial: listo para subir a
  GitHub y activar el workflow de compilación en la nube.
- Copia del ZIP en la carpeta «Antivirus Hogar PC» de su Google Drive.
