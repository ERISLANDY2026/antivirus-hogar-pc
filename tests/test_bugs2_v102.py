"""Bugs 4, 5 y 6 de la v1.0.2 + fondo de radar (segunda ronda).

- Bug 6: fusión multi-fuente de firmas (una ok, una caída, una vacía),
  con mensaje por fuente y éxito si al menos una aporta.
- Bug 4: flujo del botón «Actualizar datos de Wi-Fi» con el backend
  entregando a mano: pulsar → «leyendo» → datos con sello de hora.
- Bug 5: el escaneo de drivers con el backend lanzando excepción
  termina en error VISIBLE con causa en la página (nunca en silencio).
- Radar: el widget se crea, se apaga por interruptor y la lectura de
  «reducir animaciones» de Windows no rompe fuera de Windows.
"""
import urllib.error

import pytest

from antivirus_hogar_pc.contracts import ResultadoModulo
from antivirus_hogar_pc.core import threats_update as tu


# === Bug 6: multi-fuente =====================================================

def _descargador_falso(url, datos=None, auth_key="", timeout=45):
    if "malicious-hash" in url:
        return ""  # v1.0.3: sin huellas en este fake; el caso con huellas
        # lo cubre test_v103.py
    if "urlhaus-filter" in url:
        return "# comentario\n0.0.0.0 malo-uno.example\nmalo-dos.example\n"
    if "Phishing.Database" in url:
        raise urllib.error.HTTPError(url, 500, "boom", None, None)
    if "openphish" in url:
        return ""  # fuente vacía: no aporta, no es «fallo de conexión»
    if "cert.pl" in url:
        return "malo-tres.example\n1.2.3.4\n"
    raise AssertionError(f"URL inesperada: {url}")


def test_multifuente_fusiona_y_reporta_por_fuente():
    r = tu.actualizar_firmas_multifuente(auth_key="", descargador=_descargador_falso)
    assert r.ok  # al menos una fuente aportó
    assert "malo-uno.example" in r.dominios
    assert "malo-dos.example" in r.dominios
    assert "malo-tres.example" in r.dominios
    assert "1.2.3.4" not in r.dominios  # las IP sueltas no son dominios
    por_nombre = {f.nombre: f for f in r.por_fuente}
    assert por_nombre["URLhaus (vía malware-filter)"].cantidad == 2
    assert por_nombre["Phishing.Database"].error  # caída, con causa
    assert por_nombre["OpenPhish"].cantidad == 0
    assert not por_nombre["OpenPhish"].error  # vacía no es error de conexión
    # abuse.ch sin clave (v1.0.3): fuente OPCIONAL, no un fallo —
    # las huellas llegan de malicious-hash, que no pide clave.
    assert por_nombre["abuse.ch (MalwareBazaar)"].opcional
    assert not por_nombre["abuse.ch (MalwareBazaar)"].error
    resumen = r.resumen()
    assert "URLhaus" in resumen and "falló" in resumen
    assert "opcional" in resumen


def test_multifuente_todo_caido_es_error_total_con_causas():
    def todo_caido(url, datos=None, auth_key="", timeout=45):
        raise urllib.error.URLError("sin ruta")

    r = tu.actualizar_firmas_multifuente(auth_key="clave", descargador=todo_caido)
    assert not r.ok
    assert all(f.error for f in r.por_fuente)


def test_parsear_dominios_de_urls():
    texto = "https://phish.example/login\nhttp://malo.example:8080/x\nno-es-url\n"
    assert tu.parsear_dominios_de_urls(texto) == ["malo.example", "phish.example"]


# === Bug 4: botón de Wi-Fi =====================================================

def _pagina_red():
    pytest.importorskip("PySide6")
    import os as _os

    _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from antivirus_hogar_pc.contracts import ContextoModulo
    from antivirus_hogar_pc.modules.net.page import _PaginaRed

    app = QApplication.instance() or QApplication([])
    return app, _PaginaRed(ContextoModulo(servicios=None))


def test_wifi_flujo_leyendo_y_sello_de_hora():
    app, pagina = _pagina_red()
    pagina._cargar_wifi()
    # Estado «leyendo» INMEDIATO tras pulsar (sin procesar eventos aún)
    assert not pagina._btn_wifi.isEnabled()
    assert pagina._btn_wifi.text() == "Leyendo…"
    assert not pagina._barra_wifi.isHidden()  # progreso visible al pulsar

    datos = {"nombre": "MiRed", "senal": 80, "velocidad_enlace_mbps": 866,
             "banda": "5 GHz", "canal": 36, "estandar": "Wi-Fi 6",
             "autenticacion": "WPA2", "ip_local": "192.168.1.50",
             "puerta_enlace": "192.168.1.1", "dns": ["1.1.1.1"],
             "perfiles": ["MiRed"]}
    pagina._wifi_cargado(ResultadoModulo(ok=True, datos=datos))
    assert pagina._btn_wifi.isEnabled()
    assert pagina._btn_wifi.text() == "Actualizar datos de Wi-Fi"
    assert "Actualizado a las" in pagina._lbl_wifi_sello.text()

    # Y si netsh falla: error visible con causa, botón recuperado
    pagina._wifi_cargado(ResultadoModulo(
        ok=False, mensaje="netsh no respondió", detalle_tecnico="timeout"))
    assert pagina._btn_wifi.isEnabled()
    assert "No se pudo actualizar" in pagina._lbl_wifi_sello.text()
    pagina.deleteLater()
    app.processEvents()


# === Bug 5: escaneo de drivers ==================================================

def test_drivers_paso1_excepcion_es_error_con_causa(monkeypatch):
    from antivirus_hogar_pc.modules.system import servicios_sistema as svc
    from antivirus_hogar_pc.winapi import drivers_win

    def explota():
        raise RuntimeError("la consulta CIM cayó")

    monkeypatch.setattr(drivers_win, "enumerar_drivers", explota)
    r = svc.escanear_drivers_paso1()
    assert not r.ok
    assert "CIM" in r.mensaje


def test_drivers_pagina_muestra_el_fallo(monkeypatch):
    pytest.importorskip("PySide6")
    import os as _os
    import time as _time

    _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton

    from antivirus_hogar_pc.contracts import ContextoModulo
    from antivirus_hogar_pc.modules.system import page as pagina_drivers
    from antivirus_hogar_pc.modules.system import servicios_sistema as svc

    monkeypatch.setattr(
        svc, "escanear_drivers_paso1",
        lambda: ResultadoModulo(ok=False, mensaje="fallo CIM de prueba",
                                detalle_tecnico="boom"))
    app = QApplication.instance() or QApplication([])
    pagina = pagina_drivers.crear_pagina_drivers(ContextoModulo(servicios=None))
    boton = next(b for b in pagina.findChildren(QPushButton)
                 if b.text() == "Escanear drivers")
    boton.click()
    limite = _time.time() + 10
    textos = []
    while _time.time() < limite:
        app.processEvents()
        textos = [l.text() for l in pagina.findChildren(QLabel)]
        if any("No se pudo escanear" in t for t in textos):
            break
        _time.sleep(0.05)
    assert any("No se pudo escanear" in t and "fallo CIM de prueba" in t
               for t in textos), textos
    assert boton.isEnabled()  # nunca se queda «escaneando»
    pagina.deleteLater()
    app.processEvents()


def test_drivers_pasos_2_y_3_separados(monkeypatch):
    from antivirus_hogar_pc.core.drivers_logic import DriverInstalado
    from antivirus_hogar_pc.modules.system import servicios_sistema as svc
    from antivirus_hogar_pc.winapi import drivers_win

    instalados = [DriverInstalado("Audio", "1.0", "", "Realtek", "oem1.inf", "ID1", True)]
    monkeypatch.setattr(drivers_win, "buscar_drivers_windows_update",
                        lambda: (_ for _ in ()).throw(RuntimeError("WU caído")))
    buscar = svc.escanear_drivers_paso2_buscar(instalados)
    assert buscar.ok and buscar.datos["wu_consultado"] is False
    final = svc.escanear_drivers_paso3_comparar(
        instalados, [], False, "")
    assert final.ok and final.datos["estados"][0].estado == "sin_datos"


# === Radar del Panel ==============================================================

def test_radar_se_crea_y_se_apaga():
    pytest.importorskip("PySide6")
    import os as _os

    _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from antivirus_hogar_pc.ui.fondo_radar import FondoRadar

    app = QApplication.instance() or QApplication([])
    radar = FondoRadar(animado=True)
    radar.activar_animacion(False)
    assert not radar._temporizador.isActive()
    radar.activar_animacion(True)  # oculto: no arranca hasta mostrarse
    radar.deleteLater()
    app.processEvents()


def test_animaciones_windows_no_rompe_y_devuelve_bool():
    """En Linux devuelve True (sin lectura posible). En Windows devuelve
    lo que diga SPI_GETANIMATION del sistema — el runner de Actions, por
    ejemplo, reporta animaciones desactivadas y eso también es válido:
    lo importante es que no rompa y devuelva un bool."""
    from antivirus_hogar_pc.modules.panel.datos import animaciones_windows_permitidas

    assert isinstance(animaciones_windows_permitidas(), bool)
