"""DIAGNÓSTICO TEMPORAL v1.0.16 (3) — NO forma parte de la suite.

A) Página del Programador sola: weakref a una tarjeta vía el
   ancla real (pagina._tarjetas_programacion); deleteLater y
   ver si el wrapper y el C++ mueren.
B) Ventana completa → ir_a("programar"): weakrefs a la ventana,
   a la página y a una tarjeta; isValid tras processEvents.
Se borra al cerrar el diagnóstico.
"""
import gc
import os
import weakref

import pytest

pytest.importorskip("PySide6")


def test_diag_fuga_tarjetas():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    import shiboken6

    from antivirus_hogar_pc.contracts import ContextoModulo
    from antivirus_hogar_pc.ui import programar_page

    informe = []

    # --- A: página sola ------------------------------------------------------
    pagina = programar_page.crear_pagina_programar(
        ContextoModulo(servicios=None))
    tarjeta_a = pagina._tarjetas_programacion[0]
    ref_ta = weakref.ref(tarjeta_a)
    ref_pa = weakref.ref(pagina)
    del tarjeta_a
    pagina.deleteLater()
    app.processEvents()
    del pagina
    gc.collect()
    informe.append(
        f"A: página wrapper viva={ref_pa() is not None} "
        f"tarjeta viva={ref_ta() is not None}")

    # --- B: ventana ------------------------------------------------------------
    from antivirus_hogar_pc.ui.main_window import VentanaPrincipal
    from antivirus_hogar_pc.ui.services import ServiciosApp

    ventana = VentanaPrincipal(ServiciosApp())
    ventana.ir_a("programar")
    app.processEvents()
    pagina_b = ventana._paginas["programar"]
    tarjeta_b = pagina_b._tarjetas_programacion[0]
    ref_v = weakref.ref(ventana)
    ref_pb = weakref.ref(pagina_b)
    ref_tb = weakref.ref(tarjeta_b)
    del tarjeta_b, pagina_b
    ventana.deleteLater()
    app.processEvents()
    vivo_v = ref_v()
    informe.append(
        f"B: tras deleteLater+processEvents: ventana wrapper viva="
        f"{vivo_v is not None}, C++ válido="
        f"{shiboken6.isValid(vivo_v) if vivo_v is not None else '—'}")
    del ventana
    gc.collect()
    informe.append(
        f"B: tras del+gc: ventana={ref_v() is not None} "
        f"página={ref_pb() is not None} tarjeta={ref_tb() is not None}")
    obj = ref_tb()
    if obj is not None:
        for ref in gc.get_referrers(obj):
            if isinstance(ref, dict):
                claves = [k for k in ref.keys() if isinstance(k, str)][:10]
                s = ref.get("__self__")
                informe.append(
                    f"B: referrer dict claves={claves} "
                    f"__self__={type(s).__name__}")
            elif isinstance(ref, list):
                informe.append(f"B: referrer list len={len(ref)}")
            else:
                informe.append(
                    f"B: referrer {type(ref).__name__}: {repr(ref)[:120]}")

    raise AssertionError("\n".join(informe))
