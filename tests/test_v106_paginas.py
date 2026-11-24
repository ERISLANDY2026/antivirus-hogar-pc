"""v1.0.6 — Regresión de las notas de la PC real (15:00–15:10 EST).

Causa raíz ÚNICA de las notas 2, 3, 4 y 5, demostrada con sondas:
la ventana principal conserva SOLO el widget que devuelve cada
factoría de página. Los objetos que gobiernan la página de Red y
VPN (QObject sin padre) y las tarjetas del Programador (objetos
Python) quedaban sin ninguna referencia viva al terminar la
factoría: Python los destruía y con ellos morían sus conexiones
(botones mudos, ni el «cargando») y sus temporizadores de
autocarga (Wi-Fi «todavía sin leer», países de VPN vacíos,
«Próxima ejecución: Desactivado» en las seis programaciones).

Estos tests construyen las páginas COMO LA VENTANA (guardando solo
el widget), fuerzan la recolección de basura y pulsan los botones
de verdad. Si el ancla de vida se pierde, fallan.
"""
import gc

import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QEventLoop, QTime, QTimer  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QComboBox,
    QLabel,
    QPushButton,
    QTimeEdit,
)


def _app():
    return QApplication.instance() or QApplication([])


def _esperar(app, ms=700):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    app.processEvents()


@pytest.fixture(autouse=True)
def _datos_temporales(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    yield


# === Red y VPN: la página sobrevive y los tres botones trabajan ===============

def test_pagina_red_viva_tras_gc_y_botones_responden(monkeypatch):
    app = _app()
    from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo
    from antivirus_hogar_pc.modules.net import page as netpage
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    llamadas = []

    def falso_wifi():
        import time as _t

        llamadas.append("wifi")
        _t.sleep(0.6)  # respuesta lenta: el «Leyendo…» es observable
        return ResultadoModulo(ok=False, mensaje="sin wifi (prueba)")

    def falsa_velocidad(al_progreso=None):
        llamadas.append("velocidad")
        if al_progreso:
            al_progreso("bajada", 42.0)
        return ResultadoModulo(
            ok=True, mensaje="ok",
            datos={"ping_ms": 12, "bajada_mbps": 42.0, "subida_mbps": 9.0})

    def falsos_servidores():
        llamadas.append("servidores")
        return ResultadoModulo(ok=False, mensaje="sin red (prueba)")

    monkeypatch.setattr(srv, "informe_wifi", falso_wifi)
    monkeypatch.setattr(srv, "prueba_velocidad_viva", falsa_velocidad)
    monkeypatch.setattr(srv, "descargar_servidores_completos",
                        falsos_servidores)
    monkeypatch.setattr(srv, "estado_vpn",
                        lambda: ResultadoModulo(ok=True, datos={}))

    # Como la ventana: SOLO se conserva el widget devuelto.
    widget = netpage.crear_pagina_red(ContextoModulo(servicios=None))
    gc.collect()
    vivas = [o for o in gc.get_objects()
             if isinstance(o, netpage._PaginaRed)]
    assert vivas, "la página murió: sus botones quedarían mudos"

    widget.show()
    _esperar(app, 1600)  # autocargas a 300/500/800 ms
    # La autocarga llamó a los servicios y la SEMILLA pobló el
    # desplegable sin red (la descarga «en vivo» falla a propósito).
    assert "wifi" in llamadas and "servidores" in llamadas
    pagina = vivas[0]
    assert pagina._combo_pais.count() > 5  # semilla: 9 países + «Todos»
    assert pagina._tabla_vpn.rowCount() >= 30

    # Click real en «Actualizar datos de Wi-Fi»: feedback inmediato
    # y llamada al servicio.
    llamadas.clear()
    pagina._btn_wifi.click()
    assert pagina._btn_wifi.text() == "Leyendo…"
    _esperar(app, 1200)
    assert "wifi" in llamadas

    # Click real en «Medir velocidad»: arranca y pinta valores.
    llamadas.clear()
    pagina._btn_velocidad.click()
    assert "Midiendo" in pagina._lbl_velocidad.text()
    _esperar(app)
    assert "velocidad" in llamadas
    assert "42.0" in pagina._val_bajada.text()

    # Click real en «Actualizar lista de servidores».
    llamadas.clear()
    pagina._btn_servidores.click()
    _esperar(app)
    assert "servidores" in llamadas
    widget.close()


def test_pagina_actualizaciones_viva_tras_gc():
    app = _app()
    from antivirus_hogar_pc.contracts import ContextoModulo
    from antivirus_hogar_pc.modules.net import page as netpage

    widget = netpage.crear_pagina_actualizaciones(
        ContextoModulo(servicios=None))
    gc.collect()
    vivas = [o for o in gc.get_objects()
             if isinstance(o, netpage._PaginaActualizaciones)]
    assert vivas, "la página de Actualizaciones también moría al GC"
    widget.deleteLater()
    app.processEvents()


# === Programador: las SEIS tarjetas guardan de verdad ==========================

def _tarjetas_de(pagina_widget):
    """Agrupa los controles de cada tarjeta por orden de aparición."""
    checks = pagina_widget.findChildren(QCheckBox)
    combos = pagina_widget.findChildren(QComboBox)
    horas = pagina_widget.findChildren(QTimeEdit)
    botones = [b for b in pagina_widget.findChildren(QPushButton)
               if b.text() == "Guardar y aplicar"]
    proximas = [l for l in pagina_widget.findChildren(QLabel)
                if l.text().startswith("Próxima ejecución")]
    return checks, combos, horas, botones, proximas


def test_programador_las_seis_tarjetas_guardan(monkeypatch):
    app = _app()
    from antivirus_hogar_pc.contracts import ContextoModulo
    from antivirus_hogar_pc.ui import programar_page
    from antivirus_hogar_pc.winapi import tasks as tareas_win

    creadas = []
    monkeypatch.setattr(
        tareas_win, "crear_tarea_programada_detalle",
        lambda id_, frec, dia, hora: (creadas.append(id_) or True, "", ""))
    monkeypatch.setattr(
        tareas_win, "eliminar_tarea_programada", lambda id_: True)

    pagina = programar_page.crear_pagina_programar(
        ContextoModulo(servicios=None))
    gc.collect()
    vivas = [o for o in gc.get_objects()
             if isinstance(o, programar_page._TarjetaProgramacion)]
    assert len(vivas) == 6, "las tarjetas murieron: Guardar no haría nada"

    pagina.show()
    checks, combos, horas, botones, proximas = _tarjetas_de(pagina)
    assert len(botones) == 6
    for i in range(6):
        checks[i].setChecked(True)
        combos[2 * i].setCurrentText("Semanal")
        combos[2 * i + 1].setCurrentText("Domingo")
        horas[i].setTime(QTime(1, 0))
        botones[i].click()
        assert "desactivada" not in proximas[i].text(), (
            f"tarjeta {i}: la próxima ejecución siguió en Desactivado")
        assert "Domingo" in proximas[i].text()
        assert "01:00" in proximas[i].text()
    assert len(creadas) == 6  # las seis tareas se crearon en Windows
    pagina.close()


def test_programador_fallo_de_schtasks_se_ve_con_causa(monkeypatch):
    app = _app()
    from antivirus_hogar_pc.contracts import ContextoModulo
    from antivirus_hogar_pc.ui import programar_page
    from antivirus_hogar_pc.winapi import tasks as tareas_win

    monkeypatch.setattr(
        tareas_win, "crear_tarea_programada_detalle",
        lambda id_, frec, dia, hora: (
            False,
            "Windows denegó el permiso para crear la tarea "
            "(se necesita una cuenta con permisos de administrador).",
            "ERROR: Access is denied."))
    pagina = programar_page.crear_pagina_programar(
        ContextoModulo(servicios=None))
    pagina.show()
    checks, _c, _h, botones, _p = _tarjetas_de(pagina)
    checks[0].setChecked(True)
    botones[0].click()
    estados = [l.text() for l in pagina.findChildren(QLabel)
               if "NO se creó" in l.text()]
    assert estados and "denegó el permiso" in estados[0]
    assert "Access is denied" not in estados[0]  # el crudo no va a pantalla
    pagina.close()


def test_schtasks_ciclo_crear_consultar_en_espanol_e_ingles(monkeypatch):
    """El ciclo crear→consultar con salidas de schtasks simuladas en
    los dos idiomas: la existencia se decide por el código de
    salida, no por parsear texto localizado."""
    from antivirus_hogar_pc.winapi import tasks as tareas_win

    salidas = {
        "es_ok": (0, "CORRECTO: La tarea programada \"AntivirusHogarPC-x\" "
                     "se ha creado correctamente.", ""),
        "en_ok": (0, "SUCCESS: The scheduled task \"AntivirusHogarPC-x\" "
                     "has successfully been created.", ""),
        "es_error": (1, "", "ERROR: Acceso denegado."),
        "en_error": (1, "", "ERROR: Access is denied."),
    }
    estado = {"crear": "es_ok"}

    def falso_comando(comando, timeout=60):
        if "/Create" in comando:
            return salidas[estado["crear"]]
        if "/Query" in comando:
            return (0, "Tarea: AntivirusHogarPC-x", "") \
                if estado["crear"].endswith("ok") else (1, "", "ERROR")
        return (0, "", "")

    monkeypatch.setattr(tareas_win, "ejecutar_comando", falso_comando)
    for idioma in ("es_ok", "en_ok"):
        estado["crear"] = idioma
        ok, causa, _detalle = tareas_win.crear_tarea_programada_detalle(
            "escaneo-completo", "semanal", "domingo", "01:00")
        assert ok and causa == ""
        assert tareas_win.existe_tarea_programada("escaneo-completo")
    for idioma in ("es_error", "en_error"):
        estado["crear"] = idioma
        ok, causa, detalle = tareas_win.crear_tarea_programada_detalle(
            "escaneo-completo", "semanal", "domingo", "01:00")
        assert not ok
        assert "denegó el permiso" in causa
        assert detalle  # el crudo queda para el registro


# === Discos: la causa ya no se pierde ===========================================

def test_optimizar_resultado_vacio_busca_la_causa_en_el_verbose():
    from antivirus_hogar_pc.winapi.disks import (
        interpretar_resultado_optimizacion)

    verbose = (
        "VERBOSE: Optimizing volume C:...\n"
        "VERBOSE: Pass 1: 40% complete\n"
        "Optimize-Volume : The volume is not supported for this "
        "operation.\n")
    res = interpretar_resultado_optimizacion("", verbose, "C", "TRIM")
    assert res["ok"] is False
    assert "causa desconocida" not in res["mensaje"]
    assert "not supported" in res["mensaje"]
    assert "Pass 1" in res["detalle"]  # la cola completa viaja al registro


def test_optimizar_sin_causa_ninguna_lo_dice_y_guarda_detalle():
    from antivirus_hogar_pc.winapi.disks import (
        interpretar_resultado_optimizacion)

    res = interpretar_resultado_optimizacion("", "VERBOSE: ...\n", "C",
                                             "la desfragmentación")
    assert res["ok"] is False
    assert "Windows no dio la causa" in res["mensaje"]
    assert "registro de actividad" in res["mensaje"]
    assert res["detalle"]


def test_optimizar_script_garantiza_resultado_y_progreso_sin_amortiguar():
    from antivirus_hogar_pc.winapi.disks import _script_optimizacion

    script = _script_optimizacion("C", "-Defrag", "P:\\progreso.txt",
                                  "P:\\resultado.txt")
    assert "finally" in script  # el resultado nunca queda vacío
    assert "AppendAllText" in script  # progreso registro a registro
    assert "Out-File -FilePath 'P:\\progreso.txt' -Append" not in script


def test_progreso_de_optimizacion_es_gradual_con_prefijos():
    """Alimentando el intérprete con prefijos crecientes del verbose
    (como llega con el nuevo script), el % sube paso a paso y no
    salta de «esperando» al 100 %."""
    from antivirus_hogar_pc.modules.system.smart_logic import (
        interpretar_progreso_optimizacion)

    completo = "\n".join(
        f"VERBOSE: Defragmentation: {p}% complete" for p in
        (5, 20, 45, 70, 90, 100))
    lineas = completo.splitlines()
    vistos = []
    for i in range(1, len(lineas) + 1):
        pct = interpretar_progreso_optimizacion(
            "\n".join(lineas[:i])).porcentaje
        if pct is not None:
            vistos.append(pct)
    assert vistos == sorted(vistos) and len(vistos) >= 4
    assert vistos[0] < 100


# === Icono espartano en la instalación (nota 8) =================================

def test_instalador_recrea_accesos_y_refresca_iconos():
    import os

    ruta = os.path.join(os.path.dirname(__file__), "..",
                        "packaging", "instalador.iss")
    with open(ruta, encoding="utf-8") as f:
        iss = f.read()
    assert '#define AppVersion "1.0.6"' in iss
    assert "[InstallDelete]" in iss and ".lnk" in iss
    assert 'IconFilename: "{app}\\icono.ico"' in iss
    assert "SHChangeNotify" in iss


def test_la_app_fija_el_icono_de_ventana_desde_sus_activos():
    app = _app()
    from PySide6.QtGui import QIcon

    from antivirus_hogar_pc import config

    import os
    ruta = os.path.join(config.carpeta_activos(), "icono_app.ico")
    assert os.path.isfile(ruta), "falta el .ico del espartano en assets"
    icono = QIcon(ruta)
    assert not icono.isNull()
    app.setWindowIcon(icono)
    assert not app.windowIcon().isNull()
