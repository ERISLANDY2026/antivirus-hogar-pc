"""v1.0.7 — Notas de la revisión de la 1.0.6 en la PC real + SoftEther.

1. Discos: el desenlace de «Optimizar volúmenes» se extrae también
   del registro de eventos de Windows y de la salida detallada
   completa: si consta que terminó, «Optimización finalizada»; si
   falló, la causa verdadera de esas fuentes.
2. VPN Gate: SoftEther incorporado manejado por vpncmd (simulado:
   en CI no hay VPN real) — crear la conexión, conectar, estado
   conectado con el literal real del cliente, desconectar y errores
   con mensaje claro en español; el botón del servidor conectado se
   pone verde y dice «Conectado».
3. El descargador crea solo su carpeta (en la PC real faltaba
   %LOCALAPPDATA%\\AntivirusHogarPC\\actualizaciones y el botón de
   actualizar fallaba por eso).
"""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


# === 0. Versión y empaquetado ==================================================

def test_notas_y_version_107():
    from antivirus_hogar_pc import config
    from antivirus_hogar_pc.core import notas_version

    assert config.VERSION == "1.0.7"
    assert notas_version.NOTAS_VERSION[0]["version"] == "1.0.7"
    notas = notas_version.notas_de("1.0.7")
    assert notas is not None and len(notas["novedades"]) >= 3
    texto = " ".join(notas["novedades"])
    assert "SoftEther" in texto and "Optimización finalizada" in texto


def test_instalador_lleva_softether_incorporado():
    import os

    raiz = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(raiz, "packaging", "instalador.iss"),
              encoding="utf-8") as f:
        iss = f.read()
    assert '#define AppVersion "1.0.7"' in iss
    assert "softether\\client\\*" in iss          # el payload, a {app}\softether
    assert "SEVPNCLIENT" in iss                  # registra el servicio
    assert "SoftEtherServicioPropio" in iss      # marca: solo retira el suyo
    with open(os.path.join(raiz, ".github", "workflows",
                           "build-windows.yml"), encoding="utf-8") as f:
        yml = f.read()
    assert "softether-vpnclient-v4.44-9807" in yml  # descarga oficial fijada
    assert "56249368" in yml                        # tamaño verificado


# === 1. Discos: desenlace real de la optimización ==============================

def test_optimizar_ok_directo_dice_finalizada():
    from antivirus_hogar_pc.winapi.disks import (
        interpretar_resultado_optimizacion)

    res = interpretar_resultado_optimizacion("OK", "", "C", "TRIM")
    assert res["ok"] is True
    assert "Optimización finalizada" in res["mensaje"]


def test_optimizar_sin_ok_pero_evento_de_exito_dice_finalizada():
    from antivirus_hogar_pc.winapi.disks import (
        interpretar_resultado_optimizacion)

    eventos = [{"id": 258, "mensaje": (
        "The storage optimizer successfully completed retrim on (C:)")}]
    res = interpretar_resultado_optimizacion(
        "", "VERBOSE: Pass 1: 100% complete\n", "C", "TRIM",
        eventos=eventos)
    assert res["ok"] is True
    assert "Optimización finalizada" in res["mensaje"]
    assert "registro de eventos" in res["mensaje"]


def test_optimizar_evento_de_fallo_ensena_su_motivo():
    from antivirus_hogar_pc.winapi.disks import (
        interpretar_resultado_optimizacion)

    eventos = [{"id": 258, "mensaje": (
        "The storage optimizer was unable to complete defragmentation "
        "on (C:) because: The operation requested is not supported by "
        "the hardware backing the volume. (0x8900002A)")}]
    res = interpretar_resultado_optimizacion(
        "", "VERBOSE: ...\n", "C", "la desfragmentación", eventos=eventos)
    assert res["ok"] is False
    assert "not supported by the hardware" in res["mensaje"]
    assert "causa desconocida" not in res["mensaje"].lower()
    assert "0x8900002A" in res["detalle"]  # el texto entero, al registro


def test_optimizar_verbose_con_informe_final_dice_finalizada():
    from antivirus_hogar_pc.winapi.disks import (
        interpretar_resultado_optimizacion)

    verbose = (
        "VERBOSE: Optimizing volume C:...\n"
        "VERBOSE: Pass 1: 100% complete\n"
        "Post Defragmentation Report:\n"
        "VERBOSE:   Volume size = 100 GB\n")
    res = interpretar_resultado_optimizacion(
        "", verbose, "C", "la desfragmentación", eventos=[])
    assert res["ok"] is True
    assert "Optimización finalizada" in res["mensaje"]


def test_eventos_de_otra_unidad_no_cuentan():
    from antivirus_hogar_pc.winapi.disks import (
        interpretar_eventos_optimizacion)

    eventos = [{"mensaje": "The storage optimizer successfully "
                           "completed retrim on (D:)"}]
    assert interpretar_eventos_optimizacion(eventos, "C") is None
    assert interpretar_eventos_optimizacion([], "C") is None
    assert interpretar_eventos_optimizacion(None, "C") is None


def test_eventos_el_mas_reciente_manda():
    from antivirus_hogar_pc.winapi.disks import (
        interpretar_eventos_optimizacion)

    eventos = [
        {"mensaje": "The storage optimizer was unable to complete "
                    "retrim on (C:) because: error de prueba"},
        {"mensaje": "The storage optimizer successfully completed "
                    "retrim on (C:)"},
    ]
    res = interpretar_eventos_optimizacion(eventos, "C")
    assert res is not None and res["ok"] is False
    assert "error de prueba" in res["causa"]


# === 2. SoftEther por vpncmd (simulado) ========================================

_SALIDA_CONECTADO = (
    "AccountStatusGet command - Get Current VPN Connection Setting Status\n"
    "Item                                      |Value\n"
    "------------------------------------------+----\n"
    "VPN Connection Setting Name               |AntivirusHogarVPN\n"
    "Session Status                            |Connection Completed "
    "(Session Established)\n"
    "Server Name                               |vpn123.opengw.net\n"
    "Port Number                               |TCP Port 443\n"
    "The command completed successfully.\n")

_OK = "The command completed successfully.\n"


class _VpncmdFalso:
    """Simula el cliente SoftEther local: NIC, cuenta y sesión."""

    def __init__(self, fallar_conexion=False):
        self.nic = False
        self.cuenta = False
        self.conectado = False
        self.fallar_conexion = fallar_conexion
        self.comandos = []

    def __call__(self, argumentos, timeout=60):
        comando = argumentos[0]
        self.comandos.append(comando)
        if comando == "NicList":
            filas = ("Virtual Network Adapter Name|Status\n"
                     "----------------------------+------\n")
            if self.nic:
                filas += "VPN|Enabled\n"
            return 0, filas + _OK
        if comando == "NicCreate":
            self.nic = True
            return 0, _OK
        if comando == "AccountList":
            filas = "VPN Connection Setting Name|Status\n---\n"
            if self.cuenta:
                filas += "AntivirusHogarVPN|Disconnected\n"
            return 0, filas + _OK
        if comando == "AccountCreate":
            assert "/SERVER:vpn123.opengw.net:443" in argumentos[2]
            assert "/HUB:VPNGATE" in argumentos[3]
            assert "/USERNAME:vpn" in argumentos[4]
            assert "/NICNAME:VPN" in argumentos[5]
            self.cuenta = True
            return 0, _OK
        if comando == "AccountPasswordSet":
            assert "/PASSWORD:vpn" in argumentos[2]
            assert "/TYPE:standard" in argumentos[3]
            return 0, _OK
        if comando == "AccountConnect":
            if self.fallar_conexion:
                return 2, ("AccountConnect command\n"
                           "Error Code: 2\n"
                           "Connection to the server failed.\n")
            self.conectado = True
            return 0, _OK
        if comando == "AccountStatusGet":
            if self.conectado:
                return 0, _SALIDA_CONECTADO
            return 0, ("Session Status                            |"
                       "Not Connected\n" + _OK)
        if comando == "AccountDisconnect":
            self.conectado = False
            return 0, _OK
        if comando == "AccountDelete":
            self.cuenta = False
            return 0, _OK
        raise AssertionError(f"comando inesperado: {argumentos}")


def _softether_falso(monkeypatch, falso):
    from antivirus_hogar_pc.winapi import vpn_win

    monkeypatch.setattr(vpn_win, "ruta_vpncmd",
                        lambda: r"C:\falso\vpncmd.exe")
    monkeypatch.setattr(vpn_win, "_ejecutar_vpncmd", falso)
    return vpn_win


def test_interpretar_estado_cuenta_literal_real():
    from antivirus_hogar_pc.winapi.vpn_win import interpretar_estado_cuenta

    assert interpretar_estado_cuenta(_SALIDA_CONECTADO) is True
    assert interpretar_estado_cuenta("Session Status | Not Connected") is False
    assert interpretar_estado_cuenta("") is False


def test_conectar_softether_flujo_completo(monkeypatch):
    vpn_win = _softether_falso(monkeypatch, _VpncmdFalso())
    res = vpn_win.conectar_softether("vpn123.opengw.net", espera=5)
    assert res["ok"] is True
    assert res["datos"]["via"] == "softether"
    falso = vpn_win._ejecutar_vpncmd
    assert "NicCreate" in falso.comandos      # creó la tarjeta virtual
    assert "AccountCreate" in falso.comandos  # creó la conexión VPNGATE
    assert "AccountConnect" in falso.comandos
    estado = vpn_win.estado_softether()
    assert estado == {"instalado": True, "conectado": True,
                      "cuenta": "AntivirusHogarVPN"}
    desc = vpn_win.desconectar_softether()
    assert desc["ok"] is True
    assert vpn_win.estado_softether()["conectado"] is False


def test_conectar_softether_error_de_vpncmd_en_espanol(monkeypatch):
    vpn_win = _softether_falso(
        monkeypatch, _VpncmdFalso(fallar_conexion=True))
    res = vpn_win.conectar_softether("vpn123.opengw.net", espera=5)
    assert res["ok"] is False
    # Refuerzo 3 de la 1.0.7: cada error típico con su mensaje
    # específico en español (aquí: el servidor no respondió).
    assert "no respondió" in res["mensaje"]
    assert "Error Code: 2" in res["detalle"]  # la causa técnica, al detalle


def test_servicios_conectar_vpn_usa_softether(monkeypatch, tmp_path):
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    monkeypatch.setattr(srv.config, "carpeta_datos", lambda: str(tmp_path))
    monkeypatch.setattr(srv.vpn_win, "softether_instalado", lambda: True)
    monkeypatch.setattr(
        srv.vpn_win, "conectar_softether",
        lambda hostname: {"ok": True, "mensaje": "", "detalle": "",
                          "datos": {"via": "softether"}})

    class _Serv:
        hostname = "vpn123.opengw.net"
        pais = "Japan"
        pais_corto = "JP"

    r = srv.conectar_vpn(_Serv())
    assert r.ok is True
    assert r.datos["conectado"] is True and r.datos["via"] == "softether"
    assert srv._leer_estado_vpn().get("via") == "softether"


def test_servicios_estado_y_desconexion_softether(monkeypatch, tmp_path):
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    monkeypatch.setattr(srv.config, "carpeta_datos", lambda: str(tmp_path))
    monkeypatch.setattr(srv.vpn_win, "clientes_vpn_instalados", lambda: [])
    monkeypatch.setattr(srv.vpn_win, "ip_publica_actual",
                        lambda timeout=15: "1.2.3.4")
    monkeypatch.setattr(srv.vpn_win, "hay_tunel_openvpn", lambda: False)
    monkeypatch.setattr(
        srv.vpn_win, "estado_softether",
        lambda: {"instalado": True, "conectado": True,
                 "cuenta": "AntivirusHogarVPN"})
    monkeypatch.setattr(
        srv.vpn_win, "desconectar_softether",
        lambda: {"ok": True, "mensaje": "", "detalle": "", "datos": {}})

    estado = srv.estado_vpn()
    assert estado.ok and estado.datos["conectada"] is True
    assert estado.datos["conectada_softether"] is True

    r = srv.desconectar_vpn()
    assert r.ok is True and "SoftEther" in r.mensaje


def test_pagina_boton_se_pone_verde_conectado(monkeypatch):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    def _esperar(ms=700):
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()
        app.processEvents()

    from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo
    from antivirus_hogar_pc.modules.net import page as netpage
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    monkeypatch.setattr(srv, "informe_wifi",
                        lambda: ResultadoModulo(ok=False, mensaje="sin wifi"))
    monkeypatch.setattr(
        srv, "descargar_servidores_completos",
        lambda: ResultadoModulo(ok=False, mensaje="sin red (prueba)"))
    monkeypatch.setattr(srv, "estado_vpn",
                        lambda: ResultadoModulo(ok=True, datos={}))
    monkeypatch.setattr(
        srv, "conectar_vpn",
        lambda servidor: ResultadoModulo(
            ok=True, mensaje="túnel arriba",
            datos={"conectado": True, "via": "softether"}))

    widget = netpage.crear_pagina_red(ContextoModulo(servicios=None))
    pagina = widget._pagina_controladora
    widget.show()
    _esperar(1200)  # autocargas; la semilla puebla la tabla
    assert pagina._tabla_vpn.rowCount() >= 30
    hostname = pagina._visibles[0].hostname
    monkeypatch.setattr(
        srv, "estado_vpn",
        lambda: ResultadoModulo(ok=True, datos={
            "conectada": True, "servidor": hostname, "pais": "Japan",
            "clientes": [], "ip": ""}))

    boton = pagina._tabla_vpn.cellWidget(0, 5)
    assert boton.text() == "Conectar"
    boton.click()
    _esperar(900)
    boton_nuevo = pagina._tabla_vpn.cellWidget(0, 5)
    assert boton_nuevo.text() == "Conectado"
    assert "Conectado" in pagina._lbl_vpn.text()
    assert pagina._servidor_conectado == hostname

    # Cierre ORDENADO (lección de la corrida CI 45493532868: la suite
    # pasaba 225/225 pero el proceso salía con código 1 — un _Trabajo
    # o temporizador de la página seguía vivo al caer el intérprete y
    # la caída al cierre es una lotería de tiempos). Se espera a que
    # los hilos terminen, se destruye el widget (su señal destroyed
    # suelta los trabajos) y se vacía la cola de eventos.
    import gc as _gc

    _esperar(600)
    widget.close()
    widget.deleteLater()
    _esperar(300)
    app.processEvents()
    del widget, pagina
    _gc.collect()
    app.processEvents()


# === 3. La carpeta de descargas se crea sola ===================================

def _servidor_simple(datos: bytes):
    class Manejador(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def log_message(self, *args):
            pass

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor


def test_descarga_crea_la_carpeta_si_no_existe(tmp_path):
    from antivirus_hogar_pc.core.updater import descargar_archivo

    datos = b"instalador-de-prueba" * 100
    servidor = _servidor_simple(datos)
    try:
        url = f"http://127.0.0.1:{servidor.server_address[1]}/inst.exe"
        destino = str(tmp_path / "actualizaciones" / "inst.exe")
        assert not (tmp_path / "actualizaciones").exists()
        descargar_archivo(url, destino, reintentos=2, pausa=0.01)
        with open(destino, "rb") as f:
            assert f.read() == datos
    finally:
        servidor.shutdown()


def test_instalar_actualizacion_crea_la_carpeta(monkeypatch, tmp_path):
    import hashlib
    from types import SimpleNamespace

    from antivirus_hogar_pc.modules.net import servicios_red as srv

    datos = b"exe-falso-verificable" * 50
    servidor = _servidor_simple(datos)
    try:
        url = f"http://127.0.0.1:{servidor.server_address[1]}/inst.exe"
        monkeypatch.setattr(srv.config, "carpeta_datos", lambda: str(tmp_path))
        info = SimpleNamespace(
            url=url, sha256=hashlib.sha256(datos).hexdigest())
        # En no-Windows la función descarga, verifica y NO abre el
        # instalador: la ruta devuelta prueba que la carpeta se creó.
        r = srv.instalar_actualizacion_app(info)
        carpeta = tmp_path / "actualizaciones"
        assert carpeta.is_dir()
        assert (carpeta / "inst.exe").is_file()
        assert r.datos["ruta"] == str(carpeta / "inst.exe")
    finally:
        servidor.shutdown()
