"""v1.0.9 — Lo que queda vigente tras el cambio de motor de la 1.0.10.

Las secciones 1 y 2 de este archivo (el controlador Neo6 de
SoftEther almacenado con pnputil y el respaldo interactivo de
crear la tarjeta) se RETIRARON en la 1.0.10: SoftEther salió de
la app y su solución del «Error 31» quedó superada por el cambio
de motor a OpenVPN (ver tests/test_v1010.py). Se conserva la
guarda ISPP del .iss (una línea que empieza por «#» tras espacios
rompió ISCC en la corrida 45613046882) porque protege también al
instalador nuevo.

Lo que sigue vigente de la 1.0.9:
3. La fila del servidor conectado lleva «Conectado» (verde,
   deshabilitado) y «Desconectar» (rojo) a su derecha.
4. La calificación de salud fuera del centro del anillo:
   AnilloSalud no dibuja texto y expone texto_puntuacion() +
   señal valor_cambiado para la esquina inferior izquierda.
"""
import os

import pytest

RAIZ = os.path.join(os.path.dirname(__file__), "..")


def _leer(ruta_relativa: str) -> str:
    with open(os.path.join(RAIZ, ruta_relativa), encoding="utf-8") as f:
        return f.read()


def test_guardia_ispp_ninguna_linea_empieza_por_almohadilla():
    iss = _leer(os.path.join("packaging", "instalador.iss"))
    # Guarda ISPP: ninguna línea puede EMPEZAR por «#» tras
    # espacios (salvo las directivas legítimas, que van en columna
    # 0): una continuación «#13#10 + …» al inicio de línea rompió
    # ISCC en la corrida 45613046882 («Unknown preprocessor
    # directive», línea 283).
    for linea in iss.splitlines():
        assert not linea.startswith((" ", "\t")) or \
            not linea.lstrip().startswith("#"), linea


# === 3. Cambio 1: botones por fila en VPN Gate ================================

def test_fila_conectada_lleva_conectado_verde_y_desconectar_rojo():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QPushButton

    from antivirus_hogar_pc import config
    from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo
    from antivirus_hogar_pc.modules.net import page as netpage
    from antivirus_hogar_pc.modules.net import servicios_red as srv
    from antivirus_hogar_pc.modules.net.fake import servidores_fake
    from antivirus_hogar_pc.ui import theme

    app = QApplication.instance() or QApplication([])
    pagina = netpage._PaginaRed(ContextoModulo(servicios=None))
    pagina._servidores_cargados(
        ResultadoModulo(ok=True, datos=servidores_fake()))
    assert pagina._tabla_vpn.rowCount() == 2
    conectado = pagina._visibles[0].hostname
    pagina._servidor_conectado = conectado
    pagina._repintar_servidores()

    celda0 = pagina._tabla_vpn.cellWidget(0, 7)
    botones0 = {b.text(): b for b in celda0.findChildren(QPushButton)}
    assert set(botones0) == {"Conectado", "Desconectar"}
    assert theme.VERDE_BOTON in botones0["Conectado"].styleSheet()
    assert botones0["Conectado"].isEnabled() is False
    assert theme.ROJO_BOTON in botones0["Desconectar"].styleSheet()
    assert botones0["Desconectar"].isEnabled() is True

    celda1 = pagina._tabla_vpn.cellWidget(1, 7)
    botones1 = {b.text(): b for b in celda1.findChildren(QPushButton)}
    assert set(botones1) == {"Conectar"}
    assert config.VERSION == "1.0.15"
    pagina.deleteLater()
    app.processEvents()


# === 4. Cambio 2: la cifra fuera del centro del anillo ========================

def test_anillo_109_sin_cifra_central_y_con_texto_para_la_esquina():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from antivirus_hogar_pc.ui import theme
    from antivirus_hogar_pc.ui.health_ring import AnilloSalud

    app = QApplication.instance() or QApplication([])
    anillo = AnilloSalud()
    # Sin fijar: la esquina enseña «…», nunca un 0 en rojo.
    cifra, _color, leyenda = anillo.texto_puntuacion()
    assert cifra == "…" and leyenda == "Salud del equipo"
    recibidos = []
    anillo.valor_cambiado.connect(recibidos.append)
    anillo.fijar_puntuacion(71, animado=False)
    assert recibidos and recibidos[-1] == 71.0
    cifra, color, leyenda = anillo.texto_puntuacion()
    # 71 cae en la banda ámbar del semáforo de la app (≥80 verde).
    assert cifra == "71" and color == theme.AMBAR.lower()
    assert leyenda == "Salud del equipo"
    anillo.fijar_sin_datos()
    cifra, _color, leyenda = anillo.texto_puntuacion()
    assert cifra == "—" and leyenda == "Sin datos de Windows"
    # La cifra ya NO se pinta dentro del anillo.
    fuente = _leer(os.path.join(
        "antivirus_hogar_pc", "ui", "health_ring.py"))
    assert "drawText" not in fuente
    anillo.deleteLater()
    app.processEvents()
