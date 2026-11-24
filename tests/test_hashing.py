"""Huellas (core.hashing): vectores conocidos SHA-256/MD5 y utilidades."""
import hashlib

from antivirus_hogar_pc.core.hashing import (
    es_ruta_legible,
    huellas_archivo,
    sha256_archivo,
    sha256_datos,
    tamano_legible,
)

SHA256_VACIO = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
MD5_VACIO = "d41d8cd98f00b204e9800998ecf8427e"
SHA256_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
MD5_ABC = "900150983cd24fb0d6963f7d28e17f72"


def test_huellas_archivo_vacio(tmp_path):
    ruta = tmp_path / "vacio.bin"
    ruta.write_bytes(b"")
    assert huellas_archivo(str(ruta)) == (SHA256_VACIO, MD5_VACIO)


def test_huellas_archivo_abc(tmp_path):
    ruta = tmp_path / "abc.bin"
    ruta.write_bytes(b"abc")
    assert huellas_archivo(str(ruta)) == (SHA256_ABC, MD5_ABC)


def test_huellas_archivo_grande_por_bloques(tmp_path):
    # 2,5 MiB: fuerza varias vueltas del bucle de lectura por bloques (1 MiB).
    datos = bytes(range(256)) * 10240
    ruta = tmp_path / "grande.bin"
    ruta.write_bytes(datos)
    esperado = (hashlib.sha256(datos).hexdigest(), hashlib.md5(datos).hexdigest())
    assert huellas_archivo(str(ruta)) == esperado


def test_sha256_archivo_y_datos():
    assert sha256_datos(b"abc") == SHA256_ABC
    assert sha256_datos(b"") == SHA256_VACIO


def test_sha256_archivo_coincide_con_datos(tmp_path):
    ruta = tmp_path / "x.bin"
    ruta.write_bytes(b"contenido de prueba")
    assert sha256_archivo(str(ruta)) == sha256_datos(b"contenido de prueba")


def test_tamano_legible():
    assert tamano_legible(0) == "0 B"
    assert tamano_legible(512) == "512 B"
    assert tamano_legible(1024) == "1.0 KB"
    assert tamano_legible(1536) == "1.5 KB"
    assert tamano_legible(5 * 1024 * 1024) == "5.0 MB"
    assert tamano_legible(2 * 1024**3) == "2.0 GB"


def test_es_ruta_legible(tmp_path):
    ruta = tmp_path / "ok.bin"
    ruta.write_bytes(b"x")
    assert es_ruta_legible(str(ruta)) is True
    assert es_ruta_legible(str(tmp_path / "no_existe.bin")) is False
    assert es_ruta_legible(str(tmp_path)) is False  # una carpeta no es archivo
