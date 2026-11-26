"""DIAG v1.0.16 (13): estado justo despues del test de la ventana v105."""
import gc


def test_diag_tras_ventana_v105():
    from PySide6.QtCore import QThread
    from PySide6.QtWidgets import QApplication
    from shiboken6 import isValid

    app = QApplication.instance()
    if app is not None:
        app.processEvents()
    gc.collect()
    from antivirus_hogar_pc.ui import programar_page
    from antivirus_hogar_pc.ui.main_window import VentanaPrincipal

    L = []
    vivas = [o for o in gc.get_objects()
             if isinstance(o, programar_page._TarjetaProgramacion)]
    L.append(f"tarjetas={len(vivas)}")
    ventanas = [o for o in gc.get_objects()
                if isinstance(o, VentanaPrincipal)]
    L.append(f"ventanas_python={len(ventanas)} "
             f"validas={[isValid(v) for v in ventanas]}")
    hilos = [o for o in gc.get_objects() if isinstance(o, QThread)]
    for h in hilos:
        try:
            L.append(f"hilo {type(h).__name__} running={h.isRunning()} "
                     f"finished={h.isFinished()}")
        except RuntimeError:
            L.append(f"hilo {type(h).__name__} C++ muerto")
    if ventanas:
        v = ventanas[0]
        for r in gc.get_referrers(v):
            tn = type(r).__name__
            if tn == "frame":
                continue
            if isinstance(r, dict):
                claves = [k for k, val in r.items() if val is v]
                duenos = [o for o in gc.get_objects()
                          if getattr(o, "__dict__", None) is r]
                L.append(f"ventana dict {claves} "
                         f"duenos={[type(o).__name__ for o in duenos][:4]}")
            else:
                L.append(f"ventana ref {tn} {repr(r)[:120]}")
    assert False, "\n".join(L)
