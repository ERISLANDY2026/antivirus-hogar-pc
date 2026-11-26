"""DIAG v1.0.16 (14): referrers de la pagina Programador tras v105."""
import gc


def _desc(r, obj):
    tn = type(r).__name__
    if tn == "frame":
        return None
    if isinstance(r, dict):
        claves = [k for k, val in r.items() if val is obj]
        duenos = [o for o in gc.get_objects()
                  if getattr(o, "__dict__", None) is r]
        return (f"dict {claves} "
                f"duenos={[type(o).__name__ for o in duenos][:4]}")
    return f"{tn} {repr(r)[:120]}"


def test_diag_tras_ventana_v105():
    from PySide6.QtCore import QThread
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is not None:
        app.processEvents()
    gc.collect()
    from antivirus_hogar_pc.ui import programar_page

    L = []
    vivas = [o for o in gc.get_objects()
             if isinstance(o, programar_page._TarjetaProgramacion)]
    L.append(f"tarjetas={len(vivas)}")
    # pagina programar duena de las tarjetas
    paginas = []
    for o in gc.get_objects():
        d = getattr(o, "__dict__", None)
        if isinstance(d, dict) and "_tarjetas_programacion" in d:
            paginas.append(o)
    L.append(f"paginas_programar={len(paginas)}")
    for p in paginas:
        for r in gc.get_referrers(p):
            s = _desc(r, p)
            if s:
                L.append(f"pagina <- {s}")
    hilos = [o for o in gc.get_objects() if isinstance(o, QThread)]
    infos = []
    for h in hilos:
        try:
            infos.append(f"{type(h).__name__}(run={h.isRunning()})")
        except RuntimeError:
            infos.append(f"{type(h).__name__}(muerto)")
    L.append(f"hilos={infos}")
    for h in hilos:
        if type(h).__name__ != "_TrabajadorInforme":
            continue
        for r in gc.get_referrers(h):
            s = _desc(r, h)
            if s:
                L.append(f"trabajador <- {s}")
    assert False, "\n".join(L)
