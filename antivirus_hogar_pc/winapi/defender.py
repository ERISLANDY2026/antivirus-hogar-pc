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


# --- Exclusión anti-falso-positivo e integridad propia (v1.0.7, punto 4) -----
# En la PC real del usuario, Defender BORRÓ la 1.0.6 instalada (falso
# positivo clásico contra ejecutables PyInstaller sin firmar que
# además tocan el hosts, lanzan PowerShell elevado oculto y
# descargan-y-ejecutan su actualizador). La solución integrada:
# (1) el INSTALADOR (admin) ejecuta packaging/exclusion_defender.ps1,
# que añade la exclusión SOLO para las dos carpetas propias
# (instalación y datos) y la VERIFICA leyéndola de vuelta
# (Get-MpPreference), dejando el resultado en
# {app}\defender-exclusion.json — declarado, nada oculto;
# (2) al abrir, la app lee ese resultado y, si la exclusión no quedó
# (Protección contra alteraciones o política), AVISA con el paso
# manual mínimo — nunca finge que quedó puesta;
# (3) al abrir, la app comprueba su propia integridad contra el
# manifiesto del instalador ({app}\componentes.json).

import json as _json
import sys as _sys

PASO_MANUAL_EXCLUSION = (
    "Defender no dejó guardar la exclusión automática de las "
    "carpetas de la app (suele ser la Protección contra "
    "alteraciones o una política del equipo). Para ponerla a mano: "
    "Seguridad de Windows → Protección contra virus y amenazas → "
    "Administrar la configuración → Exclusiones → Agregar exclusión "
    "→ Carpeta, y añade estas dos carpetas: la de instalación de "
    "Antivirus Hogar PC (en Archivos de programa) y "
    "%LOCALAPPDATA%\\AntivirusHogarPC. Sin la exclusión, Defender "
    "podría volver a borrar la app por falso positivo."
)


def carpeta_instalacion() -> str:
    """Carpeta donde vive el ejecutable de la app."""
    return os.path.dirname(os.path.abspath(_sys.executable))


def rutas_exclusion() -> tuple[str, str]:
    """Las ÚNICAS dos rutas que la exclusión cubre: instalación y datos."""
    from .. import config

    return carpeta_instalacion(), config.carpeta_datos()


def interpretar_resultado_exclusion(datos) -> dict:
    """Traduce el JSON del instalador a un estado claro.

    Entrada: el dict de defender-exclusion.json (o None si no hay).
    Salida: {"estado": "aplicada"|"ya_estaba"|"bloqueada"|"sin_datos",
             "avisar": bool, "detalle": str, "paso_manual": str}
    """
    if not isinstance(datos, dict):
        return {"estado": "sin_datos", "avisar": False,
                "detalle": "El instalador no dejó resultado de la "
                           "exclusión de Defender.",
                "paso_manual": ""}
    app_ok = bool(datos.get("app"))
    datos_ok = bool(datos.get("datos"))
    if app_ok and datos_ok:
        if datos.get("ya_estaban"):
            return {"estado": "ya_estaba", "avisar": False,
                    "detalle": "La exclusión de Defender ya cubría "
                               "las carpetas de la app.",
                    "paso_manual": ""}
        return {"estado": "aplicada", "avisar": False,
                "detalle": "Exclusión de Defender aplicada y "
                           "verificada para las carpetas de la app "
                           "(instalación y datos).",
                "paso_manual": ""}
    error = str(datos.get("error") or "").strip()
    return {"estado": "bloqueada", "avisar": True,
            "detalle": ("La exclusión de Defender NO quedó aplicada "
                        f"(instalación={app_ok}, datos={datos_ok})."
                        + (f" Motivo: {error}" if error else "")),
            "paso_manual": PASO_MANUAL_EXCLUSION}


def leer_resultado_instalador(carpeta: str | None = None) -> dict | None:
    """Lee {app}\\defender-exclusion.json si el instalador lo dejó."""
    ruta = os.path.join(carpeta or carpeta_instalacion(),
                        "defender-exclusion.json")
    try:
        with open(ruta, "r", encoding="utf-8-sig") as f:
            datos = _json.load(f)
        return datos if isinstance(datos, dict) else None
    except (OSError, ValueError):
        return None


def verificar_integridad_propia(carpeta: str | None = None) -> dict:
    """Comprueba los componentes del manifiesto de instalación.

    El instalador deja {app}\\componentes.json con las rutas
    relativas que deben existir (el .exe, el icono, el script de
    exclusión y, si fue incorporado, el instalador de OpenVPN). Si
    un antivirus se llevó algo, aquí se ve. Sin manifiesto
    (instalaciones anteriores), se comprueba lo básico: el propio
    ejecutable.
    """
    base = carpeta or carpeta_instalacion()
    esperados: list[str] = []
    try:
        with open(os.path.join(base, "componentes.json"), "r",
                  encoding="utf-8-sig") as f:
            datos = _json.load(f)
        if isinstance(datos, list):
            esperados = [str(x) for x in datos]
    except (OSError, ValueError):
        esperados = []
    con_manifiesto = bool(esperados)
    if not esperados:
        esperados = [os.path.basename(os.path.abspath(_sys.executable))]
    faltan = [e for e in esperados
              if not os.path.isfile(os.path.join(base, e))]
    return {"ok": not faltan, "faltan": faltan,
            "con_manifiesto": con_manifiesto}


def comprobar_al_arranque(registrar) -> dict:
    """Chequeo de arranque (punto 4): exclusión + integridad.

    ``registrar(tipo, detalle)`` es el registro de actividad de la
    app. Devuelve {"aviso": str|None, "exclusion": {...},
    "integridad": {...}}: el aviso (si lo hay) es el texto que la
    ventana enseña al abrir. Nunca lanza: la app abre igual.
    """
    resultado = interpretar_resultado_exclusion(leer_resultado_instalador())
    registrar("defender", resultado["detalle"])
    integridad = verificar_integridad_propia()
    if integridad["ok"]:
        registrar("defender",
                  "Integridad al arranque: todos los componentes de "
                  "la app están en su sitio.")
    else:
        registrar("defender",
                  "Integridad al arranque: FALTAN componentes de la "
                  "app (¿un antivirus los borró?): "
                  + ", ".join(integridad["faltan"]))
    aviso = None
    if resultado["avisar"]:
        aviso = resultado["paso_manual"]
    elif not integridad["ok"]:
        aviso = ("Faltan componentes de Antivirus Hogar PC: "
                 + ", ".join(integridad["faltan"])
                 + ". Es posible que Defender los haya borrado por "
                   "falso positivo: reinstala la app desde el zip "
                   "oficial y revisa la exclusión de Defender.")
    return {"aviso": aviso, "exclusion": resultado,
            "integridad": integridad}
