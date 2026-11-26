"""DIAGNÓSTICO TEMPORAL v1.0.16 (6) — NO forma parte de la suite.

Flujo exacto del test_v105 (ventana → version → programar →
deleteLater → processEvents) y volcado de referrers de la
ventana para encontrar la raíz ajena al árbol que la mantiene
viva. Se borra al cerrar el diagnóstico.
"""
import gc
import os

import pytest

pytest.importorskip("PySide6")


def _dueno_dict(d):
    """¿De quién es este dict? Busca el objeto cuyo __dict__ es d."""
    for ref in gc.get_referrers(d):
        if getattr(ref, "__dict__", None) is d:
            return f"{type(ref).__name__}({repr(ref)[:60]})"
    return "?"


def _dump(obj, nombre, informe, excluir_ids):
    informe.append(f"--- referrers de {nombre}:")
    for ref in gc.get_referrers(obj):
        if id(ref) in excluir_ids:
            continue
        if isinstance(ref, dict):
            claves = [k for k in ref.keys() if isinstance(k, str)][:14]
            informe.append(
                f"  dict dueño={_dueno_dict(ref)} claves={claves}")
        elif isinstance(ref, list):
            informe.append(f"  list len={len(ref)}")
        elif isinstance(ref, tuple):
            informe.append(f"  tuple len={len(ref)}")
        else:
            informe.append(f"  {type(ref).__name__}: {repr(ref)[:100]}")


def test_diag_raiz_ventana():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    import shiboken6

    from antivirus_hogar_pc.ui.main_window import VentanaPrincipal
    from antivirus_hogar_pc.ui.services import ServiciosApp

    servicios = ServiciosApp()
    ventana = VentanaPrincipal(servicios)
    ventana.ir_a("version")
    ventana.ir_a("programar")
    app.processEvents()
    pagina_prog = ventana._paginas["programar"]
    tarjeta = pagina_prog._tarjetas_programacion[0]
    ventana.deleteLater()
    app.processEvents()

    informe = [f"C++ ventana válido tras deleteLater: "
               f"{shiboken6.isValid(ventana)}"]
    # Excluir los dicts de este propio frame (locals de la prueba).
    excluir = {id(locals())}
    _dump(ventana, "VENTANA", informe, excluir)
    _dump(tarjeta, "TARJETA", informe, excluir)
    raise AssertionError("\n".join(informe))
