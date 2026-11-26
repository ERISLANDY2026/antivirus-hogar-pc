"""Página «Versión de la app»: SOLO la versión actual (v1.0.18,
nota 5) — número, de qué se trata y qué trae de nuevo
(capacidades). El historial completo de versiones vive en su
propia pantalla, «Historial de la aplicación» (historial_page),
al final del panel izquierdo.

El contenido sale de core/notas_version.py: futuras versiones
solo añaden su entrada a NOTAS_VERSION y esta pantalla se
actualiza sola.
"""
from PySide6.QtWidgets import QWidget

from .. import config
from ..core.i18n import t
from ..core.notas_version import QUE_HACE, RESUMEN_APP, notas_de
from .paginas_base import etiqueta, pagina_base, tarjeta


def crear_pagina_version(ctx=None) -> QWidget:
    pagina, layout = pagina_base(
        t("Versión de la app"),
        t("La versión instalada y lo que trae de nuevo."))

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
        lay_a.addWidget(etiqueta(t("Qué trae de nuevo:")))
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

    layout.addStretch(1)
    return pagina
