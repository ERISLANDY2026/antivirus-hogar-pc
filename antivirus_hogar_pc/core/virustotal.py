"""VirusTotal SOLO por huella y con la clave del usuario (v1.0.21).

BYOK («trae tu propia clave»): el campo vive en Ajustes y la
consulta manda ÚNICAMENTE el SHA-256 a la API oficial
(GET /api/v3/files/<hash>). Esta vía JAMÁS sube archivos: no hay
ningún POST ni ningún cuerpo con contenido en este módulo, y una
guarda permanente de la suite lo vigila.

Sin clave, la función queda «sin configurar»: inerte, no intenta
nada y la interfaz lo dice tal cual.
"""
import json
import urllib.error
import urllib.request
from dataclasses import dataclass

URL_API = "https://www.virustotal.com/api/v3/files/"


@dataclass
class ResultadoVT:
    estado: str  # sin_configurar|ok|no_encontrado|clave_invalida|sin_respuesta
    maliciosos: int = 0
    sospechosos: int = 0
    total: int = 0
    enlace: str = ""


def consultar_hash(sha256: str, clave: str, timeout: int = 15) -> ResultadoVT:
    """Consulta el veredicto agregado de VirusTotal para una huella.

    Solo viaja el hash en la URL y la clave del propio usuario en
    la cabecera. Nunca se sube el archivo.
    """
    clave = (clave or "").strip()
    if not clave:
        return ResultadoVT(estado="sin_configurar")
    sha = (sha256 or "").strip().lower()
    if len(sha) != 64:
        return ResultadoVT(estado="sin_respuesta")
    peticion = urllib.request.Request(
        URL_API + sha, method="GET",
        headers={"x-apikey": clave, "accept": "application/json",
                 "User-Agent": "AntivirusHogarPC/1.0 (consulta por hash)"})
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as resp:
            datos = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return ResultadoVT(estado="no_encontrado")
        if exc.code in (401, 403):
            return ResultadoVT(estado="clave_invalida")
        return ResultadoVT(estado="sin_respuesta")
    except Exception:
        return ResultadoVT(estado="sin_respuesta")
    try:
        stats = (datos["data"]["attributes"]
                 ["last_analysis_stats"])
    except (KeyError, TypeError):
        return ResultadoVT(estado="sin_respuesta")
    maliciosos = int(stats.get("malicious", 0) or 0)
    sospechosos = int(stats.get("suspicious", 0) or 0)
    total = sum(int(v or 0) for v in stats.values()
                if isinstance(v, (int, float)))
    return ResultadoVT(
        estado="ok", maliciosos=maliciosos, sospechosos=sospechosos,
        total=total,
        enlace=f"https://www.virustotal.com/gui/file/{sha}")
