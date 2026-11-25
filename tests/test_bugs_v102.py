"""Tests de los DOS BUGS de la v1.0.1 corregidos en la v1.0.2:

1. «Buscar actualizaciones» siempre decía «revisa tu conexión» porque el
   version-pc.json nunca se publicó (id marcador). Ahora: canal REAL
   publicado en Drive y errores clasificados por causa.
2. VPN sin países: la lista solo se descargaba a mano y un fallo la
   dejaba vacía en silencio. Ahora: carga automática, combo y tabla se
   pueblan, error visible con causa y reintento, e interruptor general
   con «Desconectar VPN».

Lo de Qt se prueba con plataforma offscreen y se salta si PySide6 no
está (en la VM de desarrollo no está; en el runner de Actions sí).
"""
import io
import urllib.error

import pytest

from antivirus_hogar_pc import config
from antivirus_hogar_pc.core import updater
from antivirus_hogar_pc.core.vpngate import paises_disponibles, parsear_csv_vpngate

# --- Bug 1: clasificación de errores del canal ---------------------------------

def _fake_urlopen_error(exc):
    def _abrir(req, timeout=None):
        raise exc
    return _abrir


def test_canal_404_es_no_encontrado(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen_error(urllib.error.HTTPError("u", 404, "Not Found", {}, None)))
    with pytest.raises(updater.ErrorActualizacion) as e:
        updater.comprobar_actualizacion("https://ejemplo/version-pc.json", "1.0.1")
    assert e.value.tipo == "no_encontrado"


def test_canal_sin_red_es_sin_conexion(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen_error(urllib.error.URLError("sin red")))
    with pytest.raises(updater.ErrorActualizacion) as e:
        updater.comprobar_actualizacion("https://ejemplo/version-pc.json", "1.0.1")
    assert e.value.tipo == "sin_conexion"


def test_canal_json_roto_es_respuesta_invalida(monkeypatch):
    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=None: _Resp(b"<html>no es json</html>"))
    with pytest.raises(updater.ErrorActualizacion) as e:
        updater.comprobar_actualizacion("https://ejemplo/version-pc.json", "1.0.1")
    assert e.value.tipo == "respuesta_invalida"


def test_mensajes_del_servicio_distinguen_la_causa(monkeypatch):
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    class _Ajustes:
        url_actualizacion = "https://ejemplo/version-pc.json"
        ultimo_chequeo_actualizacion = 0.0

        def guardar(self):
            pass

    def _falla(tipo):
        def _comprobar(url, version):
            raise updater.ErrorActualizacion(tipo, "detalle de prueba")
        return _comprobar

    monkeypatch.setattr(srv.updater, "comprobar_actualizacion", _falla("no_encontrado"))
    r = srv.comprobar_actualizacion_app(_Ajustes())
    assert not r.ok and "no encontrado" in r.mensaje and "conexión" in r.mensaje

    monkeypatch.setattr(srv.updater, "comprobar_actualizacion", _falla("sin_conexion"))
    r = srv.comprobar_actualizacion_app(_Ajustes())
    assert not r.ok and "no hay conexión" in r.mensaje


def test_url_configurada_responde_y_parsea_en_vivo():
    """Contra el archivo REAL de Drive: la URL de config debe responder
    y parsear como version-pc.json (esto era imposible con el marcador)."""
    assert "Pendiente" not in config.UPDATE_VERSION_URL
    texto = updater.descargar_texto(config.UPDATE_VERSION_URL)
    info = updater.parsear_version_json(texto)
    assert info.version  # trae versión
    assert updater.comprobar_actualizacion(
        config.UPDATE_VERSION_URL, "0.0.0") is not None  # hay info válida


# --- Bug 2 / A: parseo del CSV de VPN Gate ---------------------------------------

_CSV_MUESTRA = """*vpn_servers
#HostName,IP,Score,Ping,Speed,CountryLong,CountryShort,NumVpnSessions,Uptime,TotalUsers,TotalTraffic,LogType,Operator,Message,OpenVPNConfigData_Base64
*vpn_servers
public-vpn-001.opengw.net,219.100.37.1,1000,15,50000000,Japan,JP,3,100000,10,1000000,2weeks,voluntario,msg1,Y2xpZW50Cg==
public-vpn-002.opengw.net,219.100.37.2,900,25,30000000,Japan,JP,5,90000,8,900000,2weeks,voluntario,msg2,Y2xpZW50Cg==
vpn-us-003.opengw.net,50.10.20.30,800,90,80000000,United States,US,12,80000,20,800000,2weeks,voluntario,msg3,Y2xpZW50Cg==
*
"""


def test_parseo_csv_vpngate_muestra():
    servidores = parsear_csv_vpngate(_CSV_MUESTRA)
    assert len(servidores) == 3
    assert paises_disponibles(servidores) == ["Japan", "United States"]
    s = servidores[0]
    assert s.hostname == "public-vpn-001.opengw.net"
    assert s.pais == "Japan" and s.ping_ms == 15 and s.sesiones == 3
    assert s.velocidad_mbps == 50.0


def test_pagina_vpn_puebla_combo_tabla_y_botones():
    """La página real (offscreen): al entregarle la lista parseada, el
    combo de países se llena, la tabla pinta las filas con sus datos y
    CADA fila lleva su botón «Conectar»."""
    pytest.importorskip("PySide6")
    import os as _os

    _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QPushButton

    from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo
    from antivirus_hogar_pc.modules.net.fake import servidores_fake
    from antivirus_hogar_pc.modules.net.page import _PaginaRed

    app = QApplication.instance() or QApplication([])
    pagina = _PaginaRed(ContextoModulo(servicios=None))
    servidores = servidores_fake()
    pagina._servidores_cargados(ResultadoModulo(ok=True, datos=servidores))

    textos_combo = [pagina._combo_pais.itemText(i)
                    for i in range(pagina._combo_pais.count())]
    assert "Japan" in textos_combo and "United States" in textos_combo

    tabla = pagina._tabla_vpn
    assert tabla.rowCount() == 2
    assert tabla.item(0, 0).text() == "Japan"
    assert tabla.item(0, 1).text() == "vpn123456789.opengw.net"
    assert tabla.item(0, 3).text() == "18 ms"
    for fila in range(2):
        # v1.0.9: la celda de acción es un contenedor con los botones.
        celda = tabla.cellWidget(fila, 5)
        botones = celda.findChildren(QPushButton)
        assert len(botones) == 1 and botones[0].text() == "Conectar"
    pagina.deleteLater()
    app.processEvents()


def test_pagina_vpn_error_visible_y_reintento():
    pytest.importorskip("PySide6")
    import os as _os

    _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo
    from antivirus_hogar_pc.modules.net.page import _PaginaRed

    app = QApplication.instance() or QApplication([])
    pagina = _PaginaRed(ContextoModulo(servicios=None))
    pagina._servidores_cargados(ResultadoModulo(
        ok=False, mensaje="No se pudo descargar… Causa: sin red."))
    assert "Causa" in pagina._lbl_vpn.text()
    assert pagina._btn_servidores.text() == "Reintentar descarga"
    pagina.deleteLater()
    app.processEvents()


# --- B: estado sí/no y desconexión con el backend simulado ------------------------

class _ServidorFalso:
    hostname = "vpn123456789.opengw.net"
    pais = "Japan"


def _preparar(monkeypatch, tmp_path):
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    monkeypatch.setattr(srv.config, "carpeta_datos", lambda: str(tmp_path))
    return srv


def test_estado_vpn_conectada_y_desconexion(monkeypatch, tmp_path):
    srv = _preparar(monkeypatch, tmp_path)
    monkeypatch.setattr(srv.vpn_win, "clientes_vpn_instalados", lambda: [])
    monkeypatch.setattr(srv.vpn_win, "ip_publica_actual", lambda timeout=15: "1.2.3.4")
    monkeypatch.setattr(srv.vpn_win, "hay_tunel_openvpn", lambda: True)
    cerrados = {"n": 0}

    def _terminar():
        cerrados["n"] = 1
        return 1

    monkeypatch.setattr(srv.vpn_win, "terminar_procesos_openvpn", _terminar)

    srv._guardar_estado_vpn(_ServidorFalso())
    estado = srv.estado_vpn()
    assert estado.ok and estado.datos["conectada"] is True
    assert estado.datos["servidor"] == "vpn123456789.opengw.net"
    assert estado.datos["pais"] == "Japan"

    r = srv.desconectar_vpn()
    assert r.ok and cerrados["n"] == 1
    assert srv._leer_estado_vpn() == {}  # el estado quedó limpio

    monkeypatch.setattr(srv.vpn_win, "hay_tunel_openvpn", lambda: False)
    estado2 = srv.estado_vpn()
    assert estado2.datos["conectada"] is False


def test_desconectar_sin_nada_activo(monkeypatch, tmp_path):
    srv = _preparar(monkeypatch, tmp_path)
    monkeypatch.setattr(srv.vpn_win, "terminar_procesos_openvpn", lambda: 0)
    r = srv.desconectar_vpn()
    assert not r.ok and "SoftEther" in r.mensaje
