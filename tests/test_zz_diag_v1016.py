"""DIAGNÓSTICO TEMPORAL v1.0.16 (5) — NO forma parte de la suite.

¿La conexión de IconoEstado3D a RELOJ.tic enraiza el widget?
Una fila sola: (a) mostrar y ocultar → el icono debe morir al
soltarla; (b) mostrar SIN ocultar (como una ventana que se
cierra sin hide) → si el icono sobrevive al GC, la raíz es la
conexión global. Se borra al cerrar el diagnóstico.
"""
import gc
import os
import weakref

import pytest

pytest.importorskip("PySide6")


def test_diag_icono_raiz():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from antivirus_hogar_pc.ui.iconos_pagina import IconoEstado3D
    from antivirus_hogar_pc.ui.paginas_base import fila_estado

    informe = []

    fila = fila_estado("escudo", "pulso", "Defender", "Activo.")
    icono = fila.findChildren(IconoEstado3D)[0]
    ref = weakref.ref(icono)
    fila.show()
    app.processEvents()
    fila.hide()
    app.processEvents()
    del fila, icono
    gc.collect()
    informe.append(f"mostrar+ocultar: icono vivo={ref() is not None}")

    fila2 = fila_estado("escudo", "pulso", "Defender", "Activo.")
    icono2 = fila2.findChildren(IconoEstado3D)[0]
    ref2 = weakref.ref(icono2)
    fila2.show()
    app.processEvents()
    del fila2, icono2
    gc.collect()
    informe.append(f"mostrar SIN ocultar: icono vivo={ref2() is not None}")

    raise AssertionError(" | ".join(informe))
