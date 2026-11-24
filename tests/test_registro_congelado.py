"""Regresión del bug v1.0.0: la app congelada abría SIN módulos.

Causa raíz probada: en el ejecutable de PyInstaller, los paquetes viven en
el PYZ y `modules.__path__` apunta a una carpeta que no existe en el disco;
`pkgutil.iter_modules()` sobre esa ruta devuelve [] SIN error, y la v1
descubría los módulos así → 0 módulos, solo «Ajustes» (cableado a mano).

Estos tests simulan ese entorno: con iter_modules devolviendo vacío (lo
que hace en el .exe), el descubrimiento debe seguir encontrando los 9
módulos, porque desde v1.0.1 el registro es explícito por nombre.
"""
import pkgutil

from antivirus_hogar_pc import modules as paquete_modules
from antivirus_hogar_pc.modules import descubrir_modulos, errores_descubrimiento

IDS_ESPERADOS = {
    "panel", "escaner", "proteccion", "drivers", "limpieza",
    "discos", "actualizaciones", "red", "informes",
}


def test_descubrimiento_funciona_con_iter_modules_vacio(monkeypatch):
    """Simula el congelado: pkgutil no ve ningún paquete en el disco."""
    monkeypatch.setattr(pkgutil, "iter_modules", lambda *a, **k: iter([]))
    registros = descubrir_modulos()
    assert {r.id for r in registros} == IDS_ESPERADOS
    assert len(registros) == 9
    assert errores_descubrimiento() == []


def test_descubrimiento_no_depende_del_path_en_disco(monkeypatch):
    """Ni siquiera con un __path__ roto (carpeta inexistente, como el PYZ)."""
    monkeypatch.setattr(
        paquete_modules, "__path__", ["/ruta/que/no/existe/en/el/disco"]
    )
    registros = descubrir_modulos()
    assert len(registros) == 9


def test_un_paquete_roto_no_desaparece_en_silencio(monkeypatch):
    """Un fallo al importar un registro queda anotado, no tragado."""
    anotados = []
    monkeypatch.setattr(
        paquete_modules, "_anotar_error_en_log",
        lambda ruta, detalle: anotados.append(ruta),
    )
    registros = descubrir_modulos(paquetes=["panel", "paquete_fantasma_xyz"])
    # El paquete sano sigue cargando…
    assert [r.id for r in registros] == ["panel"]
    # …y el roto queda registrado como error, en memoria y en el log.
    errores = errores_descubrimiento()
    assert len(errores) == 1
    assert "paquete_fantasma_xyz" in errores[0]
    assert anotados and "paquete_fantasma_xyz" in anotados[0]
