"""Cálculo de huellas (SHA-256 y MD5) de archivos, por bloques."""
import hashlib
import os

_BLOQUE = 1024 * 1024


def huellas_archivo(ruta: str) -> tuple[str, str]:
    """Devuelve (sha256, md5) en minúsculas del archivo indicado."""
    h256 = hashlib.sha256()
    hmd5 = hashlib.md5()
    with open(ruta, "rb") as f:
        while True:
            bloque = f.read(_BLOQUE)
            if not bloque:
                break
            h256.update(bloque)
            hmd5.update(bloque)
    return h256.hexdigest(), hmd5.hexdigest()


def sha256_archivo(ruta: str) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        while True:
            bloque = f.read(_BLOQUE)
            if not bloque:
                break
            h.update(bloque)
    return h.hexdigest()


def sha256_datos(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def tamano_legible(n: float) -> str:
    """Formatea un tamaño en bytes para personas (KB, MB, GB…)."""
    unidades = ["B", "KB", "MB", "GB", "TB"]
    valor = float(n)
    for unidad in unidades:
        if valor < 1024 or unidad == unidades[-1]:
            if unidad == "B":
                return f"{int(valor)} B"
            return f"{valor:.1f} {unidad}"
        valor /= 1024
    return f"{valor:.1f} TB"


def es_ruta_legible(ruta: str) -> bool:
    return os.path.isfile(ruta) and os.access(ruta, os.R_OK)
