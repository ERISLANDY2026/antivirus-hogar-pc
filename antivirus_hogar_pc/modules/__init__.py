"""Registro de módulos: descubrimiento automático y declarativo.

Cada carril declara sus módulos en `modules/<paquete>/registro.py` con una
lista REGISTROS de contracts.RegistroModulo. Ese archivo NO importa Qt (la
página se resuelve perezosamente desde la ruta «paquete.modulo:funcion»),
así que el descubrimiento funciona también sin interfaz (tests, CI).

main.py / main_window.py NO se editan al añadir un módulo: basta con que el
paquete exista y declare su registro.
"""
import importlib
import pkgutil

from ..contracts import RegistroModulo


def descubrir_modulos() -> list[RegistroModulo]:
    """Devuelve todos los módulos declarados, ordenados por `orden`."""
    import antivirus_hogar_pc.modules as paquete_modulos

    registros: list[RegistroModulo] = []
    for info in pkgutil.iter_modules(paquete_modulos.__path__):
        if not info.ispkg:
            continue
        try:
            modulo_registro = importlib.import_module(
                f"antivirus_hogar_pc.modules.{info.name}.registro"
            )
        except ModuleNotFoundError:
            continue  # paquete sin registro: no es un módulo de la app
        registros.extend(getattr(modulo_registro, "REGISTROS", []))
    registros.sort(key=lambda r: r.orden)
    ids = [r.id for r in registros]
    if len(ids) != len(set(ids)):
        raise ValueError(f"IDs de módulo duplicados: {ids}")
    return registros


def crear_pagina(registro: RegistroModulo, ctx) -> object:
    """Resuelve la ruta «paquete.modulo:funcion» y crea la página (Qt)."""
    ruta_modulo, _, funcion = registro.pagina.partition(":")
    modulo = importlib.import_module(ruta_modulo)
    return getattr(modulo, funcion)(ctx)
