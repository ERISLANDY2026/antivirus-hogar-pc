"""Información del sistema: versión de Windows, actualizaciones pendientes,
programas instalados, arranque, tareas programadas y servicios."""
import re

from ..core.watch_logic import ProgramaInstalado, es_tarea_sospechosa
from . import WindowsNoDisponible, es_windows
from .powershell import como_lista, ejecutar_comando, ejecutar_powershell_json


def interpretar_estado_energia(ac_line_status, battery_flag,
                               battery_pct_raw) -> dict:
    """Interpreta los códigos de GetSystemPowerStatus (puro,
    probado sin Windows): ACLineStatus 1 = con cargador,
    0 = con batería, 255 = desconocido; BatteryFlag 128 =
    no hay batería (un sobremesa), 255 = desconocido."""
    if battery_flag == 128:
        sin_bateria = True
    else:
        sin_bateria = False
    if ac_line_status == 1:
        con_cargador: bool | None = True
    elif ac_line_status == 0:
        con_cargador = False
    else:
        con_cargador = None
    pct = battery_pct_raw if isinstance(battery_pct_raw, int) \
        and 0 <= battery_pct_raw <= 100 else None
    return {"con_cargador": con_cargador, "bateria_pct": pct,
            "sin_bateria": sin_bateria}


def estado_bateria() -> dict:
    """Estado de energía del equipo (v1.0.16, frente 6):
    {con_cargador, bateria_pct, sin_bateria} vía
    GetSystemPowerStatus (ctypes, sin PowerShell: es un sondeo
    ligero cada ~30 s). Fuera de Windows lanza
    WindowsNoDisponible, como el resto de la capa."""
    if not es_windows():
        raise WindowsNoDisponible("GetSystemPowerStatus es de Windows")
    import ctypes

    class _SYSTEM_POWER_STATUS(ctypes.Structure):
        _fields_ = [("ACLineStatus", ctypes.c_byte),
                    ("BatteryFlag", ctypes.c_byte),
                    ("BatteryLifePercent", ctypes.c_byte),
                    ("SystemStatusFlag", ctypes.c_byte),
                    ("BatteryLifeTime", ctypes.c_ulong),
                    ("BatteryFullLifeTime", ctypes.c_ulong)]

    estado = _SYSTEM_POWER_STATUS()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(
            ctypes.byref(estado)):
        raise WindowsNoDisponible("GetSystemPowerStatus no respondió")
    return interpretar_estado_energia(
        int(estado.ACLineStatus), int(estado.BatteryFlag),
        int(estado.BatteryLifePercent))


def version_windows() -> dict:
    """{nombre, build, es_windows_11, es_windows_10}."""
    script = (
        "Get-ComputerInfo | Select-Object WindowsProductName, OsBuildNumber, "
        "WindowsVersion | ConvertTo-Json"
    )
    datos = ejecutar_powershell_json(script) or {}
    build = 0
    try:
        build = int(str(datos.get("OsBuildNumber", "0")).strip() or 0)
    except ValueError:
        build = 0
    nombre = str(datos.get("WindowsProductName", "Windows"))
    return {
        "nombre": nombre,
        "build": build,
        "es_windows_11": build >= 22000,
        "es_windows_10": 10240 <= build < 22000,
    }


def actualizaciones_pendientes_windows() -> list[dict]:
    """Vía COM Microsoft.Update.Session (buscar NO exige administrador)."""
    script = (
        "$s = New-Object -ComObject Microsoft.Update.Session; "
        "$b = $s.CreateUpdateSearcher(); "
        "$r = $b.Search(\"IsInstalled=0 and IsHidden=0\"); "
        "$r.Updates | ForEach-Object { [PSCustomObject]@{ "
        "Titulo = $_.Title; Descargada = [bool]$_.IsDownloaded; "
        "Reinicio = [bool]$_.RebootRequired } } | ConvertTo-Json"
    )
    datos = como_lista(ejecutar_powershell_json(script, timeout=600))
    return [
        {"titulo": d.get("Titulo", ""), "descargada": bool(d.get("Descargada")),
         "reinicio": bool(d.get("Reinicio"))}
        for d in datos
    ]


def fabricante_y_modelo_pc() -> dict:
    script = (
        "Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model "
        "| ConvertTo-Json"
    )
    datos = ejecutar_powershell_json(script) or {}
    return {"fabricante": datos.get("Manufacturer", ""), "modelo": datos.get("Model", "")}


def programas_instalados() -> dict[str, ProgramaInstalado]:
    """Claves Uninstall del registro (HKLM, HKLM Wow6432Node y HKCU)."""
    script = (
        "$rutas = @("
        "'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',"
        "'HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',"
        "'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*'); "
        "Get-ItemProperty $rutas -ErrorAction SilentlyContinue | "
        "Where-Object { $_.DisplayName } | "
        "Select-Object DisplayName, Publisher, DisplayVersion, InstallDate, "
        "EstimatedSize, UninstallString, InstallLocation | ConvertTo-Json"
    )
    datos = como_lista(ejecutar_powershell_json(script, timeout=300))
    programas: dict[str, ProgramaInstalado] = {}
    for d in datos:
        nombre = (d.get("DisplayName") or "").strip()
        if not nombre:
            continue
        programas[nombre.lower()] = ProgramaInstalado(
            nombre=nombre,
            editor=d.get("Publisher") or "",
            version=d.get("DisplayVersion") or "",
            fecha_instalacion=_formatear_fecha_instalacion(d.get("InstallDate")),
            tamano_kb=int(d.get("EstimatedSize") or 0),
            cadena_desinstalacion=d.get("UninstallString") or "",
            carpeta=d.get("InstallLocation") or "",
        )
    return programas


def _formatear_fecha_instalacion(valor) -> str:
    texto = str(valor or "")
    if re.fullmatch(r"\d{8}", texto):
        return f"{texto[6:8]}/{texto[4:6]}/{texto[0:4]}"
    return texto


def elementos_arranque() -> list[dict]:
    """Win32_StartupCommand: Run/RunOnce, carpeta de inicio y registro."""
    script = (
        "Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, "
        "Location, User | ConvertTo-Json"
    )
    datos = como_lista(ejecutar_powershell_json(script))
    return [
        {"nombre": d.get("Name", ""), "comando": d.get("Command", ""),
         "ubicacion": d.get("Location", ""), "usuario": d.get("User", "")}
        for d in datos
    ]


def tareas_programadas() -> list[dict]:
    """Tareas con su acción; marca las sospechosas con la heurística de core."""
    script = (
        "Get-ScheduledTask | ForEach-Object { $t = $_; "
        "[PSCustomObject]@{ Nombre = $t.TaskName; Ruta = $t.TaskPath; "
        "Autor = $t.Author; Estado = [string]$t.State; "
        "Accion = ($t.Actions | ForEach-Object { $_.Execute + ' ' + $_.Arguments }) -join '; ' } "
        "} | ConvertTo-Json"
    )
    datos = como_lista(ejecutar_powershell_json(script, timeout=300))
    tareas: list[dict] = []
    for d in datos:
        sospechosa, motivo = es_tarea_sospechosa(d.get("Accion", ""), d.get("Autor", ""))
        tareas.append({
            "nombre": d.get("Nombre", ""), "ruta": d.get("Ruta", ""),
            "autor": d.get("Autor", "") or "", "estado": d.get("Estado", ""),
            "accion": d.get("Accion", ""),
            "sospechosa": sospechosa, "motivo_sospecha": motivo,
        })
    return tareas


def servicios_terceros() -> list[dict]:
    """Servicios automáticos cuyo ejecutable NO está en la carpeta de Windows."""
    script = (
        "Get-CimInstance Win32_Service | Where-Object { $_.StartMode -eq 'Auto' "
        "-and $_.PathName -notmatch 'Windows' } | "
        "Select-Object Name, DisplayName, State, PathName | ConvertTo-Json"
    )
    datos = como_lista(ejecutar_powershell_json(script, timeout=300))
    return [
        {"nombre": d.get("DisplayName") or d.get("Name", ""),
         "estado": d.get("State", ""), "ruta": d.get("PathName", "")}
        for d in datos
    ]


def info_wifi() -> str:
    """Salida cruda de netsh wlan show interfaces (la parsea core.wifi_parse)."""
    _codigo, salida, _error = ejecutar_comando(
        ["netsh", "wlan", "show", "interfaces"], timeout=60
    )
    return salida


def perfil_red() -> str:
    """Categoría de la red activa: Pública o Privada."""
    script = (
        "Get-NetConnectionProfile | Select-Object -First 1 NetworkCategory "
        "| ConvertTo-Json"
    )
    datos = ejecutar_powershell_json(script) or {}
    return str(datos.get("NetworkCategory", ""))


def info_red_local(nombre_interfaz: str = "") -> dict:
    """IP local, puerta de enlace y DNS de la conexión (v1.0.5).

    Get-NetIPConfiguration de la interfaz pedida (la Wi-Fi) o, si no se
    pide ninguna o no tiene puerta de enlace, de la primera interfaz
    con puerta IPv4 (la conexión activa, p. ej. Ethernet). Proceso
    oculto como todo PowerShell de la app. Devuelve {} si no hay datos:
    la UI lo enseña como «—», nunca inventa valores.
    """
    filtro = ""
    if nombre_interfaz:
        seguro_ps = nombre_interfaz.replace("'", "''")
        filtro = f" | Where-Object {{ $_.InterfaceAlias -eq '{seguro_ps}' }}"
    script = (
        f"$c = Get-NetIPConfiguration{filtro} | "
        "Where-Object { $_.IPv4Address } | "
        "Sort-Object { -not $_.IPv4DefaultGateway } | Select-Object -First 1; "
        "if ($c) { [PSCustomObject]@{ "
        "Interfaz = $c.InterfaceAlias; "
        "IP = [string]$c.IPv4Address.IPAddress; "
        "PuertaEnlace = [string]$c.IPv4DefaultGateway.NextHop; "
        "DNS = @($c.DNSServer | Where-Object { $_.AddressFamily -eq 2 } | "
        "ForEach-Object { $_.ServerAddresses }) } | ConvertTo-Json } "
        "else { '{}' }"
    )
    datos = ejecutar_powershell_json(script) or {}
    dns = datos.get("DNS") or []
    if isinstance(dns, str):
        dns = [dns]
    return {
        "interfaz": str(datos.get("Interfaz") or ""),
        "ip": str(datos.get("IP") or ""),
        "puerta_enlace": str(datos.get("PuertaEnlace") or ""),
        "dns": [str(d) for d in dns if d],
    }
