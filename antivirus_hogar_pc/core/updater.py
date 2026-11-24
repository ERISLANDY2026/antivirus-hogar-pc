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
import urllib.error
import urllib.request
from dataclasses import dataclass

from .drivers_logic import comparar_versiones
from .hashing import sha256_archivo


class ErrorActualizacion(Exception):
    """Fallo al comprobar el canal, CLASIFICADO para un mensaje honesto.

    tipo:
    - "sin_conexion": no se llegó al servidor (red caída, DNS, tiempo fuera).
    - "no_encontrado": el servidor respondió 404: el archivo de versión no
      está publicado (esto fue el bug de la v1.0.1: el id era un marcador).
    - "respuesta_invalida": respondió, pero el contenido no es un
      version-pc.json válido.
    """

    def __init__(self, tipo: str, detalle: str = ""):
        super().__init__(detalle or tipo)
        self.tipo = tipo
        self.detalle = detalle


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
    """Descarga texto clasificando el fallo (ErrorActualizacion)."""
    req = urllib.request.Request(url, headers={"User-Agent": "AntivirusHogarPC"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ErrorActualizacion(
                "no_encontrado", f"HTTP 404 en {url}") from exc
        raise ErrorActualizacion(
            "respuesta_invalida", f"HTTP {exc.code} en {url}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ErrorActualizacion("sin_conexion", str(exc)) from exc


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
    """Devuelve la info si hay una versión más nueva; None si no la hay.

    Lanza ErrorActualizacion clasificado si el canal falla: quien llama
    (la página, vía servicios) enseña el mensaje que corresponde a la
    causa REAL, no un genérico «revisa tu conexión»."""
    if not url_version:
        raise ErrorActualizacion("no_encontrado", "Canal sin configurar.")
    texto = descargar_texto(url_version)
    try:
        info = parsear_version_json(texto)
    except (ValueError, TypeError) as exc:
        raise ErrorActualizacion(
            "respuesta_invalida", f"El canal no devolvió un JSON válido: {exc}") from exc
    if not info.version:
        raise ErrorActualizacion(
            "respuesta_invalida", "El archivo de versión no trae campo «version».")
    return info if hay_actualizacion(version_actual, info) else None


def nombre_instalador(url: str) -> str:
    nombre = os.path.basename(url.split("?")[0]) or "AntivirusHogarPC-Setup.exe"
    if not nombre.lower().endswith(".exe"):
        nombre += ".exe"
    return nombre
