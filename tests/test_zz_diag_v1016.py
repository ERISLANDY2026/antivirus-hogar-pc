"""DIAGNÓSTICO TEMPORAL v1.0.16 (4) — NO forma parte de la suite.

¿Muere el C++ de la página del Programador con deleteLater?
Se prueba processEvents normal y sendPostedEvents(DeferredDelete)
explícito, con isValid tras cada paso. Se borra al cerrar.
"""
import gc
import os
import weakref

import pytest

pytest.importorskip("PySide6")


def test_diag_fuga_tarjetas():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    import shiboken6

    from antivirus_hogar_pc.contracts import ContextoModulo
    from antivirus_hogar_pc.ui import programar_page

    informe = []
    pagina = programar_page.crear_pagina_programar(
        ContextoModulo(servicios=None))
    ref_p = weakref.ref(pagina)
    informe.append(f"recién creada: válida={shiboken6.isValid(pagina)}")
    pagina.deleteLater()
    app.processEvents()
    informe.append(
        f"tras deleteLater+processEvents: wrapper={ref_p() is not None} "
        f"válida={shiboken6.isValid(pagina)}")
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    informe.append(
        f"tras sendPostedEvents(DeferredDelete): "
        f"wrapper={ref_p() is not None} válida={shiboken6.isValid(pagina)}")
    app.processEvents()
    del pagina
    gc.collect()
    informe.append(f"tras del+gc: wrapper={ref_p() is not None}")

    raise AssertionError("\n".join(informe))
