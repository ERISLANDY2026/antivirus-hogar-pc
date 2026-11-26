"""DIAGNÓSTICO TEMPORAL v1.0.16 (9) — NO forma parte de la suite.

Flujo v105; cada 3 s: tarjetas vivas, QThreads del proceso
(isRunning) y validez C++ de la ventana. Al final,
sendPostedEvents(DeferredDelete) y nueva foto. Se borra.
"""
import gc
import os
import time

import pytest

pytest.importorskip("PySide6")


def test_diag_hilos_y_validez():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication, QEvent, QThread
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    import shiboken6

    from antivirus_hogar_pc.ui import programar_page
    from antivirus_hogar_pc.ui.main_window import VentanaPrincipal
    from antivirus_hogar_pc.ui.services import ServiciosApp

    def foto():
        gc.collect()
        tarjetas = len([o for o in gc.get_objects()
                        if isinstance(o, programar_page._TarjetaProgramacion)])
        hilos = [o for o in gc.get_objects() if isinstance(o, QThread)]
        corriendo = sum(1 for h in hilos if h.isRunning())
        return tarjetas, len(hilos), corriendo

    ventana = VentanaPrincipal(ServiciosApp())
    ventana.ir_a("programar")
    app.processEvents()
    ref_v = ventana
    ventana.deleteLater()
    app.processEvents()
    del ventana
    serie = []
    for s in range(0, 31, 3):
        if s:
            time.sleep(3.0)
            app.processEvents()
        t, h, c = foto()
        serie.append(
            f"t{s}: tarjetas={t} hilos={h} corriendo={c} "
            f"ventanaC++={shiboken6.isValid(ref_v)}")
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    t, h, c = foto()
    serie.append(
        f"tras sendPostedEvents: tarjetas={t} hilos={h} corriendo={c} "
        f"ventanaC++={shiboken6.isValid(ref_v)}")
    raise AssertionError(" | ".join(serie))
