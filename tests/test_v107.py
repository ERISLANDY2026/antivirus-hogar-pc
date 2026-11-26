"""v1.0.7 — Notas de la revisión de la 1.0.6 en la PC real.

1. Discos: el desenlace de «Optimizar volúmenes» se extrae también
   del registro de eventos de Windows y de la salida detallada
   completa: si consta que terminó, «Optimización finalizada»; si
   falló, la causa verdadera de esas fuentes.
2. VPN Gate: la sección 2 era el motor SoftEther por vpncmd —
   RETIRADO en la 1.0.10 con el cambio de motor a OpenVPN; aquí
   quedan los equivalentes de la capa de servicios con el motor
   nuevo (los del motor en sí viven en tests/test_v1010.py) y la
   página con el botón verde «Conectado».
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

    # v1.0.13: la versión vigente sube (arreglo del motor VPN);
    # las notas de la 1.0.10 y anteriores quedan en el historial.
    assert config.VERSION == "1.0.20"
    assert notas_version.NOTAS_VERSION[0]["version"] == "1.0.20"
    notas = notas_version.notas_de("1.0.14")
    assert notas is not None and len(notas["novedades"]) >= 3
    notas = notas_version.notas_de("1.0.10")
    assert notas is not None and len(notas["novedades"]) >= 3
    texto = " ".join(notas["novedades"])
    assert "OpenVPN" in texto and "SoftEther" in texto
    notas109 = notas_version.notas_de("1.0.9")
    assert notas109 is not None and len(notas109["novedades"]) >= 3
    texto109 = " ".join(notas109["novedades"])
    assert "SoftEther" in texto109 and "tarjeta virtual" in texto109
    notas108 = notas_version.notas_de("1.0.8")
    assert notas108 is not None and len(notas108["novedades"]) >= 3
    notas107 = notas_version.notas_de("1.0.7")
    assert notas107 is not None
    assert "Optimización finalizada" in " ".join(notas107["novedades"])


def test_instalador_lleva_openvpn_incorporado():
    import os

    raiz = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(raiz, "packaging", "instalador.iss"),
              encoding="utf-8") as f:
        iss = f.read()
    assert '#define AppVersion "1.0.20"' in iss  # v1.0.12: vigente
    # El payload de OpenVPN, a {app}\openvpn, y su instalación silenciosa.
    assert "openvpn\\OpenVPN-2.7.9-I002-amd64.msi" in iss
    assert "msiexec" in iss
    with open(os.path.join(raiz, ".github", "workflows",
                           "build-windows.yml"), encoding="utf-8") as f:
        yml = f.read()
    assert "OpenVPN-2.7.9-I002-amd64.msi" in yml  # descarga oficial fijada
    assert "5939200" in yml                        # tamaño verificado


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


# === 2. Servicios VPN con el motor OpenVPN (simulado) =========================

def test_servicios_conectar_vpn_usa_openvpn(monkeypatch, tmp_path):
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    monkeypatch.setattr(srv.config, "carpeta_datos", lambda: str(tmp_path))
    monkeypatch.setattr(srv.vpn_win, "openvpn_instalado", lambda: True)
    monkeypatch.setattr(
        srv.vpn_win, "conectar_openvpn",
        lambda contenido, hostname, **kw: {"ok": True, "mensaje": "",
                                           "detalle": "",
                                           "datos": {"via": "openvpn"}})

    class _Serv:
        hostname = "vpn123.opengw.net"
        pais = "Japan"
        pais_corto = "JP"

        def generar_ovpn(self):
            return "client\nremote vpn123.opengw.net 443\n"

    r = srv.conectar_vpn(_Serv())
    assert r.ok is True
    assert r.datos["conectado"] is True and r.datos["via"] == "openvpn"
    assert srv._leer_estado_vpn().get("via") == "openvpn"


def test_servicios_estado_y_desconexion_openvpn(monkeypatch, tmp_path):
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    monkeypatch.setattr(srv.config, "carpeta_datos", lambda: str(tmp_path))
    monkeypatch.setattr(srv.vpn_win, "clientes_vpn_instalados", lambda: [])
    monkeypatch.setattr(srv.vpn_win, "ip_publica_actual",
                        lambda timeout=15: "1.2.3.4")
    monkeypatch.setattr(srv.vpn_win, "hay_tunel_openvpn", lambda: False)
    monkeypatch.setattr(
        srv.vpn_win, "estado_openvpn",
        lambda: {"instalado": True, "conectado": True,
                 "hostname": "vpn123.opengw.net"})
    monkeypatch.setattr(
        srv.vpn_win, "desconectar_openvpn",
        lambda: {"ok": True, "mensaje": "", "detalle": "", "datos": {}})

    estado = srv.estado_vpn()
    assert estado.ok and estado.datos["conectada"] is True
    assert estado.datos["conectada_openvpn"] is True

    r = srv.desconectar_vpn()
    assert r.ok is True and "OpenVPN" in r.mensaje


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
