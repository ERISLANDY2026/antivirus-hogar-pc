"""Microsoft Defender y firewall: lectura de estado y escaneos orquestados.

Comandos documentados por Microsoft:
- Get-MpComputerStatus / Get-MpPreference / Set-MpPreference
- Start-MpScan y MpCmdRun.exe -Scan -ScanType 1|2|3
- Get-NetFirewallProfile
"""
import os
from datetime import datetime, timezone

from .powershell import como_lista, ejecutar_elevado, ejecutar_powershell, ejecutar_powershell_json


def estado_defender() -> dict:
    """Estado de Defender. Claves normalizadas en español de dominio."""
    script = (
        "Get-MpComputerStatus | Select-Object AntivirusEnabled, "
        "RealTimeProtectionEnabled, BehaviorMonitorEnabled, "
        "AntivirusSignatureVersion, AntivirusSignatureLastUpdated, "
        "IsTamperProtected, QuickScanEndTime, FullScanEndTime | ConvertTo-Json"
    )
    datos = ejecutar_powershell_json(script)
    if not datos:
        return {}
    ultima = _parsear_fecha_ms(datos.get("AntivirusSignatureLastUpdated"))
    firmas_al_dia = None
    if ultima is not None:
        antiguedad_dias = (datetime.now(timezone.utc) - ultima).days
        firmas_al_dia = antiguedad_dias <= 2
    return {
        "activo": bool(datos.get("AntivirusEnabled")),
        "tiempo_real": bool(datos.get("RealTimeProtectionEnabled")),
        "monitor_conducta": bool(datos.get("BehaviorMonitorEnabled")),
        "version_firmas": datos.get("AntivirusSignatureVersion") or "",
        "firmas_al_dia": firmas_al_dia,
        "tamper_protection": bool(datos.get("IsTamperProtected")),
        "ultimo_escaneo_rapido": datos.get("QuickScanEndTime") or "",
        "ultimo_escaneo_completo": datos.get("FullScanEndTime") or "",
    }


def _parsear_fecha_ms(valor) -> datetime | None:
    """PowerShell serializa fechas como /Date(123456789)/ en JSON clásico."""
    if isinstance(valor, str) and valor.startswith("/Date("):
        try:
            ms = int(valor[6:].split(")")[0].split("+")[0].split("-")[0])
            return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        except (ValueError, OSError):
            return None
    if isinstance(valor, str) and valor:
        try:
            return datetime.fromisoformat(valor.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def perfiles_firewall() -> list[dict]:
    script = "Get-NetFirewallProfile | Select-Object Name, Enabled | ConvertTo-Json"
    datos = como_lista(ejecutar_powershell_json(script))
    nombres = {"Domain": "Dominio", "Private": "Privado", "Public": "Público"}
    return [
        {"perfil": nombres.get(d.get("Name", ""), d.get("Name", "")),
         "activo": bool(d.get("Enabled"))}
        for d in datos
    ]


def firewall_todo_activo(perfiles: list[dict]) -> bool:
    return bool(perfiles) and all(p["activo"] for p in perfiles)


def escanear_con_defender(tipo: str = "rapido", ruta: str | None = None) -> str:
    """Lanza un escaneo de Defender. tipo: rapido | completo | ruta."""
    if tipo == "completo":
        script = "Start-MpScan -ScanType FullScan"
    elif tipo == "ruta" and ruta:
        ruta_esc = ruta.replace("'", "''")
        script = f"Start-MpScan -ScanType CustomScan -ScanPath '{ruta_esc}'"
    else:
        script = "Start-MpScan -ScanType QuickScan"
    ejecutar_powershell(script, timeout=3600)
    return "Escaneo de Defender lanzado."


def ruta_mpcmdrun() -> str:
    base = os.environ.get("ProgramFiles", r"C:\Program Files")
    return os.path.join(base, "Windows Defender", "MpCmdRun.exe")


def analizar_archivo_defender(ruta: str) -> tuple[int, str]:
    """MpCmdRun -Scan -ScanType 3 -File <ruta>. 0 = limpio, 2 = amenaza."""
    from .powershell import ejecutar_comando

    codigo, salida, error = ejecutar_comando(
        [ruta_mpcmdrun(), "-Scan", "-ScanType", "3", "-File", ruta, "-DisableRemediation"],
        timeout=600,
    )
    return codigo, (salida or error or "").strip()


def amenazas_detectadas_defender() -> list[dict]:
    script = (
        "Get-MpThreatDetection | Select-Object -First 20 ThreatID, "
        "InitialDetectionTime, Resources | ConvertTo-Json -Depth 4"
    )
    try:
        return como_lista(ejecutar_powershell_json(script))
    except Exception:
        return []


# --- Protección de carpetas contra ransomware (Controlled Folder Access) ----
def estado_cfa() -> dict:
    """0 = desactivado, 1 = activado, 2 = modo auditoría."""
    script = "(Get-MpPreference).EnableControlledFolderAccess | ConvertTo-Json"
    datos = ejecutar_powershell_json(script)
    valor = int(datos) if isinstance(datos, (int, float)) else 0
    textos = {0: "Desactivada", 1: "Activada", 2: "Modo auditoría (solo avisa)"}
    return {"valor": valor, "texto": textos.get(valor, f"Valor {valor}"),
            "activo": valor in (1, 2)}


def activar_cfa(modo: str = "auditoria") -> bool:
    """Activa CFA (exige administrador → UAC). modo: auditoria | activado."""
    valor = "AuditMode" if modo == "auditoria" else "Enabled"
    return ejecutar_elevado(f"Set-MpPreference -EnableControlledFolderAccess {valor}")


def desactivar_cfa() -> bool:
    return ejecutar_elevado("Set-MpPreference -EnableControlledFolderAccess Disabled")


def agregar_carpeta_protegida(ruta: str) -> bool:
    ruta_esc = ruta.replace("'", "''")
    return ejecutar_elevado(
        f"Add-MpPreference -ControlledFolderAccessProtectedFolders '{ruta_esc}'"
    )
