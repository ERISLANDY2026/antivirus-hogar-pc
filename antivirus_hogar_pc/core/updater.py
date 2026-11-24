"""Auto-actualización propia (mismo esquema que Android).

Se descarga un version.json del canal de Drive con:
  {"version": "1.1.0", "notas": "Qué trae…", "url": "https://…/instalador.exe",
   "sha256": "…huella del instalador…"}

La app compara versiones, enseña el diálogo «Qué trae esta actualización» y,
solo si el usuario pulsa el botón verde, descarga el instalador, VERIFICA su
SHA-256 y lo abre. En Windows sin firma, SmartScreen avisará: es lo esperado
y se explica en el propio diálogo.
"""
import json
import os
import urllib.request
from dataclasses import dataclass

from .drivers_logic import comparar_versiones
from .hashing import sha256_archivo


@dataclass
class InfoActualizacion:
    version: str
    notas: str
    url: str
    sha256: str = ""


def parsear_version_json(texto: str) -> InfoActualizacion:
    datos = json.loads(texto)
    return InfoActualizacion(
        version=str(datos.get("version", "")).strip(),
        notas=str(datos.get("notas", "")).strip(),
        url=str(datos.get("url", "")).strip(),
        sha256=str(datos.get("sha256", "")).strip().lower(),
    )


def hay_actualizacion(version_actual: str, info: InfoActualizacion) -> bool:
    return bool(info.version) and comparar_versiones(info.version, version_actual) > 0


def descargar_texto(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "AntivirusHogarPC"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def descargar_archivo(url: str, destino: str, timeout: int = 600) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "AntivirusHogarPC"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(destino, "wb") as f:
        while True:
            bloque = resp.read(1024 * 256)
            if not bloque:
                break
            f.write(bloque)
    return destino


def verificar_sha256(ruta: str, esperado: str) -> bool:
    if not esperado:
        return False
    return sha256_archivo(ruta).lower() == esperado.lower()


def comprobar_actualizacion(url_version: str, version_actual: str) -> InfoActualizacion | None:
    """Devuelve la info si hay una versión más nueva; None si no la hay."""
    if not url_version:
        return None
    info = parsear_version_json(descargar_texto(url_version))
    return info if hay_actualizacion(version_actual, info) else None


def nombre_instalador(url: str) -> str:
    nombre = os.path.basename(url.split("?")[0]) or "AntivirusHogarPC-Setup.exe"
    if not nombre.lower().endswith(".exe"):
        nombre += ".exe"
    return nombre
