"""Auditoría de exclusiones de Defender (v1.0.21): lógica pura.

Una exclusión le dice a Defender «aquí no mires»: útil en manos
del usuario, oro en manos de un malware que logra añadir la suya.
Esta auditoría es SOLO LECTURA: lista las exclusiones activas y
señala las riesgosas con el motivo. La app no borra exclusiones
por su cuenta — quitar una es decisión del usuario en la propia
configuración de Windows, y la interfaz lo explica.
"""
import re

EXTENSIONES_PELIGROSAS = {
    ".exe", ".dll", ".sys", ".scr", ".com", ".bat", ".cmd", ".ps1",
    ".vbs", ".js", ".jse", ".wsf", ".hta", ".msi", ".jar", ".reg",
}

# Carpetas donde un malware «vive» típicamente si quedan excluidas.
_PATRONES_RUTA_ALTA = [
    (re.compile(r"^[a-z]:\\?$", re.I), "raiz_unidad"),
    (re.compile(r"^[a-z]:\\windows(\\.*)?$", re.I), "carpeta_sistema"),
    (re.compile(r"^[a-z]:\\users\\[^\\]+\\appdata\\", re.I), "appdata"),
    (re.compile(r"\\temp(\\.*)?$", re.I), "temporal"),
    (re.compile(r"^[a-z]:\\users\\[^\\]+\\?$", re.I), "perfil_completo"),
    (re.compile(r"^[a-z]:\\programdata(\\.*)?$", re.I), "programdata"),
]

_PROCESOS_SENSIBLES = {
    "powershell.exe", "cmd.exe", "wscript.exe", "cscript.exe",
    "mshta.exe", "rundll32.exe", "regsvr32.exe", "explorer.exe", "*",
}


def clasificar_ruta(ruta: str) -> tuple[str, str]:
    """(nivel, motivo): nivel alta|media|baja."""
    valor = (ruta or "").strip()
    if not valor:
        return "baja", ""
    for patron, motivo in _PATRONES_RUTA_ALTA:
        if patron.match(valor):
            return "alta", motivo
    if valor.endswith("\\") and valor.count("\\") <= 2:
        return "media", "carpeta_amplia"
    return "baja", ""


def clasificar_extension(extension: str) -> tuple[str, str]:
    valor = (extension or "").strip().lower()
    if not valor.startswith("."):
        valor = "." + valor
    if valor in EXTENSIONES_PELIGROSAS:
        return "alta", "extension_ejecutable"
    return "baja", ""


def clasificar_proceso(proceso: str) -> tuple[str, str]:
    valor = (proceso or "").strip().lower()
    nombre = valor.replace("/", "\\").rsplit("\\", 1)[-1]
    if nombre in _PROCESOS_SENSIBLES:
        return "alta", "proceso_sensible"
    if "*" in valor:
        return "media", "comodin"
    return "baja", ""


def clasificar_ip(ip: str) -> tuple[str, str]:
    valor = (ip or "").strip()
    if valor in ("0.0.0.0/0", "::/0", "*"):
        return "alta", "red_completa"
    return "media", "ip_excluida"


_CLASIFICADORES = {
    "ruta": clasificar_ruta,
    "extension": clasificar_extension,
    "proceso": clasificar_proceso,
    "ip": clasificar_ip,
}


def auditar(exclusiones: dict | None) -> list[dict]:
    """Lista [{tipo, valor, nivel, motivo}] ordenada por riesgo.

    exclusiones: {"ruta": [...], "extension": [...],
    "proceso": [...], "ip": [...]} desde winapi.defender.
    """
    salida: list[dict] = []
    if not isinstance(exclusiones, dict):
        return salida
    for tipo, clasificador in _CLASIFICADORES.items():
        for valor in exclusiones.get(tipo, []) or []:
            nivel, motivo = clasificador(str(valor))
            salida.append({"tipo": tipo, "valor": str(valor),
                           "nivel": nivel, "motivo": motivo})
    orden = {"alta": 0, "media": 1, "baja": 2}
    salida.sort(key=lambda e: (orden.get(e["nivel"], 3), e["tipo"]))
    return salida


def hay_riesgos(auditoria: list[dict]) -> bool:
    return any(e["nivel"] == "alta" for e in auditoria)
