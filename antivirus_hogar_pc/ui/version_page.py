"""Página «Versión de la app» (v1.0.5): versión actual, qué lleva,
qué tiene y qué hace la aplicación, e historial reciente.

El contenido sale de core/notas_version.py: futuras versiones solo
añaden su entrada a NOTAS_VERSION y esta pantalla se actualiza sola.
"""
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .. import config
from ..core.i18n import t
from ..core.notas_version import NOTAS_VERSION, QUE_HACE, RESUMEN_APP, notas_de
from .paginas_base import etiqueta, pagina_base, tarjeta


def crear_pagina_version(ctx=None) -> QWidget:
    pagina, layout = pagina_base(
        t("Versión de la app"),
        t("La versión instalada, sus novedades y el historial reciente."))

    # --- Versión actual y sus novedades -----------------------------------
    actual = notas_de(config.VERSION)
    tarjeta_a, lay_a = tarjeta(t("Versión actual: {version}", version=config.VERSION))
    fecha = actual.get("fecha") if actual else ""
    lay_a.addWidget(etiqueta(
        t("Estás en la versión {version} (publicada el {fecha}).",
          version=config.VERSION, fecha=fecha) if fecha else
        t("Estás en la versión {version}.", version=config.VERSION),
        suave=True))
    if actual:
        lay_a.addWidget(etiqueta(t("Qué lleva esta versión:")))
        for novedad in actual.get("novedades", []):
            lay_a.addWidget(etiqueta(f"•  {novedad}", suave=True))
    else:
        lay_a.addWidget(etiqueta(
            t("Esta versión aún no tiene notas cargadas."), suave=True))
    layout.addWidget(tarjeta_a)

    # --- Qué tiene y qué hace ----------------------------------------------
    tarjeta_b, lay_b = tarjeta(t("Qué tiene y qué hace esta app"))
    lay_b.addWidget(etiqueta(t(RESUMEN_APP), suave=True))
    for linea in QUE_HACE:
        lay_b.addWidget(etiqueta(f"•  {t(linea)}", suave=True))
    layout.addWidget(tarjeta_b)

    # --- Historial reciente ---------------------------------------------------
    historial = [n for n in NOTAS_VERSION
                 if n.get("version") != config.VERSION]
    if historial:
        tarjeta_c, lay_c = tarjeta(t("Historial reciente"))
        for entrada in historial:
            lay_c.addWidget(etiqueta(t(
                "Versión {version} — {fecha}",
                version=entrada.get('version', ''),
                fecha=entrada.get('fecha', ''))))
            for novedad in entrada.get("novedades", []):
                lay_c.addWidget(etiqueta(f"•  {novedad}", suave=True))
        layout.addWidget(tarjeta_c)

    layout.addStretch(1)
    return pagina
