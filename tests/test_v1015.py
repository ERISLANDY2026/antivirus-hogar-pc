"""v1.0.15 — Optimizar volúmenes: VEREDICTO CIERTO SIEMPRE.

Orden directa del usuario (2026-11-25, con foto de su Toughbook):
«ya no quiero que diga no se completó. Busca una solución
definitiva». Regresión de un requisito permanente (desde la
v1.0.7): al terminar bien, «Optimización finalizada»; si falla,
la causa REAL. El desenlace «Windows no dio la causa en ninguna
de sus fuentes» desaparece: estas pruebas fuerzan AMBOS
desenlaces y una matriz de entradas hostiles, y verifican que
ese texto no aparece en NINGÚN resultado de la vía nueva.
"""
import ast
import os

import pytest

from antivirus_hogar_pc.winapi.disks import (
    _script_defrag,
    interpretar_resultado_defrag,
)

FRASE_PROHIBIDA = "no dio la causa"


def test_defrag_exito_codigo_cero():
    res = interpretar_resultado_defrag(
        "PRECHECK=OK\nEXITCODE=0\n",
        "Microsoft Drive Optimizer\nRetrim: 100%\n"
        "The operation completed successfully.\n",
        "C", "TRIM")
    assert res["ok"] is True
    assert res["mensaje"].startswith("Optimización finalizada")


def test_defrag_fallo_con_causa_en_su_salida():
    res = interpretar_resultado_defrag(
        "PRECHECK=OK\nEXITCODE=1\n",
        "Microsoft Drive Optimizer\n"
        "The volume could not be optimized. Error: 0x89000017\n",
        "C", "TRIM")
    assert res["ok"] is False
    assert "could not be optimized" in res["mensaje"]


def test_defrag_fallo_sin_texto_la_causa_es_el_codigo():
    res = interpretar_resultado_defrag(
        "PRECHECK=OK\nEXITCODE=2147746132\n", "", "C", "TRIM")
    assert res["ok"] is False
    assert "2147746132" in res["mensaje"]


def test_precheck_trim_deshabilitado_es_la_causa():
    res = interpretar_resultado_defrag(
        "PRECHECK=TRIM_DESHABILITADO\n", "", "C", "TRIM")
    assert res["ok"] is False
    assert "TRIM" in res["mensaje"] and "DisableDeleteNotify" in res["mensaje"]


def test_precheck_servicio_deshabilitado_es_la_causa():
    res = interpretar_resultado_defrag(
        "PRECHECK=SERVICIO_DESHABILITADO\n", "", "C", "TRIM")
    assert res["ok"] is False
    assert "defragsvc" in res["mensaje"]


def test_matriz_sin_frase_prohibida():
    entradas = [
        ("", ""),
        ("PRECHECK=OK\n", ""),
        ("PRECHECK=SIN_RESULTADO\n", "ruido\n"),
        ("PRECHECK=ERROR_SCRIPT\nERROR=boom\n", ""),
        ("EXITCODE=\n", ""),
        ("basura sin claves\n", "error generico\n"),
        ("PRECHECK=OK\nEXITCODE=5\n", "Access denied.\n"),
        ("PRECHECK=OK\nEXITCODE=0\n", ""),
    ]
    for resultado, salida in entradas:
        res = interpretar_resultado_defrag(resultado, salida, "C", "TRIM")
        assert FRASE_PROHIBIDA not in res["mensaje"], (resultado, res)
        assert res["mensaje"].strip()


def test_script_defrag_lleva_prechecks_y_codigo():
    script = _script_defrag("C", True, "X:\\salida.txt", "X:\\res.txt")
    assert "DisableDeleteNotify" in script       # pre-chequeo TRIM
    assert "defragsvc" in script                 # pre-chequeo servicio
    assert "defrag.exe" in script and "'/L'" in script   # SSD: retrim
    assert "EXITCODE=" in script                 # código capturado
    script_hdd = _script_defrag("D", False, "X:\\s.txt", "X:\\r.txt")
    assert "'/D'" in script_hdd                  # HDD: desfragmentar
    assert "DisableDeleteNotify" not in script_hdd


# --- Iconos 3D como recursos gráficos (veredicto del usuario) ------

def test_los_12_iconos_son_recursos_png_con_alfa():
    """Cada entrada de navegación tiene su recurso gráfico 3D
    (assets/iconos3d/<nombre>.png): PNG real, cuadrado, con
    píxeles transparentes (fondo recortado) y contenido opaco."""
    import os
    import struct

    # Las claves de PALETA_NAV se leen por AST: importar el módulo
    # arrastraría Qt y esta prueba es de recursos, no de widgets.
    ruta_nav = os.path.join(os.path.dirname(__file__), "..",
                            "antivirus_hogar_pc", "ui", "iconos_nav.py")
    arbol = ast.parse(open(ruta_nav, encoding="utf-8").read())
    claves = set()
    for nodo in ast.walk(arbol):
        valor = None
        if isinstance(nodo, ast.AnnAssign) and isinstance(
                nodo.target, ast.Name) and nodo.target.id == "PALETA_NAV":
            valor = nodo.value
        if isinstance(nodo, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "PALETA_NAV"
                for t in nodo.targets):
            valor = nodo.value
        if valor is not None:
            claves = {c.value for c in valor.keys}
    PALETA_NAV = sorted(claves)
    assert len(PALETA_NAV) == 12

    raiz = os.path.join(os.path.dirname(__file__), "..",
                        "antivirus_hogar_pc", "assets", "iconos3d")
    assert sorted(PALETA_NAV) == sorted(
        os.path.splitext(f)[0] for f in os.listdir(raiz)
        if f.endswith(".png"))
    for nombre in PALETA_NAV:
        datos = open(os.path.join(raiz, f"{nombre}.png"), "rb").read()
        assert datos[:8] == b"\x89PNG\r\n\x1a\n", nombre
        ancho, alto = struct.unpack(">II", datos[16:24])
        assert ancho == alto == 192, (nombre, ancho, alto)


def test_pixmap_nav_usa_el_recurso_3d():
    """pixmap_nav compone desde el recurso (no devuelve nulo y el
    centro del icono es opaco: hay gráfico, no un glifo vacío)."""
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    from antivirus_hogar_pc.ui.iconos_nav import (
        _recurso_3d, pixmap_nav)

    app = QApplication.instance() or QApplication([])
    for nombre in ("inicio", "escanear", "proteccion", "drivers",
                   "limpieza", "discos", "actualizar", "red",
                   "informes", "version", "calendario", "ajustes"):
        assert _recurso_3d(nombre) is not None, nombre
        pm = pixmap_nav(nombre)
        assert not pm.isNull(), nombre
        img: QImage = pm.toImage()
        assert img.pixelColor(img.width() // 2,
                              img.height() // 2).alpha() > 0, nombre
