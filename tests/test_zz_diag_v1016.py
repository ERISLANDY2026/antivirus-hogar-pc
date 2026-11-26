"""DIAGNÓSTICO TEMPORAL v1.0.16 (11) — NO forma parte de la suite.

Secuencia v105→v106 y sondeo cada segundo: ¿cuándo termina el
_TrabajadorInforme de la ventana y cuándo cae el conteo de
tarjetas? Se borra al cerrar el diagnóstico.
"""
import gc
import os
import time

import pytest

pytest.importorskip("PySide6")


def test_diag_vida_trabajador():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from antivirus_hogar_pc.contracts import ContextoModulo
    from antivirus_hogar_pc.modules.panel.page import _TrabajadorInforme
    from antivirus_hogar_pc.ui import programar_page
    from antivirus_hogar_pc.ui.main_window import VentanaPrincipal
    from antivirus_hogar_pc.ui.services import ServiciosApp

    def conteo():
        gc.collect()
        return len([o for o in gc.get_objects()
                    if isinstance(o, programar_page._TarjetaProgramacion)])

    def trabajadores():
        return [o for o in gc.get_objects()
                if isinstance(o, _TrabajadorInforme)]

    ventana = VentanaPrincipal(ServiciosApp())
    ventana.ir_a("version")
    ventana.ir_a("programar")
    app.processEvents()
    ventana.deleteLater()
    app.processEvents()
    del ventana
    pagina = programar_page.crear_pagina_programar(
        ContextoModulo(servicios=None))
    serie = [f"t0: tarjetas={conteo()} trabajadores="
             f"{[(t.isRunning(), t.isFinished()) for t in trabajadores()]}"]
    for s in range(1, 21):
        time.sleep(1.0)
        app.processEvents()
        serie.append(
            f"t{s}: tarjetas={conteo()} trabajadores="
            f"{[(t.isRunning(), t.isFinished()) for t in trabajadores()]}")
    raise AssertionError(" | ".join(serie))
