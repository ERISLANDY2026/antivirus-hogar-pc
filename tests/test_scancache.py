"""Caché incremental (core.scancache) y su uso por el escáner (core.scanner).

La clave de la caché es (ruta, tamaño, mtime): si el archivo no cambió en
tamaño ni en fecha, se reutilizan las huellas sin releerlo. Tradeoff
declarado en el módulo: contenido cambiado con el MISMO tamaño y la MISMA
fecha escaparía a la caché; los tests fijan ese comportamiento tal cual
está contratado, y la mitigación (forzar_rehash_en) en el escáner.
"""
import os

import pytest

from antivirus_hogar_pc.core.scancache import CacheEscaneo
from antivirus_hogar_pc.core.scanner import analizar_archivo, escanear
from antivirus_hogar_pc.core.signatures import BaseFirmas


@pytest.fixture()
def cache(tmp_path):
    c = CacheEscaneo(str(tmp_path / "subdir" / "cache.sqlite3"))
    yield c
    c.cerrar()


def test_cache_empieza_vacia(cache):
    assert cache.total() == 0
    assert cache.buscar("/x/y.exe", 10, 1.0) is None


def test_cache_guardar_y_buscar(cache):
    cache.guardar("/x/y.exe", 10, 1.5, "a" * 64, "b" * 32)
    cache.confirmar()
    assert cache.buscar("/x/y.exe", 10, 1.5) == ("a" * 64, "b" * 32)
    assert cache.total() == 1


def test_cache_clave_exacta_tamano_y_mtime(cache):
    cache.guardar("/x/y.exe", 10, 1.5, "a" * 64, "b" * 32)
    cache.confirmar()
    assert cache.buscar("/x/y.exe", 11, 1.5) is None   # tamaño distinto
    assert cache.buscar("/x/y.exe", 10, 2.5) is None   # mtime distinta
    assert cache.buscar("/x/z.exe", 10, 1.5) is None   # ruta distinta


def test_cache_reemplaza_la_entrada_de_la_misma_ruta(cache):
    cache.guardar("/x/y.exe", 10, 1.5, "a" * 64, "b" * 32)
    cache.guardar("/x/y.exe", 20, 3.5, "c" * 64, "d" * 32)
    cache.confirmar()
    assert cache.total() == 1
    assert cache.buscar("/x/y.exe", 20, 3.5) == ("c" * 64, "d" * 32)
    assert cache.buscar("/x/y.exe", 10, 1.5) is None


def test_cache_persiste_entre_instancias(tmp_path):
    ruta = str(tmp_path / "cache.sqlite3")
    c1 = CacheEscaneo(ruta)
    c1.guardar("/x/y.exe", 10, 1.5, "a" * 64, "b" * 32)
    c1.cerrar()
    c2 = CacheEscaneo(ruta)
    try:
        assert c2.buscar("/x/y.exe", 10, 1.5) == ("a" * 64, "b" * 32)
    finally:
        c2.cerrar()


# --- Integración con el escáner ----------------------------------------------

@pytest.fixture()
def carpeta_con_malo(tmp_path):
    """Carpeta con un .exe «malo» (su huella está en la base) y uno limpio."""
    malo = tmp_path / "malo.exe"
    malo.write_bytes(b"contenido-malo")
    limpio = tmp_path / "limpio.exe"
    limpio.write_bytes(b"contenido-limpio")
    nota = tmp_path / "nota.txt"
    nota.write_bytes(b"contenido-malo")  # misma huella, pero no ejecutable
    from antivirus_hogar_pc.core.hashing import huellas_archivo

    sha, md5 = huellas_archivo(str(malo))
    base = BaseFirmas()
    base.sha256[sha] = "Malware de prueba"
    base.md5[md5] = "Malware de prueba"
    return tmp_path, base


def test_escaner_detecta_y_usa_cache_la_segunda_vez(carpeta_con_malo, tmp_path):
    carpeta, base = carpeta_con_malo
    cache = CacheEscaneo(str(tmp_path / "c.sqlite3"))
    try:
        r1 = escanear([str(carpeta)], base, cache=cache)
        assert r1.archivos_revisados == 2          # solo .exe, la .txt no
        assert r1.archivos_desde_cache == 0
        assert [h.etiqueta for h in r1.hallazgos] == ["Malware de prueba"]

        r2 = escanear([str(carpeta)], base, cache=cache)
        assert r2.archivos_revisados == 2
        assert r2.archivos_desde_cache == 2        # todo sale de la caché
        assert len(r2.hallazgos) == 1
    finally:
        cache.cerrar()


def test_escaner_forzar_rehash_ignora_la_cache(carpeta_con_malo, tmp_path):
    carpeta, base = carpeta_con_malo
    cache = CacheEscaneo(str(tmp_path / "c.sqlite3"))
    try:
        escanear([str(carpeta)], base, cache=cache)
        r = escanear([str(carpeta)], base, cache=cache,
                     forzar_rehash_en=[str(carpeta)])
        assert r.archivos_desde_cache == 0
        assert len(r.hallazgos) == 1
    finally:
        cache.cerrar()


def test_escaner_rehashea_si_cambia_el_mtime(carpeta_con_malo, tmp_path):
    carpeta, base = carpeta_con_malo
    cache = CacheEscaneo(str(tmp_path / "c.sqlite3"))
    try:
        escanear([str(carpeta)], base, cache=cache)
        limpio = carpeta / "limpio.exe"
        st = os.stat(limpio)
        os.utime(limpio, (st.st_atime, st.st_mtime + 5))
        r = escanear([str(carpeta)], base, cache=cache)
        assert r.archivos_desde_cache == 1  # solo el .exe sin tocar
    finally:
        cache.cerrar()


def test_analizar_archivo_directo(carpeta_con_malo):
    carpeta, base = carpeta_con_malo
    hallazgo = analizar_archivo(str(carpeta / "malo.exe"), base)
    assert hallazgo is not None
    assert hallazgo.etiqueta == "Malware de prueba"
    assert analizar_archivo(str(carpeta / "limpio.exe"), base) is None
