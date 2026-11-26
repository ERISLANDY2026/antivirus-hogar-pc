"""DIAGNÓSTICO TEMPORAL v1.0.16 (10) — NO forma parte de la suite.

Flujo v105 → zombi; volcado de referrers de la página del
Programador y de la del Panel, con el dueño de cada dict, para
ver la raíz ajena al árbol. Se borra al cerrar el diagnóstico.
"""
import gc
import os
import weakref

import pytest

pytest.importorskip("PySide6")


def _dueno(d):
    for ref in gc.get_referrers(d):
        if getattr(ref, "__dict__", None) is d:
            nombre = getattr(ref, "__name__", None)
            return f"{type(ref).__name__}({nombre or repr(ref)[:50]})"
    return "?"


def _dump(obj, nombre, informe):
    informe.append(f"--- referrers de {nombre}:")
    for ref in gc.get_referrers(obj):
        if isinstance(ref, dict):
            claves = [k for k in ref.keys() if isinstance(k, str)][:12]
            informe.append(f"  dict dueño={_dueno(ref)} claves={claves}")
        elif isinstance(ref, list):
            informe.append(f"  list len={len(ref)}")
        elif isinstance(ref, tuple):
            informe.append(f"  tuple len={len(ref)}")
        else:
            informe.append(f"  {type(ref).__name__}: {repr(ref)[:90]}")


def test_diag_referrers_paginas():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from antivirus_hogar_pc.ui.main_window import VentanaPrincipal
    from antivirus_hogar_pc.ui.services import ServiciosApp

    ventana = VentanaPrincipal(ServiciosApp())
    ventana.ir_a("version")
    ventana.ir_a("programar")
    app.processEvents()
    pagina_prog = ventana._paginas["programar"]
    pagina_panel = ventana._paginas["panel"]
    ventana.deleteLater()
    app.processEvents()
    informe = []
    _dump(pagina_prog, "PÁGINA PROGRAMAR", informe)
    _dump(pagina_panel, "PÁGINA PANEL", informe)
    raise AssertionError("\n".join(informe))
