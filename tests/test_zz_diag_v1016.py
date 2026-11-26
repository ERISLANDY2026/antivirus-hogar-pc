"""DIAGNÓSTICO TEMPORAL v1.0.16 (7) — NO forma parte de la suite.

¿El hilo trabajador del Panel mantiene vivas las tarjetas del
Programador de la ventana? Flujo v105, después se ESPERA a que
el hilo de informe termine y se cuentan las tarjetas en gc.
Se borra al cerrar el diagnóstico.
"""
import gc
import os
import time

import pytest

pytest.importorskip("PySide6")


def test_diag_hilo_panel():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from antivirus_hogar_pc.ui import programar_page
    from antivirus_hogar_pc.ui.main_window import VentanaPrincipal
    from antivirus_hogar_pc.ui.services import ServiciosApp

    ventana = VentanaPrincipal(ServiciosApp())
    ventana.ir_a("version")
    ventana.ir_a("programar")
    app.processEvents()
    panel = ventana._paginas["panel"]
    hilo = getattr(panel, "_hilo_informe", None)
    informe = [f"hilo del panel presente: {hilo is not None}"]
    ventana.deleteLater()
    app.processEvents()
    del ventana, panel
    gc.collect()
    vivas = [o for o in gc.get_objects()
             if isinstance(o, programar_page._TarjetaProgramacion)]
    informe.append(f"sin esperar al hilo: tarjetas vivas={len(vivas)}")
    if hilo is not None:
        t0 = time.time()
        hilo.wait(60000)
        informe.append(
            f"hilo terminado tras {time.time() - t0:.1f} s "
            f"(finished={hilo.isFinished()})")
        app.processEvents()
        gc.collect()
        vivas = [o for o in gc.get_objects()
                 if isinstance(o, programar_page._TarjetaProgramacion)]
        informe.append(f"tras terminar el hilo: tarjetas vivas={len(vivas)}")
    raise AssertionError(" | ".join(informe))
