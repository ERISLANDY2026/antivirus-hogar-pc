"""DIAGNÓSTICO TEMPORAL v1.0.16 (2) — NO forma parte de la suite.

Sigue UNA tarjeta concreta de cada flujo con weakref:
A) página del Programador creada y destruida sola;
B) ventana completa → ir_a("programar") → deleteLater.
Reporta isValid (C++ vivo?) y los referrers de ESA tarjeta.
Se borra al cerrar el diagnóstico.
"""
import gc
import os
import weakref

import pytest

pytest.importorskip("PySide6")


def _referrers(obj, limite=14):
    lineas = []
    for ref in gc.get_referrers(obj):
        if isinstance(ref, dict):
            claves = [k for k in ref.keys() if isinstance(k, str)][:10]
            selfref = ref.get("__self__")
            extra = f" __self__={type(selfref).__name__}" if selfref else ""
            lineas.append(f"dict claves={claves}{extra}")
        elif isinstance(ref, list):
            lineas.append(f"list len={len(ref)}")
        else:
            lineas.append(f"{type(ref).__name__}: {repr(ref)[:120]}")
        if len(lineas) >= limite:
            break
    return lineas


def test_diag_fuga_tarjetas():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    import shiboken6

    from antivirus_hogar_pc.contracts import ContextoModulo
    from antivirus_hogar_pc.ui import programar_page

    informe = []

    # --- Flujo A: la página sola -------------------------------------------
    pagina = programar_page.crear_pagina_programar(
        ContextoModulo(servicios=None))
    tarjetas = pagina.findChildren(programar_page._TarjetaProgramacion)
    informe.append(f"A: tarjetas en la página = {len(tarjetas)}")
    ref_a = weakref.ref(tarjetas[0])
    pagina.deleteLater()
    app.processEvents()
    del pagina, tarjetas
    gc.collect()
    obj_a = ref_a()
    informe.append(
        f"A: tras destruir, wrapper vivo = {obj_a is not None}, "
        f"C++ válido = {shiboken6.isValid(obj_a) if obj_a is not None else '—'}")
    if obj_a is not None:
        informe.append("A: referrers:\n  " + "\n  ".join(_referrers(obj_a)))

    # --- Flujo B: la ventana ------------------------------------------------
    from antivirus_hogar_pc.ui.main_window import VentanaPrincipal
    from antivirus_hogar_pc.ui.services import ServiciosApp

    ventana = VentanaPrincipal(ServiciosApp())
    ventana.ir_a("programar")
    app.processEvents()
    pagina_b = ventana._paginas["programar"]
    tarjetas_b = pagina_b.findChildren(programar_page._TarjetaProgramacion)
    informe.append(f"B: tarjetas en la ventana = {len(tarjetas_b)}")
    ref_b = weakref.ref(tarjetas_b[0])
    ventana.deleteLater()
    app.processEvents()
    del ventana, pagina_b, tarjetas_b
    gc.collect()
    obj_b = ref_b()
    informe.append(
        f"B: tras destruir, wrapper vivo = {obj_b is not None}, "
        f"C++ válido = {shiboken6.isValid(obj_b) if obj_b is not None else '—'}")
    if obj_b is not None:
        informe.append("B: referrers:\n  " + "\n  ".join(_referrers(obj_b)))

    raise AssertionError("\n".join(informe))
