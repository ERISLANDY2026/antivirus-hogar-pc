"""Registro de módulos: declaración EXPLÍCITA de paquetes.

Cada carril declara sus módulos en `modules/<paquete>/registro.py` con una
lista REGISTROS de contracts.RegistroModulo. Ese archivo NO importa Qt (la
página se resuelve perezosamente desde la ruta «paquete.modulo:funcion»),
así que el registro funciona también sin interfaz (tests, CI).

POR QUÉ EXPLÍCITO (bug v1.0.0, corregido en v1.0.1): la v1 descubría los
paquetes con `pkgutil.iter_modules(paquete.__path__)`. En el ejecutable
congelado de PyInstaller los paquetes viven dentro del archivo PYZ y
`__path__` apunta a una carpeta que NO existe en el disco, así que
iter_modules devolvía una lista vacía SIN error: la ventana abría con cero
módulos (solo sobrevivía «Ajustes», cableado a mano en main_window.py).
El import directo por nombre funciona igual en fuente y en congelado,
porque el importador de PyInstaller sí conoce los módulos del PYZ (el
.spec ya los incluye con collect_submodules).

ERRORES VISIBLES: si un paquete falla al importar, el fallo NO se traga:
queda en `errores_descubrimiento()` (la ventana lo enseña en la barra
lateral) y se anexa con su traceback a `errores-modulos.log` en la carpeta
de datos de la app.
"""
import importlib
import os
import traceback

from ..contracts import RegistroModulo

# Paquetes que declaran módulos de navegación (uno por carril).
PAQUETES_MODULOS = ("panel", "security", "system", "net")

_errores_ultimo_descubrimiento: list[str] = []


def errores_descubrimiento() -> list[str]:
    """Errores del último descubrir_modulos() (vacío si todo cargó)."""
    return list(_errores_ultimo_descubrimiento)


def _anotar_error_en_log(ruta: str, detalle: str) -> None:
    """Anexa el error a errores-modulos.log; nunca lanza."""
    try:
        from ..config import carpeta_datos

        destino = os.path.join(carpeta_datos(), "errores-modulos.log")
        with open(destino, "a", encoding="utf-8") as fh:
            fh.write(f"--- {ruta}\n{detalle}\n")
    except Exception:
        pass  # el log es un respaldo; el error ya quedó en memoria y en la UI


def descubrir_modulos(paquetes=None) -> list[RegistroModulo]:
    """Devuelve todos los módulos declarados, ordenados por `orden`.

    `paquetes` permite inyectar la lista de paquetes (tests). Un paquete
    que falla al importar se anota en errores_descubrimiento() y en el log,
    y el resto de módulos sigue cargando.
    """
    global _errores_ultimo_descubrimiento
    _errores_ultimo_descubrimiento = []

    registros: list[RegistroModulo] = []
    for nombre in (paquetes if paquetes is not None else PAQUETES_MODULOS):
        ruta = f"antivirus_hogar_pc.modules.{nombre}.registro"
        try:
            modulo_registro = importlib.import_module(ruta)
        except Exception:
            detalle = traceback.format_exc()
            _errores_ultimo_descubrimiento.append(f"{ruta}: {detalle}")
            _anotar_error_en_log(ruta, detalle)
            continue
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
