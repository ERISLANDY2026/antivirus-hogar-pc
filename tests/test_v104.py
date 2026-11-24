"""v1.0.4 — Regresión del fallo real del usuario (foto 2026-11-24):

«El escaneo no se pudo completar: SQLite objects created in a thread
can only be used in that same thread. The object was created in thread
id 5944 and this is thread id 8588.»

La caché de escaneo (SQLite) se crea en el hilo principal (ServiciosApp)
y el escaneo la usa dentro del hilo trabajador (QThread de la página).
Estos tests reproducen ESE cruce de hilos sin Qt: los objetos se crean
en el hilo principal del test y el escaneo corre en un hilo distinto.
"""
import sqlite3
import threading

from antivirus_hogar_pc.core.hashing import huellas_archivo
from antivirus_hogar_pc.core.scancache import CacheEscaneo
from antivirus_hogar_pc.core.scanner import escanear
from antivirus_hogar_pc.core.signatures import BaseFirmas
from antivirus_hogar_pc.core.textos_error import mensaje_para_usuario


def _carpeta_con_ejecutables(tmp_path):
    carpeta = tmp_path / "descargas"
    carpeta.mkdir()
    bueno = carpeta / "bueno.exe"
    bueno.write_bytes(b"MZ bueno " * 64)
    malo = carpeta / "malo.exe"
    malo.write_bytes(b"MZ malo conocido " * 64)
    texto = carpeta / "notas.txt"
    texto.write_text("no ejecutable")
    return carpeta, bueno, malo


def _base_con_malo(malo):
    base = BaseFirmas()
    sha256, md5 = huellas_archivo(str(malo))
    base.sha256[sha256] = "Malware conocido (test)"
    return base


def _escanear_en_otro_hilo(raices, base, cache):
    """Ejecuta escanear() en un hilo NUEVO, como hace la UI con QThread.
    Devuelve (resultado, excepcion) — la excepción NO se traga aquí."""
    caja = {}

    def trabajo():
        try:
            caja["resultado"] = escanear(
                raices, base, cache=cache, solo_ejecutables=True)
        except Exception as exc:  # se captura para afirmarla fuera
            caja["excepcion"] = exc

    hilo = threading.Thread(target=trabajo, name="trabajador-escaneo-test")
    hilo.start()
    hilo.join(timeout=60)
    assert not hilo.is_alive(), "el escaneo en otro hilo no terminó"
    return caja.get("resultado"), caja.get("excepcion")


def test_escaneo_desde_otro_hilo_completa_con_cache_creada_en_principal(tmp_path):
    carpeta, bueno, malo = _carpeta_con_ejecutables(tmp_path)
    base = _base_con_malo(malo)
    # La caché nace en el hilo principal, igual que ServiciosApp.
    cache = CacheEscaneo(str(tmp_path / "cache.sqlite3"))
    try:
        resultado, excepcion = _escanear_en_otro_hilo(
            [str(carpeta)], base, cache)
        # LA regresión: antes esto era sqlite3.ProgrammingError.
        assert excepcion is None, f"el escaneo lanzó: {excepcion!r}"
        assert resultado is not None
        assert resultado.error == ""
        assert resultado.archivos_revisados == 2  # solo ejecutables
        assert [h.ruta for h in resultado.hallazgos] == [str(malo)]
        # La caché quedó escrita por el hilo trabajador…
        assert cache.total() == 2
        # …y un SEGUNDO escaneo, en un tercer hilo, la reutiliza.
        resultado2, excepcion2 = _escanear_en_otro_hilo(
            [str(carpeta)], base, cache)
        assert excepcion2 is None
        assert resultado2.archivos_desde_cache == 2
        assert [h.ruta for h in resultado2.hallazgos] == [str(malo)]
    finally:
        cache.cerrar()


def test_cache_uso_cruzado_directo_entre_hilos(tmp_path):
    cache = CacheEscaneo(str(tmp_path / "cache.sqlite3"))
    try:
        caja = {}

        def trabajo():
            cache.guardar("/x/a.exe", 10, 1.5, "a" * 64, "b" * 32)
            cache.confirmar()
            caja["buscado"] = cache.buscar("/x/a.exe", 10, 1.5)

        hilo = threading.Thread(target=trabajo)
        hilo.start()
        hilo.join(timeout=30)
        assert caja["buscado"] == ("a" * 64, "b" * 32)
        assert cache.buscar("/x/a.exe", 10, 1.5) == ("a" * 64, "b" * 32)
        assert cache.total() == 1
    finally:
        cache.cerrar()


def test_mensaje_sqlite_hilos_es_espanol_claro_sin_ingles_tecnico():
    exc = sqlite3.ProgrammingError(
        "SQLite objects created in a thread can only be used in that "
        "same thread. The object was created in thread id 5944 and "
        "this is thread id 8588.")
    mensaje = mensaje_para_usuario(exc)
    assert "SQLite objects" not in mensaje
    assert "thread" not in mensaje
    assert "base de datos interna" in mensaje


def test_mensaje_sqlite_generico_tambien_mapeado():
    mensaje = mensaje_para_usuario(sqlite3.OperationalError("database is locked"))
    assert "database is locked" not in mensaje
    assert "base de datos interna" in mensaje
