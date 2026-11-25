"""v1.0.14 — AGREGADO 1: selector de idioma Español/English.

- Paridad y cobertura del catálogo: TODA cadena que el código
  pasa por t() tiene su traducción en _EN (extracción por AST,
  como la verificación de construcción), sin valores vacíos.
- El selector de la ventana cambia textos clave de la carcasa y
  de varias pantallas, guarda el ajuste y no exige reiniciar.
- La bandeja se retraduce con el gancho al_cambiar_idioma.
(Los iconos 3D quedaron FUERA de esta entrega por veredicto del
usuario: ver INFORME-V1014.md.)
"""
import ast
import glob
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from antivirus_hogar_pc.core import i18n  # noqa: E402


def _claves_del_codigo() -> set[str]:
    claves: set[str] = set()
    raiz = os.path.join(os.path.dirname(__file__), "..", "antivirus_hogar_pc")
    for ruta in glob.glob(os.path.join(raiz, "**", "*.py"), recursive=True):
        arbol = ast.parse(open(ruta, encoding="utf-8").read())
        for nodo in ast.walk(arbol):
            if (isinstance(nodo, ast.Call)
                    and isinstance(nodo.func, ast.Name)
                    and nodo.func.id == "t"
                    and nodo.args
                    and isinstance(nodo.args[0], ast.Constant)
                    and isinstance(nodo.args[0].value, str)):
                claves.add(nodo.args[0].value)
    return claves


def test_catalogo_cubre_todo_el_codigo():
    claves = _claves_del_codigo()
    assert len(claves) > 250  # la UI entera pasa por t()
    faltan = claves - set(i18n._EN)
    assert not faltan, f"sin traducción: {sorted(faltan)[:5]}"
    assert all(v.strip() for v in i18n._EN.values())


def test_traducciones_clave_distintas_y_plantillas():
    i18n.fijar_idioma("en")
    try:
        assert i18n.t("Inicio") == "Home"
        assert i18n.t("Red y VPN") == "Network & VPN"
        assert i18n.t("Ajustes") == "Settings"
        assert i18n.t("Versión de la app") == "App version"
        assert i18n.t("Programador de tareas") == "Task scheduler"
        assert (i18n.t("Ningún servidor aceptó la conexión: se probaron "
                       "{n} servidores y todos están llenos o fuera de "
                       "servicio en este momento. No es tu conexión ni "
                       "tu credencial: es el estado de los servidores "
                       "gratuitos. Espera unos minutos o elige otro país "
                       "y vuelve a intentarlo.", n=3).startswith(
                           "No server accepted the connection: 3 servers"))
        assert i18n.t("Cadena sin catalogar XYZ") == "Cadena sin catalogar XYZ"
    finally:
        i18n.fijar_idioma("es")
    assert i18n.t("Inicio") == "Inicio"


def test_ajustes_persiste_idioma(tmp_path):
    from antivirus_hogar_pc.ui.services import Ajustes
    a = Ajustes(_ruta=str(tmp_path / "ajustes.json"))
    assert a.idioma == "es"
    a.idioma = "en"
    a.guardar()
    import json as _json
    datos = _json.loads((tmp_path / "ajustes.json").read_text("utf-8"))
    assert datos["idioma"] == "en"
    # Y un ajustes.json VIEJO (sin la clave) carga en español:
    (tmp_path / "ajustes.json").write_text("{}", encoding="utf-8")
    b = Ajustes(_ruta=str(tmp_path / "ajustes.json"))
    import json as _j2
    for clave, valor in _j2.loads("{}").items():
        setattr(b, clave, valor)
    assert b.idioma == "es"


@pytest.fixture()
def app_qt():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    i18n.fijar_idioma("es")


def test_ventana_nace_en_ingles_y_el_selector_vuelve_al_espanol(app_qt):
    from antivirus_hogar_pc.ui.main_window import VentanaPrincipal
    from antivirus_hogar_pc.ui.services import ServiciosApp

    servicios = ServiciosApp()
    servicios.ajustes.idioma = "en"
    ventana = VentanaPrincipal(servicios)
    try:
        textos = {b.text() for b in ventana._botones.values()}
        assert "Home" in textos
        assert "Settings" in textos
        assert "App version" in textos
        assert "Task scheduler" in textos
        # El selector cambia en vivo y guarda el ajuste.
        ventana._combo_idioma.setCurrentIndex(
            ventana._combo_idioma.findData("es"))
        textos = {b.text() for b in ventana._botones.values()}
        assert "Inicio" in textos
        assert "Ajustes" in textos
        assert servicios.ajustes.idioma == "es"
        ventana._combo_idioma.setCurrentIndex(
            ventana._combo_idioma.findData("en"))
        textos = {b.text() for b in ventana._botones.values()}
        assert "Home" in textos
        assert servicios.ajustes.idioma == "en"
    finally:
        ventana.deleteLater()


def test_bandeja_se_retraduce(app_qt):
    from PySide6.QtGui import QIcon

    from antivirus_hogar_pc.ui.bandeja import Bandeja

    bandeja = Bandeja(QIcon(), lambda: None, lambda: None, lambda: None)
    try:
        assert bandeja.accion_abrir.text() == "Abrir"
        i18n.fijar_idioma("en")
        bandeja.retraducir()
        assert bandeja.accion_abrir.text() == "Open"
        assert bandeja.accion_escaneo.text() == "Quick scan"
        assert bandeja.accion_salir.text() == "Quit"
    finally:
        i18n.fijar_idioma("es")
        bandeja.retraducir()
        bandeja.ocultar()
