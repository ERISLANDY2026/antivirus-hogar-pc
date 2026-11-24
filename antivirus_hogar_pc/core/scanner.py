"""Motor de escaneo por huellas.

Recorre las rutas pedidas, calcula (o reutiliza de la caché) las huellas de
cada archivo y las contrasta con la base de firmas. No borra ni mueve nada:
devuelve hallazgos y la DECISIÓN la toma el usuario, como en Android.
"""
import os
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from .hashing import huellas_archivo
from .scancache import CacheEscaneo
from .signatures import BaseFirmas

# Tipos que tiene sentido hashear en un escaneo rápido (los de riesgo real).
EXTENSIONES_EJECUTABLES = {
    ".exe", ".dll", ".scr", ".com", ".bat", ".cmd", ".ps1", ".vbs", ".js",
    ".jse", ".wsf", ".wsh", ".msi", ".msp", ".cpl", ".ocx", ".sys", ".jar",
    ".hta", ".lnk", ".reg", ".docm", ".xlsm", ".pptm", ".zip", ".rar", ".7z",
}


@dataclass
class Hallazgo:
    ruta: str
    sha256: str
    md5: str
    etiqueta: str
    tamano: int


@dataclass
class ResultadoEscaneo:
    archivos_revisados: int = 0
    archivos_desde_cache: int = 0
    errores: int = 0
    hallazgos: list[Hallazgo] = field(default_factory=list)
    cancelado: bool = False


# progreso(ruta_actual, revisados, total) — total puede ser None si aún no se sabe
Progreso = Callable[[str, int, Optional[int]], None]


def _recolectar(raices: Iterable[str], solo_ejecutables: bool) -> list[str]:
    archivos: list[str] = []
    for raiz in raices:
        if os.path.isfile(raiz):
            archivos.append(raiz)
            continue
        for dirpath, _dirnames, filenames in os.walk(raiz):
            for nombre in filenames:
                if solo_ejecutables:
                    ext = os.path.splitext(nombre)[1].lower()
                    if ext not in EXTENSIONES_EJECUTABLES:
                        continue
                archivos.append(os.path.join(dirpath, nombre))
    return archivos


def escanear(
    raices: Iterable[str],
    base: BaseFirmas,
    cache: CacheEscaneo | None = None,
    solo_ejecutables: bool = True,
    forzar_rehash_en: Iterable[str] = (),
    progreso: Progreso | None = None,
    debe_cancelar: Callable[[], bool] | None = None,
) -> ResultadoEscaneo:
    """Escanea las rutas. `forzar_rehash_en`: prefijos donde no se usa caché
    (p. ej. Descargas), mitigación del tradeoff de la caché."""
    resultado = ResultadoEscaneo()
    archivos = _recolectar(raices, solo_ejecutables)
    total = len(archivos)
    prefijos_forzados = tuple(os.path.normpath(p) for p in forzar_rehash_en)

    for ruta in archivos:
        if debe_cancelar and debe_cancelar():
            resultado.cancelado = True
            break
        try:
            st = os.stat(ruta)
        except OSError:
            resultado.errores += 1
            continue
        tamano, mtime = st.st_size, st.st_mtime
        forzado = any(os.path.normpath(ruta).startswith(p) for p in prefijos_forzados)
        huellas = None
        if cache is not None and not forzado:
            huellas = cache.buscar(ruta, tamano, mtime)
            if huellas:
                resultado.archivos_desde_cache += 1
        if huellas is None:
            try:
                huellas = huellas_archivo(ruta)
            except OSError:
                resultado.errores += 1
                continue
            if cache is not None:
                cache.guardar(ruta, tamano, mtime, huellas[0], huellas[1])
        resultado.archivos_revisados += 1
        etiqueta = base.buscar(sha256=huellas[0], md5=huellas[1])
        if etiqueta:
            resultado.hallazgos.append(
                Hallazgo(ruta=ruta, sha256=huellas[0], md5=huellas[1],
                         etiqueta=etiqueta, tamano=tamano)
            )
        if progreso:
            progreso(ruta, resultado.archivos_revisados, total)
    if cache is not None:
        cache.confirmar()
    return resultado


def analizar_archivo(ruta: str, base: BaseFirmas) -> Hallazgo | None:
    """«Analizar ESTE archivo»: huella directa contra la base local."""
    st = os.stat(ruta)
    sha256, md5 = huellas_archivo(ruta)
    etiqueta = base.buscar(sha256=sha256, md5=md5)
    if not etiqueta:
        return None
    return Hallazgo(ruta=ruta, sha256=sha256, md5=md5, etiqueta=etiqueta,
                    tamano=st.st_size)
