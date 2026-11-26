"""v1.0.18 — Las OCHO notas del usuario tras probar la 1.0.17.

- Nota 1: ningún trabajo en segundo plano puede elevar OpenVPN
  (cero UAC espontáneos): el lanzador con solo_servicio jamás
  toca la vía elevada y conectar_openvpn en ese modo se difiere
  en silencio si la puerta previa solo deja la elevada. La app
  nunca abre un túnel por su cuenta: el vigilante solo actúa
  sobre un túnel VISTO arriba (el que el usuario abrió).
- Nota 4: el barrido del arranque reutiliza el motor de
  «Verificar servidores» con solo_servicio y presupuesto, y el
  progreso llega a los oyentes registrados (la tabla en vivo).
- Nota 2: la descarga de la actualización lleva identidad
  propia: parcial ajeno se descarta, parcial propio se reanuda,
  huella mala se re-descarga limpia DENTRO de la misma llamada.
- Nota 3: defrag con resultado atómico, testigo de eventos y
  recaptura: la frase «sin dejar el código de salida» no puede
  salir en ningún desenlace.
- Notas 5 y 6: página de versión sin historial, página de
  historial propia, idioma arriba e icono de la app en el
  encabezado (a nivel de fuente y de datos).
- Nota 7: el espartano en el asistente de instalación (BMP y
  código Inno) y el grupo OpenVPN verificado en su script.
- Nota 8: el activo animado nuevo (640×960, 240 cuadros) — su
  decodificación con Qt la vigila test_v1017; aquí, su peso.
"""
import hashlib
import http.server
import json
import os
import threading

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _leer(ruta_rel: str) -> str:
    with open(os.path.join(RAIZ, ruta_rel), encoding="utf-8") as f:
        return f.read()


def _servidor(host, sesiones=10):
    from antivirus_hogar_pc.core.vpngate import ServidorVPN
    return ServidorVPN(
        hostname=host, ip="1.2.3.4", puntuacion=0, ping_ms=50,
        velocidad_bps=1000000, pais="Japan", pais_corto="JP",
        sesiones=sesiones, uptime=9999, total_usuarios=0,
        operador="op", mensaje="", ovpn_base64="eA==")


# --- Nota 1: cero elevación en segundo plano ---------------------------------

def test_lanzador_solo_servicio_nunca_eleva(monkeypatch):
    from antivirus_hogar_pc.winapi import vpn_win

    monkeypatch.setattr(vpn_win, "es_windows", lambda: True)
    monkeypatch.setattr(
        vpn_win, "_lanzar_por_servicio",
        lambda a, c: (_ for _ in ()).throw(
            vpn_win._ErrorServicioOpenVPN("servicio denegado")))
    elevado_llamado = []
    monkeypatch.setattr(
        vpn_win, "_lanzar_elevado",
        lambda a, c: elevado_llamado.append(True))
    with pytest.raises(vpn_win._ErrorServicioOpenVPN):
        vpn_win._lanzar_openvpn(["openvpn"], "C:\\x",
                                solo_servicio=True)
    assert elevado_llamado == []  # jamás se intentó la elevada


def test_conectar_solo_servicio_se_difiere_sin_lanzar(monkeypatch):
    from antivirus_hogar_pc.winapi import vpn_win

    monkeypatch.setattr(vpn_win, "ruta_openvpn_exe",
                        lambda: "C:\\OpenVPN\\openvpn.exe")
    monkeypatch.setattr(vpn_win, "_cerrar_intento_previo",
                        lambda: None)
    monkeypatch.setattr(vpn_win, "_barrido_huerfanos", lambda: None)
    monkeypatch.setattr(vpn_win, "_ajenos_vivos", lambda: False)
    monkeypatch.setattr(
        vpn_win, "puerta_previa_openvpn",
        lambda: {"listo": True, "via": "elevado",
                 "aviso": "sesión sin grupo", "motivo": ""})
    monkeypatch.setattr(
        vpn_win, "_lanzar_openvpn",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("no debió lanzar nada")))
    res = vpn_win.conectar_openvpn(
        "client\n", "vpn123.opengw.net", solo_servicio=True)
    assert res["ok"] is False
    assert res["datos"]["familia"] == "local"
    assert res["datos"]["diferido"] is True


def test_vigilante_no_toca_lo_que_el_usuario_no_abrio():
    from antivirus_hogar_pc.modules.net.servicios_red import (
        VigilanteVPN)

    reconexiones = []
    vigilante = VigilanteVPN(
        leer_conectada=lambda: False,
        leer_objetivo=lambda: {"hostname": "vpn1", "desde": 123.0},
        reconectar=lambda obj, ronda: reconexiones.append(ronda)
        or True)
    # La app recién abierta: hay estado guardado pero el túnel
    # nunca se vio arriba en esta sesión → no se reconecta nada.
    assert vigilante.ciclo() == "esperando"
    assert reconexiones == []


def test_arranque_vpn_fondo_barrido_solo_servicio(monkeypatch):
    from antivirus_hogar_pc.core import fuentes_vpn as fuentes
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    monkeypatch.setattr(srv, "_cargar_estado_fuentes", lambda: None)
    monkeypatch.setattr(srv, "_ULTIMA_LISTA", [_servidor("a.jp")])
    monkeypatch.setattr(fuentes, "leer_estado_refresco",
                        lambda ruta: {})
    monkeypatch.setattr(fuentes, "toca_refrescar",
                        lambda ahora, estado: False)
    capturado = {}

    class _Res:
        datos = {"comprobados": 1, "total": 1}
        mensaje = "Verificación terminada."

    def _verificar(**kw):
        capturado.update(kw)
        return _Res()

    monkeypatch.setattr(srv, "verificar_todos_los_servidores",
                        _verificar)
    salida = srv.arranque_vpn_fondo(presupuesto_s=321.0)
    assert capturado["solo_servicio"] is True
    assert capturado["presupuesto_s"] == 321.0
    assert salida["refresco"] is False
    assert salida["verificacion"]["comprobados"] == 1


# --- Nota 4: oyentes del barrido ----------------------------------------------

def test_barrido_avisa_a_los_oyentes_y_solo_servicio(monkeypatch):
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    lista = [_servidor("a.jp"), _servidor("b.jp")]
    monkeypatch.setattr(srv, "_ULTIMA_LISTA", lista)
    monkeypatch.setattr(srv, "_VEREDICTOS", {})
    monkeypatch.setattr(srv, "_cargar_estado_fuentes", lambda: None)
    monkeypatch.setattr(srv, "_ocupado_vpn", lambda: False)
    modos = []
    monkeypatch.setattr(
        srv, "_sondear_uno",
        lambda s, solo_servicio=False: modos.append(solo_servicio)
        or "verificado")
    avisos = []
    oyente = lambda *v: avisos.append(v)  # noqa: E731
    srv.registrar_oyente_verificacion(oyente)
    try:
        res = srv.verificar_todos_los_servidores(solo_servicio=True)
    finally:
        srv.desregistrar_oyente_verificacion(oyente)
    assert modos == [True, True]          # las sondas, solo servicio
    assert res.datos["verificados"] == 2
    assert avisos and avisos[-1][0] == 2  # progreso hasta el final


# --- Nota 2: actualización en un solo clic -------------------------------------

_CONTENIDO_BUENO = b"INSTALADOR-VALIDO-" + bytes(range(256)) * 40
_HUELLA_BUENA = hashlib.sha256(_CONTENIDO_BUENO).hexdigest()


class _ManejadorCanal(http.server.BaseHTTPRequestHandler):
    """Canal de mentira: apoya Range; puede servir mal la 1ª vez."""
    servir_mal_primero = False
    peticiones: list = []

    def log_message(self, *a):  # silencio
        pass

    def do_GET(self):  # noqa: N802
        type(self).peticiones.append(self.headers.get("Range"))
        cuerpo = _CONTENIDO_BUENO
        if type(self).servir_mal_primero and \
                len(type(self).peticiones) == 1:
            cuerpo = b"X" * len(_CONTENIDO_BUENO)  # huella mala
        rango = self.headers.get("Range")
        if rango:
            inicio = int(rango.split("=")[1].split("-")[0])
            if inicio >= len(cuerpo):
                self.send_response(416)
                self.end_headers()
                return
            trozo = cuerpo[inicio:]
            self.send_response(206)
            self.send_header("Content-Length", str(len(trozo)))
            self.send_header(
                "Content-Range",
                f"bytes {inicio}-{len(cuerpo) - 1}/{len(cuerpo)}")
            self.end_headers()
            self.wfile.write(trozo)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)


@pytest.fixture()
def canal(tmp_path):
    _ManejadorCanal.peticiones = []
    _ManejadorCanal.servir_mal_primero = False
    servidor = http.server.HTTPServer(
        ("127.0.0.1", 0), _ManejadorCanal)
    hilo = threading.Thread(target=servidor.serve_forever,
                            daemon=True)
    hilo.start()
    url = f"http://127.0.0.1:{servidor.server_port}/inst.exe"
    yield url, tmp_path
    servidor.shutdown()


def test_descarga_actualizacion_directa(canal):
    from antivirus_hogar_pc.core import updater

    url, carpeta = canal
    ruta = updater.descargar_actualizacion(
        url, _HUELLA_BUENA, "1.0.18", str(carpeta))
    with open(ruta, "rb") as f:
        assert f.read() == _CONTENIDO_BUENO


def test_huella_mala_se_redescarga_dentro_del_mismo_clic(canal):
    from antivirus_hogar_pc.core import updater

    url, carpeta = canal
    _ManejadorCanal.servir_mal_primero = True
    ruta = updater.descargar_actualizacion(
        url, _HUELLA_BUENA, "1.0.18", str(carpeta))
    with open(ruta, "rb") as f:
        assert f.read() == _CONTENIDO_BUENO
    # Hubo re-descarga: más de una petición completa.
    assert len(_ManejadorCanal.peticiones) >= 2


def test_parcial_ajeno_se_descarta_no_se_reanuda(canal):
    from antivirus_hogar_pc.core import updater

    url, carpeta = canal
    parcial = updater._ruta_parcial(str(carpeta), "1.0.18")
    with open(parcial, "wb") as f:
        f.write(b"BASURA-DE-OTRA-VERSION" * 500)  # más largo que el bueno
    updater._guardar_identidad(parcial, url, "0" * 64, "9.9.9")
    ruta = updater.descargar_actualizacion(
        url, _HUELLA_BUENA, "1.0.18", str(carpeta))
    with open(ruta, "rb") as f:
        assert f.read() == _CONTENIDO_BUENO
    # Nunca se pidió Range desde la basura ajena.
    assert all(r is None for r in _ManejadorCanal.peticiones)


def test_parcial_propio_se_reanuda(canal):
    from antivirus_hogar_pc.core import updater

    url, carpeta = canal
    parcial = updater._ruta_parcial(str(carpeta), "1.0.18")
    with open(parcial, "wb") as f:
        f.write(_CONTENIDO_BUENO[:400])  # corte a mitad (hotspot)
    updater._guardar_identidad(parcial, url, _HUELLA_BUENA, "1.0.18")
    ruta = updater.descargar_actualizacion(
        url, _HUELLA_BUENA, "1.0.18", str(carpeta))
    with open(ruta, "rb") as f:
        assert f.read() == _CONTENIDO_BUENO
    assert _ManejadorCanal.peticiones[0] == "bytes=400-"


def test_huella_imposible_levanta_error_de_huella(canal):
    from antivirus_hogar_pc.core import updater

    url, carpeta = canal
    with pytest.raises(updater.ErrorHuellaActualizacion):
        updater.descargar_actualizacion(
            url, "f" * 64, "1.0.18", str(carpeta))


# --- Nota 3: veredicto de defrag con testigo -----------------------------------

_FRASE_ELIMINADA = "sin dejar el código de salida"


def test_defrag_sin_codigo_manda_el_evento_exito():
    from antivirus_hogar_pc.winapi.disks import (
        interpretar_resultado_defrag)

    eventos = [{"mensaje": "Defragmentation of the volume (C:) "
                           "successfully completed."}]
    res = interpretar_resultado_defrag(
        "PRECHECK=SIN_RESULTADO\n", "", "C", "TRIM",
        eventos=eventos)
    assert res["ok"] is True
    assert res["mensaje"].startswith("Optimización finalizada")


def test_defrag_sin_codigo_manda_el_evento_fallo():
    from antivirus_hogar_pc.winapi.disks import (
        interpretar_resultado_defrag)

    eventos = [{"mensaje": "Unable to complete optimization "
                           "on (C:): the disk is locked."}]
    res = interpretar_resultado_defrag(
        "PRECHECK=OK\nEXITCODE=SIN_CODIGO\n", "", "C", "TRIM",
        eventos=eventos)
    assert res["ok"] is False
    assert "registro de eventos" in res["mensaje"]


def test_defrag_sin_evidencia_se_marca_para_recaptura():
    from antivirus_hogar_pc.winapi.disks import (
        interpretar_resultado_defrag)

    res = interpretar_resultado_defrag(
        "PRECHECK=SIN_RESULTADO\n", "", "C", "TRIM", eventos=[])
    assert res["ok"] is False
    assert res.get("sin_evidencia") is True
    assert _FRASE_ELIMINADA not in res["mensaje"]


def test_defrag_matriz_sin_la_frase_eliminada():
    from antivirus_hogar_pc.winapi.disks import (
        interpretar_resultado_defrag)

    entradas = [
        ("", ""), ("PRECHECK=OK\n", ""),
        ("PRECHECK=SIN_RESULTADO\n", "ruido\n"),
        ("PRECHECK=OK\nEXITCODE=SIN_CODIGO\n", ""),
        ("PRECHECK=ERROR_SCRIPT\nERROR=boom\n", ""),
        ("EXITCODE=\n", ""), ("basura\n", ""),
        ("PRECHECK=OK\nEXITCODE=5\n", "Access denied.\n"),
        ("PRECHECK=OK\nEXITCODE=0\n", ""),
    ]
    for resultado, salida in entradas:
        for eventos in (None, [], [{"mensaje": "otro volumen (D:) "
                                               "successfully "
                                               "completed."}]):
            res = interpretar_resultado_defrag(
                resultado, salida, "C", "TRIM", eventos=eventos)
            assert _FRASE_ELIMINADA not in res["mensaje"], (
                resultado, eventos, res)


def test_script_defrag_atomico_y_error_a_su_archivo():
    from antivirus_hogar_pc.winapi.disks import _script_defrag

    script = _script_defrag("C", True, "X:\\salida.txt",
                            "X:\\res.txt")
    assert "Move-Item" in script and ".tmp" in script  # atómico
    assert "-RedirectStandardError $salidaErr" in script
    assert "$salida.err" not in script  # el bug de la 1.0.15
    assert "EXITCODE=SIN_CODIGO" in script


# --- Notas 5 y 6: páginas y carcasa ---------------------------------------------

def test_pagina_version_sin_historial_e_historial_propia():
    fuente_version = _leer("antivirus_hogar_pc/ui/version_page.py")
    assert "Historial reciente" not in fuente_version
    assert "import NOTAS_VERSION" not in fuente_version
    fuente_historial = _leer(
        "antivirus_hogar_pc/ui/historial_page.py")
    assert "NOTAS_VERSION" in fuente_historial
    assert "crear_pagina_historial" in fuente_historial


def test_historial_completo_en_los_datos():
    from antivirus_hogar_pc.core.notas_version import NOTAS_VERSION

    versiones = [e["version"] for e in NOTAS_VERSION]
    assert versiones[0] == "1.0.18"
    for esperada in ("1.0.2", "1.0.7", "1.0.10", "1.0.14",
                     "1.0.17", "1.0.18"):
        assert esperada in versiones
    assert all(e["novedades"] for e in NOTAS_VERSION)


def test_carcasa_idioma_arriba_icono_e_historial_al_final():
    fuente = _leer("antivirus_hogar_pc/ui/main_window.py")
    # El idioma se construye ANTES del bucle de botones de módulo.
    assert fuente.index("_combo_idioma = QComboBox()") < \
        fuente.index("for _i, registro in enumerate")
    # El encabezado usa el icono de la aplicación.
    assert "icono_app.png" in fuente
    # «Historial» existe como página fija y en la retraducción.
    assert 'ir_a("historial")' in fuente
    assert "crear_pagina_historial" in fuente
    assert os.path.isfile(os.path.join(
        RAIZ, "antivirus_hogar_pc", "assets", "icono_app.png"))


# --- Nota 7: instalador -----------------------------------------------------------

def test_interno_iss_espartano_y_bmp_valido():
    iss = _leer("packaging/instalador.iss")
    assert "espartano_instalador.bmp" in iss
    assert "dontcopy" in iss
    assert "InitializeWizard" in iss
    assert "InstallingPage" in iss
    ruta_bmp = os.path.join(RAIZ, "packaging",
                            "espartano_instalador.bmp")
    with open(ruta_bmp, "rb") as f:
        cabecera = f.read(26)
    assert cabecera[:2] == b"BM"
    import struct
    ancho, alto = struct.unpack("<ii", cabecera[18:26])
    assert (ancho, alto) == (509, 746)


def test_grupo_openvpn_verifica_tras_agregar():
    ps1 = _leer("packaging/grupo_openvpn.ps1")
    assert "EsMiembro" in ps1
    assert "VERIFICADO" in ps1
    assert "net localgroup" in ps1          # vía de respaldo
    assert "StartupType Automatic" in ps1  # servicio automático


# --- Nota 8: peso del activo nuevo -------------------------------------------------

def test_activo_animado_nuevo_peso_coherente():
    ruta = os.path.join(
        RAIZ, "antivirus_hogar_pc", "assets",
        "espartano_animado.webp")
    tamano = os.path.getsize(ruta)
    # 640×960 a 24 fps q85: ~40 MB (la 1.0.17 pesaba ~10 MB a
    # 440×660/12 fps). Fuera de esta banda, algo se desvió.
    assert 30_000_000 < tamano < 50_000_000


def test_version_1018_en_json_del_canal_no_tocado():
    # El canal lo publica la entrega, no el código: config solo
    # lleva la versión de la app.
    from antivirus_hogar_pc import config

    assert config.VERSION == "1.0.18"
    json.dumps({"version": config.VERSION})  # serializable
