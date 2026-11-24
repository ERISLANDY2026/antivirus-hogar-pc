# CONTRATOS CONGELADOS — Antivirus Hogar PC · Ola 0 (2026-11-24)

**Versión de contratos: `1.0-ola0`** (`antivirus_hogar_pc/contracts.py`).
Nadie cambia un contrato sin pasar por el integrador. Si un carril necesita
otra forma, lo pide; no la inventa en su módulo.

## 1. Registro de módulos (auto-descubrible)

- Cada paquete en `antivirus_hogar_pc/modules/<paquete>/` declara sus
  módulos en `registro.py` como `REGISTROS: list[RegistroModulo]`.
- `registro.py` **no importa Qt**: el descubrimiento
  (`modules.descubrir_modulos()`) funciona sin interfaz (tests/CI).
- La página se crea perezosamente desde `RegistroModulo.pagina`
  («paquete.modulo:funcion», firma `crear_pagina(ctx) -> QWidget`).
- `main.py`/`main_window.py` **no se editan** al añadir módulos.
- IDs congelados: `panel` (A, ola 1) · `escaner` (B, ola 1) · `proteccion`
  (B, ola 2) · `drivers` (C, ola 2) · `limpieza` (C, ola 3) · `discos`
  (C, ola 2) · `actualizaciones` (D, ola 2) · `red` (D, ola 3) ·
  `informes` (B, ola 2). `ajustes` es de la carcasa (integrador).

## 2. Formas de intercambio (contracts.py)

| Forma | Productor → Consumidor | Notas |
|---|---|---|
| `ResultadoModulo` | todo módulo → UI | Sobre único: ok/mensaje/datos/detalle_tecnico. Los errores NO se lanzan a la UI. |
| `InformeSalud` | A (panel) | Incluye `ResultadoSalud` de `core.health.calcular_salud` (pesos congelados: Defender 30, firewall 15, Windows 15, CFA 10, hallazgos 15, disco 10, arranque 5). |
| `DatosPanel` | A (psutil) | CPU/RAM/disco del sistema en vivo. |
| `Hallazgo`, `ResultadoEscaneo` | B (`core.scanner`) | El usuario decide por hallazgo: cuarentena / eliminar / Defender. La app nunca actúa sola. |
| `HostsEstado` | B | Base por defecto: **semilla Android (19.563)**. La fusionada con StevenBlack (100.776) es opción con aviso: Windows se degrada con decenas de miles de líneas de hosts. |
| `DriverInstalado`, `EstadoDriver` | C (`core.drivers_logic`) | Cadena oficial: WU/Catalog → chip (NVIDIA/AMD/Intel) → OEM. Punto de restauración antes de instalar; solo firmados. |
| `SmartInfo` | C | `salud`: bien/regular/mal/desconocido. `sin_datos=True` = «no se puede leer» (USB/RAID), nunca «sano». Fuente: pySMART/smartctl; respaldo Get-PhysicalDisk. |
| `InformeTuneUp`, `PartidaLimpieza` | C (psutil + shell) | Primero informe, borrado tras confirmación. Arranque reversible. **Sin limpiador de registro.** |
| `ServidorVPN` | D (`core.vpngate`) | CSV de VPN Gate: parseo con `csv` + recomposición del campo Message (equivale a partir con límite: el Base64 es SIEMPRE la última columna, índice 14). La app delega en SoftEther/OpenVPN; no crea el túnel. |
| `InfoWifi` | D (`core.wifi_parse`) | Parseo de `netsh wlan` en español o inglés. |
| `ProgramaDesactualizado` | D (`core.winget_parse`) | Salida de `winget upgrade` por posiciones de cabecera. |
| `ActualizacionWindows` | D (COM WU) | Búsqueda `IsInstalled=0 and IsHidden=0`; drivers con `Type='Driver'`. |
| `ProgramaInstalado` | B (`core.watch_logic`) | Diff de instalados para la protección al instalar (modo usuario). |
| `ContextoModulo` | carcasa → páginas | Solo `servicios` (ServiciosApp) y `al_navegar(id)`. Las páginas no se importan entre sí. |

## 3. Capa winapi (firmas exactas, ya implementadas por el integrador)

- `winapi.powershell`: `ejecutar_powershell(script, timeout) -> str`,
  `ejecutar_powershell_json(...)`, `ejecutar_elevado(script) -> bool` (UAC,
  solo tras confirmación del usuario), `ejecutar_comando(args) -> (rc, out, err)`.
  Fuera de Windows: `WindowsNoDisponible` (la UI lo traduce vía
  `ui.services.seguro`).
- `winapi.defender`: `estado_defender()`, `perfiles_firewall()`,
  `escanear_con_defender(tipo, ruta)`, `analizar_archivo_defender(ruta)`,
  `estado_cfa()`, `activar_cfa(modo)` (empezar en **auditoría**),
  `agregar_carpeta_protegida(ruta)`.
- `winapi.system_info`: `version_windows()`, `actualizaciones_pendientes_windows()`,
  `programas_instalados()`, `elementos_arranque()`, `tareas_programadas()`
  (con marca de sospecha de `core.watch_logic`), `servicios_terceros()`,
  `info_wifi()`, `perfil_red()`, `fabricante_y_modelo_pc()`.
- `winapi.disks`: `discos_fisicos()`, `volumenes()`, `optimizar_volumen(letra, es_ssd)`
  (Optimize-Volume: -Defrag HDD / -ReTrim SSD).
- `winapi.drivers_win`: `enumerar_drivers()` (Win32_PnPSignedDriver),
  `buscar_drivers_windows_update()`, `instalar_drivers_windows_update(ids)`,
  `crear_punto_restauracion(descripcion)`.
- `winapi.tuneup_win`: temporales (analizar/limpiar), papelera, arranque
  reversible de la carpeta de inicio, `respaldo_registro()`, hosts
  (`leer_hosts`, `escribir_hosts_elevado` con respaldo previo), winget.
- `winapi.tasks`: tarea semanal (`schtasks`, «Antivirus Hogar - Escaneo
  semanal», `--escaneo-programado`) y `notificar_windows(titulo, mensaje)`.
- `winapi.vpn_win`: `clientes_vpn_instalados()`, `guardar_ovpn()`,
  `abrir_perfil_vpn()`, `ip_publica_actual()`.

## 4. Reutilización obligada (no reinventar)

- Tema: QSS propio del proyecto (paleta aprobada por el usuario: fondo
  #0B0F17, tarjetas #141B29 con borde #24304A, cian #22D3EE). qt-material es
  alternativa documentada; **QFluentWidgets prohibido (GPLv3)**.
- Panel/tune-up: **psutil**. SMART: **pySMART/smartctl** (el instalador
  incluirá smartctl.exe). Dominios: **StevenBlack/hosts** fusionado con la
  semilla Android → `assets/dominios_fusionados.txt` (100.776 únicos, ya
  generado en la Ola 0). Programas: **winget**. Drivers: **WMI
  Win32_PnPSignedDriver / pnputil**. VPN: **API CSV de VPN Gate**.

## 5. Propiedad de archivos por carril

| Carril | Propiedad exclusiva |
|---|---|
| Integrador | `contracts.py`, `CONTRATOS.md`, `modules/__init__.py`, `ui/main.py`, `ui/main_window.py`, `ui/paginas_base.py`, `ui/ajustes_page.py`, `ui/services.py`, `winapi/` (base), `config.py` |
| A — Presentación | `ui/theme.py`, `ui/icons.py`, `ui/health_ring.py`, `modules/panel/` |
| B — Seguridad | `modules/security/`, `core/scanner.py`, `core/signatures.py`, `core/scancache.py`, `core/hashing.py`, `core/quarantine.py`, `core/hosts_blocker.py`, `core/threats_update.py`, `core/watch_logic.py` |
| C — Sistema | `modules/system/`, `core/drivers_logic.py` |
| D — Red/actualizaciones | `modules/net/`, `core/vpngate.py`, `core/wifi_parse.py`, `core/winget_parse.py`, `core/updater.py` |
| E — Transversal | `tests/`, `packaging/` (.spec/.iss), `.github/`, `assets/`, LEEME/README |

`core/health.py` y `core/__init__.py`: compartidos, cambios solo vía integrador.

## 6. Entrega por olas

- **Ola 1 → v1 instalable:** núcleo + `panel` + `escaner` reales.
- **Ola 2:** `proteccion` (hosts), `informes`, `drivers`, `discos`, `actualizaciones`.
- **Ola 3:** `limpieza`, `red` (VPN Gate + Wi-Fi).
- Puerta del usuario (sigue vigente): verificación completa del código y
  aviso antes de instalar nada en su PC; la entrega es el .exe instalable
  (PyInstaller `--onedir` + Inno Setup; compilación en su PC con
  `Construir-en-Windows.bat` o en GitHub Actions `windows-latest`, carril E).
