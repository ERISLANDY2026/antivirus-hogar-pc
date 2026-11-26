"""DIAGNÓSTICO TEMPORAL v1.0.16 (8) — NO forma parte de la suite.

Flujo v105 y serie temporal: cada segundo, processEvents +
gc + conteo de tarjetas. Al final, sendPostedEvents
(DeferredDelete) y nuevo conteo. Se borra al cerrar.
"""
import gc
import os
import time

import pytest

pytest.importorskip("PySide6")


def test_diag_serie_temporal():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from antivirus_hogar_pc.ui import programar_page
    from antivirus_hogar_pc.ui.main_window import VentanaPrincipal
    from antivirus_hogar_pc.ui.services import ServiciosApp

    def conteo():
        gc.collect()
        return len([o for o in gc.get_objects()
                    if isinstance(o, programar_page._TarjetaProgramacion)])

    base = conteo()
    ventana = VentanaPrincipal(ServiciosApp())
    ventana.ir_a("version")
    ventana.ir_a("programar")
    app.processEvents()
    ventana.deleteLater()
    app.processEvents()
    del ventana
    serie = [f"t0(base={base})={conteo()}"]
    for s in range(1, 16):
        time.sleep(1.0)
        app.processEvents()
        serie.append(f"t{s}={conteo()}")
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    serie.append(f"tras sendPostedEvents={conteo()}")
    raise AssertionError(" | ".join(serie))
