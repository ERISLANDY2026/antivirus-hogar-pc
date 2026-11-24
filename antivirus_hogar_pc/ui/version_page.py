"""Página «Versión de la app» (v1.0.5): versión actual, qué lleva,
qué tiene y qué hace la aplicación, e historial reciente.

El contenido sale de core/notas_version.py: futuras versiones solo
añaden su entrada a NOTAS_VERSION y esta pantalla se actualiza sola.
"""
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .. import config
from ..core.notas_version import NOTAS_VERSION, QUE_HACE, RESUMEN_APP, notas_de
from .paginas_base import etiqueta, pagina_base, tarjeta


def crear_pagina_version(ctx=None) -> QWidget:
    pagina, layout = pagina_base(
        "Versión de la app",
        "La versión instalada, sus novedades y el historial reciente.")

    # --- Versión actual y sus novedades -----------------------------------
    actual = notas_de(config.VERSION)
    tarjeta_a, lay_a = tarjeta(f"Versión actual: {config.VERSION}")
    fecha = actual.get("fecha") if actual else ""
    lay_a.addWidget(etiqueta(
        f"Estás en la versión {config.VERSION}"
        + (f" (publicada el {fecha})." if fecha else "."),
        suave=True))
    if actual:
        lay_a.addWidget(etiqueta("Qué lleva esta versión:"))
        for novedad in actual.get("novedades", []):
            lay_a.addWidget(etiqueta(f"•  {novedad}", suave=True))
    else:
        lay_a.addWidget(etiqueta(
            "Esta versión aún no tiene notas cargadas.", suave=True))
    layout.addWidget(tarjeta_a)

    # --- Qué tiene y qué hace ----------------------------------------------
    tarjeta_b, lay_b = tarjeta("Qué tiene y qué hace esta app")
    lay_b.addWidget(etiqueta(RESUMEN_APP, suave=True))
    for linea in QUE_HACE:
        lay_b.addWidget(etiqueta(f"•  {linea}", suave=True))
    layout.addWidget(tarjeta_b)

    # --- Historial reciente ---------------------------------------------------
    historial = [n for n in NOTAS_VERSION
                 if n.get("version") != config.VERSION]
    if historial:
        tarjeta_c, lay_c = tarjeta("Historial reciente")
        for entrada in historial:
            lay_c.addWidget(etiqueta(
                f"Versión {entrada.get('version', '')} — "
                f"{entrada.get('fecha', '')}"))
            for novedad in entrada.get("novedades", []):
                lay_c.addWidget(etiqueta(f"•  {novedad}", suave=True))
        layout.addWidget(tarjeta_c)

    layout.addStretch(1)
    return pagina
