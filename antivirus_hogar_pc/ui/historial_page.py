"""Página «Historial de la aplicación» (v1.0.18, nota 5).

El historial completo de versiones —desde el desarrollo hasta
hoy, en orden, con lo trabajado en cada una— vive aquí, en su
propia pantalla al final del panel izquierdo. La página
«Versión de la app» enseña SOLO la versión actual; lo que allí
se mezclaba (el historial reciente) se mudó a esta página.

El contenido sale de core/notas_version.py (NOTAS_VERSION).
"""
from PySide6.QtWidgets import QWidget

from ..core.i18n import t
from ..core.notas_version import NOTAS_VERSION
from .paginas_base import etiqueta, pagina_base, tarjeta


def crear_pagina_historial(ctx=None) -> QWidget:
    pagina, layout = pagina_base(
        t("Historial de la aplicación"),
        t("Todas las versiones desde el desarrollo, con lo "
          "trabajado en cada una."))

    for entrada in NOTAS_VERSION:
        tarjeta_v, lay_v = tarjeta(t(
            "Versión {version} — {fecha}",
            version=entrada.get("version", ""),
            fecha=entrada.get("fecha", "")))
        for novedad in entrada.get("novedades", []):
            lay_v.addWidget(etiqueta(f"•  {novedad}", suave=True))
        layout.addWidget(tarjeta_v)

    layout.addStretch(1)
    return pagina
