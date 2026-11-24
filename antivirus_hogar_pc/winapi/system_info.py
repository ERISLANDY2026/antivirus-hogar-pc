"""Información del sistema: versión de Windows, actualizaciones pendientes,
programas instalados, arranque, tareas programadas y servicios."""
import re

from ..core.watch_logic import ProgramaInstalado, es_tarea_sospechosa
from .powershell import como_lista, ejecutar_comando, ejecutar_powershell_json


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
