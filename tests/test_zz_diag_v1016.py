"""DIAGNÓSTICO TEMPORAL v1.0.16 — NO forma parte de la suite.

Reproduce el flujo de test_v105 (ventana → ir_a("programar") →
deleteLater → processEvents → gc) y, si queda alguna
_TarjetaProgramacion viva, vuelca sus referrers de gc para
encontrar qué raíz la mantiene viva. Se borra al cerrar el
diagnóstico.
"""
import gc
import os

import pytest

pytest.importorskip("PySide6")


def test_diag_fuga_tarjetas():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from antivirus_hogar_pc.ui import programar_page
    from antivirus_hogar_pc.ui.main_window import VentanaPrincipal
    from antivirus_hogar_pc.ui.services import ServiciosApp

    ventana = VentanaPrincipal(ServiciosApp())
    ventana.ir_a("programar")
    app.processEvents()
    ventana.deleteLater()
    app.processEvents()
    del ventana
    gc.collect()
    vivas = [o for o in gc.get_objects()
             if isinstance(o, programar_page._TarjetaProgramacion)]
    if vivas:
        lineas = []
        for ref in gc.get_referrers(vivas[0]):
            if isinstance(ref, dict):
                claves = [k for k in ref.keys() if isinstance(k, str)][:12]
                duenos = ref.get("__self__", "")
                lineas.append(
                    f"dict claves={claves} __self__={type(duenos).__name__}")
            else:
                lineas.append(f"{type(ref).__name__}: {repr(ref)[:160]}")
        raise AssertionError(
            f"quedan {len(vivas)} tarjetas vivas; referrers de la 1ª:\n"
            + "\n".join(lineas))
