"""Chequeo BYOVD de drivers (v1.0.21).

BYOVD («trae tu propio driver vulnerable»): un atacante instala un
driver legítimo pero vulnerable para ganar el kernel. La defensa
práctica en casa es cruzar los drivers presentes contra las listas
públicas de drivers vulnerables/maliciosos conocidos:

- LOLDrivers (CC0): huellas SHA-256 de muestras confirmadas; la
  lista incluida también recoge los drivers de la lista de bloqueo
  de Microsoft que el proyecto documenta.
- La comprobación es por HUELLA del archivo .sys: fiable, sin
  adivinar por nombres (la API de LOLDrivers no da un nombre de
  archivo fiable por muestra, así que no se finge ese cruce).

Si un driver instalado figura en la lista, la interfaz lo avisa y
la actualización de ese driver pasa a ser prioritaria; un candidato
de actualización solo se puede juzgar cuando su archivo existe en
disco (antes de descargar no hay huella que cruzar, y se dice así).
"""
import os

from .. import config
from .hashing import sha256_archivo

_cache: dict[str, str] | None = None


def _ruta_base() -> str:
    datos = os.path.join(config.carpeta_datos(), "byovd_loldrivers.txt")
    if os.path.isfile(datos):
        return datos
    return os.path.join(config.carpeta_activos(), "byovd_loldrivers.txt")


def cargar_base() -> dict[str, str]:
    """{sha256: categoria} con categoria «vulnerable»|«malicioso»."""
    global _cache
    if _cache is not None:
        return _cache
    base: dict[str, str] = {}
    try:
        with open(_ruta_base(), "r", encoding="utf-8",
                  errors="replace") as fh:
            for linea in fh:
                linea = linea.strip()
                if not linea or linea.startswith("#"):
                    continue
                partes = linea.split("\t")
                sha = partes[0].strip().lower()
                if len(sha) == 64:
                    base[sha] = (partes[1].strip().lower()
                                 if len(partes) > 1 else "vulnerable")
    except OSError:
        pass
    _cache = base
    return base


def total_base() -> int:
    return len(cargar_base())


def revisar_hash(sha256: str) -> str | None:
    """Categoría si la huella figura en la lista; None si no."""
    return cargar_base().get((sha256 or "").strip().lower())


def revisar_archivo(ruta: str) -> str | None:
    """Categoría BYOVD de un .sys por su huella; None si limpio
    o si no se pudo leer."""
    try:
        return revisar_hash(sha256_archivo(ruta))
    except OSError:
        return None


def auditar_archivos(rutas: list[str]) -> list[dict]:
    """Cruza una lista de archivos contra la base.

    Devuelve [{ruta, nombre, categoria}] solo con los que figuran.
    """
    hallazgos: list[dict] = []
    for ruta in rutas:
        categoria = revisar_archivo(ruta)
        if categoria:
            hallazgos.append({
                "ruta": ruta,
                "nombre": os.path.basename(ruta),
                "categoria": categoria,
            })
    return hallazgos
