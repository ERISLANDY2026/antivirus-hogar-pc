"""DIAG v1.0.16 (12): cadena de retención de la ventana tras deleteLater."""
import gc
import time


def test_diag_cadena_retencion():
    L = []
    def print(*a, **k):
        L.append(' '.join(str(x) for x in a))
    from PySide6.QtCore import QCoreApplication, QEvent, QThread
    from PySide6.QtWidgets import QApplication
    from shiboken6 import isValid

    app = QApplication.instance() or QApplication([])
    from antivirus_hogar_pc.ui import programar_page
    from antivirus_hogar_pc.ui.main_window import VentanaPrincipal
    from antivirus_hogar_pc.ui.services import ServiciosApp

    ventana = VentanaPrincipal(ServiciosApp())
    ventana.setObjectName("VENTANA_DIAG")
    ventana.ir_a("version")
    app.processEvents()
    ventana.ir_a("programar")
    app.processEvents()
    ventana.deleteLater()
    app.processEvents()
    viva_ref = ventana
    del ventana
    for i in range(10):
        gc.collect()
        app.processEvents()
        vivas = [o for o in gc.get_objects()
                 if isinstance(o, programar_page._TarjetaProgramacion)]
        hilos = [o for o in gc.get_objects() if isinstance(o, QThread)]
        corriendo = []
        for h in hilos:
            try:
                if h.isRunning():
                    corriendo.append(type(h).__name__)
            except RuntimeError:
                pass
        print(f"DIAG12 t={i} tarjetas={len(vivas)} "
              f"ventana_valida={isValid(viva_ref)} hilos={corriendo}")
        if not isValid(viva_ref):
            break
        time.sleep(2)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()
    print("DIAG12 tras sendPostedEvents: ventana_valida=",
          isValid(viva_ref))
    if isValid(viva_ref):
        # referrers directos de la ventana, sin frames ni este módulo
        for r in gc.get_referrers(viva_ref):
            tn = type(r).__name__
            if tn == "frame":
                continue
            if isinstance(r, dict):
                claves = [k for k, v in r.items() if v is viva_ref]
                duenos = [o for o in gc.get_objects()
                          if getattr(o, "__dict__", None) is r]
                print("DIAG12 dict", claves,
                      "duenos:", [type(o).__name__ for o in duenos][:4])
            else:
                print("DIAG12 ref:", tn, repr(r)[:140])
    assert False, '\n'.join(L)
