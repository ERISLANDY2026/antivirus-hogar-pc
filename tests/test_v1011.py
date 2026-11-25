"""v1.0.11 — Arreglo del fallo VPN de la 1.0.10 (diagnóstico cerrado
en INVESTIGACION-VPN-V1010.md, confirmado en la Toughbook del
usuario):

1. LA CAUSA: `preparar_perfil_vpngate` escribía la ruta de
   credenciales en `auth-user-pass` con barras SIMPLES; OpenVPN
   2.7.9 lo trata como error FATAL de opciones («Bad backslash»,
   options_parse.c/parse_line con nivel M_USAGE → usage_small →
   exit) y muere al parsear el perfil, ANTES de abrir su
   --log-append: muerte instantánea, cero log, cero detalle, con
   todos los servidores. Aquí: la ruta sale ESCAPADA con barras
   dobles y una guarda reproduce el perfil real de 221 líneas de
   VPN Gate verificando que la línea añadida (la 221) queda
   escapada y sin ninguna barra simple «desnuda».
2. Estado honesto: «conectada» SOLO con CONNECTED,SUCCESS de la
   interfaz de gestión; fuera la detección por subcadena de
   procesos (openvpn-gui/openvpnserv ya no cuentan); la sesión
   nace «conectando»; en timeout se mata el proceso y se borra
   la sesión.
3. Nunca más un fallo sin causa: la salida de arranque de
   openvpn.exe se captura (no más DEVNULL sin red) y su código de
   salida se guarda; si muere antes del registro, esa salida ES
   la causa. El clasificador conoce el error de opciones, DCO y
   el servicio interactivo; «apagado o saturado» solo para red/
   TLS; causa vacía declarada como tal. El detalle técnico se
   PINTA en la página de Red y VPN.
4. El registro rota por intento (fecha/hora, últimos 5) sin
   borrar el anterior, y sus últimas líneas completas van al
   detalle y al registro de actividad.
"""
import os
import re
import time

import pytest

RAIZ = os.path.join(os.path.dirname(__file__), "..")


def _leer(ruta_relativa: str) -> str:
    with open(os.path.join(RAIZ, ruta_relativa), encoding="utf-8") as f:
        return f.read()


# === 0. Versión vigente =========================================================

def test_version_vigente_1011():
    from antivirus_hogar_pc import config
    from antivirus_hogar_pc.core import notas_version

    assert config.VERSION == "1.0.13"
    assert notas_version.NOTAS_VERSION[0]["version"] == "1.0.13"
    notas = notas_version.notas_de("1.0.13")
    assert notas is not None and len(notas["novedades"]) >= 3
    iss = _leer(os.path.join("packaging", "instalador.iss"))
    assert '#define AppVersion "1.0.13"' in iss


# === 1. LA CAUSA: la ruta escapada ==============================================

_PERFIL_221 = "\n".join(
    ["client", "dev tun", "proto tcp", "remote 203.0.113.7 443",
     "cipher AES-128-CBC", "data-ciphers AES-128-CBC", "auth SHA1",
     "resolv-retry infinite", "nobind", "persist-key", "persist-tun",
     "verb 3", "<ca>", "-----BEGIN CERTIFICATE-----", "MIIfalso",
     "-----END CERTIFICATE-----", "</ca>", "<cert>",
     "-----BEGIN CERTIFICATE-----", "MIIfalso",
     "-----END CERTIFICATE-----", "</cert>", "<key>",
     "-----BEGIN PRIVATE KEY-----", "MIIfalso",
     "-----END PRIVATE KEY-----"]
    + ["# relleno del perfil real"] * 193 + ["</key>"]) + "\n\n"


def test_perfil_real_221_lineas_y_linea_escapada():
    """Reproduce el perfil real de VPN Gate (221 líneas con la
    última vacía): la línea que añade la app cae en la 221 y debe
    quedar con barras DOBLES — ninguna barra simple «desnuda» que
    OpenVPN pueda leer como escape."""
    from antivirus_hogar_pc.winapi.vpn_win import preparar_perfil_vpngate

    ruta = (r"C:\Users\NEW USER\AppData\Local\AntivirusHogarPC\vpn"
            r"\vpngate-credenciales.txt")
    salida = preparar_perfil_vpngate(_PERFIL_221, ruta)
    lineas = salida.splitlines()
    assert len(lineas) == 221
    assert lineas[219] == "</key>"
    esperada = 'auth-user-pass "' + ruta.replace("\\", "\\\\") + '"'
    assert lineas[220] == esperada
    # Sin barras simples desnudas: al quitar los pares «\\» no
    # puede quedar ninguna «\» (eso es lo que parse_line rechaza).
    sin_pares = lineas[220].replace("\\\\", "")
    assert "\\" not in sin_pares
    assert not re.search(r'(?<!\\)\\(?!\\)', lineas[220])


def test_preparar_perfil_ruta_sin_espacios_tambien_escapada():
    from antivirus_hogar_pc.winapi.vpn_win import preparar_perfil_vpngate

    salida = preparar_perfil_vpngate("client\ndev tun\n", r"C:\d\c.txt")
    assert 'auth-user-pass "C:\\\\d\\\\c.txt"' in salida


# === 2. Estado honesto ===========================================================

def test_filtro_procesos_solo_el_exe_del_tunel():
    from antivirus_hogar_pc.winapi.vpn_win import _filtrar_procesos_openvpn

    infos = [
        {"pid": 1, "name": "openvpn.exe"},
        {"pid": 2, "name": "openvpn-gui.exe"},
        {"pid": 3, "name": "openvpnserv.exe"},
        {"pid": 4, "name": "openvpnserv2.exe"},
        {"pid": 5, "name": "OpenVPNConnect.exe"},
        {"pid": 6, "name": "chrome.exe"},
        {"pid": 7, "name": None},
    ]
    assert _filtrar_procesos_openvpn(infos) == [
        {"pid": 1, "nombre": "openvpn.exe"}]


def _sesion_falsa(monkeypatch, tmp_path, estado_mgmt):
    from antivirus_hogar_pc.winapi import vpn_win

    carpeta = tmp_path / "vpn"
    carpeta.mkdir(exist_ok=True)
    monkeypatch.setattr(vpn_win, "ruta_openvpn_exe",
                        lambda: r"C:\Program Files\OpenVPN\bin\openvpn.exe")
    monkeypatch.setattr(vpn_win, "carpeta_perfiles_vpn",
                        lambda: str(carpeta))
    monkeypatch.setattr(vpn_win, "_mgmt_enviar",
                        lambda puerto, comando, timeout=10: estado_mgmt)
    # Aunque haya procesos «openvpn» vivos, ya no prueban nada.
    monkeypatch.setattr(vpn_win, "hay_tunel_openvpn", lambda: True)
    vpn_win._guardar_sesion({"hostname": "vpn123.opengw.net",
                             "puerto": 12345, "pid": 999,
                             "estado": "conectando"})
    return vpn_win


def test_estado_sin_confirmacion_no_es_conectado(monkeypatch, tmp_path):
    vpn_win = _sesion_falsa(
        monkeypatch, tmp_path,
        "1732464000,RECONNECTING,auth-failure,,,,,\r\nEND\r\n")
    estado = vpn_win.estado_openvpn()
    assert estado["conectado"] is False       # ← el falso de la foto
    assert estado["conectando"] is True
    assert estado["hostname"] == "vpn123.opengw.net"


def test_estado_confirmado_por_la_interfaz(monkeypatch, tmp_path):
    vpn_win = _sesion_falsa(
        monkeypatch, tmp_path,
        "1732464000,CONNECTED,SUCCESS,10.211.1.5,203.0.113.7,443,,\r\n"
        "END\r\n")
    estado = vpn_win.estado_openvpn()
    assert estado["conectado"] is True
    assert estado["conectando"] is False


def test_estado_vpn_servicio_solo_openvpn_confirmado(monkeypatch, tmp_path):
    """En la capa de servicios: proceso vivo SIN confirmación del
    motor ya no marca «conectada» (el interruptor de la foto)."""
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    monkeypatch.setattr(srv.config, "carpeta_datos", lambda: str(tmp_path))
    monkeypatch.setattr(srv.vpn_win, "clientes_vpn_instalados", lambda: [])
    monkeypatch.setattr(srv.vpn_win, "ip_publica_actual",
                        lambda timeout=15: "1.2.3.4")
    monkeypatch.setattr(srv.vpn_win, "hay_tunel_openvpn", lambda: True)
    monkeypatch.setattr(
        srv.vpn_win, "estado_openvpn",
        lambda: {"instalado": True, "conectado": False, "hostname": ""})
    estado = srv.estado_vpn()
    assert estado.datos["conectada"] is False
    assert estado.datos["conectada_openvpn"] is False


# === 3. Nunca más un fallo sin causa =============================================

class _ProcesoMuerto:
    def __init__(self, codigo=1):
        self.pid = 777
        self.returncode = codigo

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        pass


class _ProcesoVivo:
    def __init__(self):
        self.pid = 778
        self.returncode = None
        self.terminado = False

    def poll(self):
        return None

    def wait(self, timeout=None):
        return 0

    def terminate(self):
        self.terminado = True
        self.returncode = -15

    def kill(self):
        self.terminado = True


_PERFIL_SIMPLE = "client\ndev tun\nproto udp\nremote vpn123 1194\n"


def _motor_muerto(monkeypatch, tmp_path, proceso, salida_arranque="",
                  log=""):
    from antivirus_hogar_pc.winapi import vpn_win

    carpeta = tmp_path / "vpn"
    carpeta.mkdir(exist_ok=True)
    monkeypatch.setattr(vpn_win, "ruta_openvpn_exe",
                        lambda: r"C:\Program Files\OpenVPN\bin\openvpn.exe")
    monkeypatch.setattr(vpn_win, "carpeta_perfiles_vpn",
                        lambda: str(carpeta))
    monkeypatch.setattr(vpn_win, "_mgmt_enviar",
                        lambda puerto, comando, timeout=10: "")

    def falso_lanzar(argumentos, carpeta_trabajo, ruta_salida=""):
        if ruta_salida and salida_arranque:
            with open(ruta_salida, "w", encoding="utf-8") as f:
                f.write(salida_arranque)
        if log:
            ruta_log = argumentos[argumentos.index("--log-append") + 1]
            with open(ruta_log, "w", encoding="utf-8") as f:
                f.write(log)
        return proceso

    monkeypatch.setattr(vpn_win, "_lanzar_openvpn", falso_lanzar)
    vpn_win._PROCESO = None
    return vpn_win, carpeta


def test_muerte_por_opciones_se_ve_desde_la_salida_de_arranque(
        monkeypatch, tmp_path):
    """LA reproducción del fallo de la 1.0.10, bajo el contrato
    de la 1.0.13: openvpn muere al parsear (sin abrir su
    registro) y la única «causa» disponible estaría en el
    archivo de salida de arranque — pero desde la 1.0.12 las
    vías servicio/elevado lanzan con el stdout a NUL y NADIE
    escribe ese archivo: su contenido es un FÓSIL de otro
    intento y el detalle tiene prohibido servírselo al usuario
    (en la prueba real de la 1.0.12 se sirvió el fósil de las
    11:31 como si fuera el intento en curso). La muerte sin
    registro propio se declara como lo que es —«se cerró sin
    dejar registro en este intento»—, sin disfrazarla de
    «servidor apagado o saturado» y sin filtrar el fósil."""
    salida = (
        "2026-11-25 10:54:06 DEPRECATED OPTION: --persist-key option "
        "ignored.\n"
        "Options warning: Bad backslash ('\\') usage in "
        "C:\\Users\\NEW USER\\...\\vpngate-activo.ovpn:221\n"
        "Use --help for more information.\n")
    vpn_win, _c = _motor_muerto(monkeypatch, tmp_path,
                                _ProcesoMuerto(codigo=1),
                                salida_arranque=salida)
    res = vpn_win.conectar_openvpn(_PERFIL_SIMPLE, "vpn123.opengw.net",
                                   espera=5)
    assert res["ok"] is False
    assert "sin dejar registro" in res["mensaje"]
    assert "saturado" not in res["mensaje"]
    assert res["datos"]["codigo_salida"] == 1
    # El fósil NO se filtra: ni su marca en el detalle ni en el
    # mensaje (el detalle hermético tiene su propio test en la
    # suite de la 1.0.13).
    assert "Bad backslash" not in res["detalle"]
    assert "Bad backslash" not in res["mensaje"]
    # La sesión no queda: nada de «conectada» fantasma tras el fallo.
    assert vpn_win._leer_sesion() == {}


def test_muerte_sin_causa_se_declara_como_tal(monkeypatch, tmp_path):
    vpn_win, _c = _motor_muerto(monkeypatch, tmp_path,
                                _ProcesoMuerto(codigo=-1073741515))
    res = vpn_win.conectar_openvpn(_PERFIL_SIMPLE, "vpn123.opengw.net",
                                   espera=5)
    assert res["ok"] is False
    assert "sin dejar registro" in res["mensaje"]
    assert "-1073741515" in res["mensaje"]
    assert "saturado" not in res["mensaje"]
    assert res["datos"]["codigo_salida"] == -1073741515


def test_muerte_por_red_si_es_servidor_saturado(monkeypatch, tmp_path):
    log = ("2026-11-25 10:00:00 Connection reset, restarting [0]\n"
           "2026-11-25 10:00:01 Exiting due to fatal error\n")
    vpn_win, _c = _motor_muerto(monkeypatch, tmp_path,
                                _ProcesoMuerto(codigo=1), log=log)
    res = vpn_win.conectar_openvpn(_PERFIL_SIMPLE, "vpn123.opengw.net",
                                   espera=5)
    assert res["ok"] is False
    assert "saturado" in res["mensaje"]  # solo AQUÍ vale ese texto
    assert "Connection reset" in res["detalle"]


def test_timeout_mata_el_proceso_y_borra_la_sesion(monkeypatch, tmp_path):
    proceso = _ProcesoVivo()
    vpn_win, _c = _motor_muerto(monkeypatch, tmp_path, proceso)
    res = vpn_win.conectar_openvpn(_PERFIL_SIMPLE, "vpn123.opengw.net",
                                   espera=5)
    assert res["ok"] is False
    assert "no se confirmó a tiempo" in res["mensaje"]
    assert proceso.terminado is True          # nada de huérfanos
    assert vpn_win._PROCESO is None
    assert vpn_win._leer_sesion() == {}


def test_clasificador_familias_nuevas():
    from antivirus_hogar_pc.winapi.vpn_win import _clasificar_fallo_openvpn

    m, _d = _clasificar_fallo_openvpn(
        "Cannot open TUN/TAP device: ovpn-dco error", 1, "h")
    assert "tarjeta virtual" in m
    m, _d = _clasificar_fallo_openvpn(
        "Failed to connect to the interactive service", 1, "h")
    assert "Interactive Service" in m
    m, _d = _clasificar_fallo_openvpn("VERIFY ERROR: depth=0", 1, "h")
    assert "TLS" in m
    m, _d = _clasificar_fallo_openvpn("", 2, "h")
    assert "sin dejar registro" in m and "2" in m


# === 4. Registro por intento, sin borrar =========================================

def test_rotacion_del_registro(tmp_path):
    from antivirus_hogar_pc.winapi import vpn_win

    ruta = tmp_path / "openvpn-conexion.log"
    ruta.write_text("intento viejo\n", encoding="utf-8")
    rotado = vpn_win._rotar_registro_openvpn(str(ruta))
    assert rotado and os.path.isfile(rotado)
    assert not ruta.exists()
    assert "intento viejo" in open(rotado, encoding="utf-8").read()
    # Sin registro no rota nada y no falla.
    assert vpn_win._rotar_registro_openvpn(str(ruta)) == ""


def test_rotacion_conserva_solo_los_ultimos_5(tmp_path):
    from antivirus_hogar_pc.winapi import vpn_win

    for i in range(6):
        f = tmp_path / f"openvpn-conexion-2026010{i}-000000.log"
        f.write_text(f"rotado {i}\n", encoding="utf-8")
        os.utime(f, (1_700_000_000 + i * 100, 1_700_000_000 + i * 100))
    ruta = tmp_path / "openvpn-conexion.log"
    ruta.write_text("actual\n", encoding="utf-8")
    os.utime(ruta, (1_700_001_000, 1_700_001_000))
    vpn_win._rotar_registro_openvpn(str(ruta))
    rotados = [n for n in os.listdir(tmp_path)
               if n.startswith("openvpn-conexion-")]
    assert len(rotados) == 5


def test_intento_nuevo_rota_el_registro_anterior(monkeypatch, tmp_path):
    vpn_win, carpeta = _motor_muerto(monkeypatch, tmp_path,
                                     _ProcesoMuerto(codigo=1))
    anterior = carpeta / "openvpn-conexion.log"
    anterior.write_text("causa del intento anterior\n", encoding="utf-8")
    vpn_win.conectar_openvpn(_PERFIL_SIMPLE, "vpn123.opengw.net", espera=5)
    rotados = [n for n in os.listdir(carpeta)
               if n.startswith("openvpn-conexion-")]
    assert len(rotados) == 1  # el anterior sigue ahí, con su fecha


def test_ultimas_lineas_completas_al_registro_de_actividad(
        monkeypatch, tmp_path):
    """La capa de servicios vuelca las últimas líneas del registro
    de OpenVPN en actividad.jsonl, no solo la línea elegida."""
    from antivirus_hogar_pc.modules.net import servicios_red as srv
    from antivirus_hogar_pc.core.vpngate import ServidorVPN

    monkeypatch.setattr(srv.config, "carpeta_datos", lambda: str(tmp_path))
    monkeypatch.setattr(srv.vpn_win, "openvpn_instalado", lambda: True)
    ultimas = ("línea uno del registro\n"
               "Options warning: Bad backslash usage\n"
               "Use --help for more information.")
    monkeypatch.setattr(
        srv.vpn_win, "conectar_openvpn",
        lambda contenido, hostname: {
            "ok": False, "mensaje": "fallo de opciones",
            "detalle": "Options warning: Bad backslash usage",
            "datos": {"ultimas_lineas": ultimas,
                      "codigo_salida": 1}})
    registradas = []
    monkeypatch.setattr(srv, "_registrar_intento_vpn",
                        lambda detalle: registradas.append(detalle))
    servidor = ServidorVPN("vpn123.opengw.net", "203.0.113.7", 1, 1, 1,
                           "Japan", "JP", 1, 1, 1, "", "", "")
    r = srv.conectar_vpn(servidor)
    assert r.ok is False
    assert r.detalle_tecnico  # el detalle viaja a la página
    assert registradas and "línea uno del registro" in registradas[0]
    assert "Bad backslash" in registradas[0]


# === 5. El detalle técnico SE PINTA en la página =================================

def test_pagina_muestra_el_detalle_tecnico_del_fallo(monkeypatch):
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo
    from antivirus_hogar_pc.modules.net import page as netpage
    from antivirus_hogar_pc.modules.net import servicios_red as srv
    from antivirus_hogar_pc.modules.net.fake import servidores_fake
    from antivirus_hogar_pc.ui import theme

    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(theme.QSS)
    monkeypatch.setattr(srv, "informe_wifi",
                        lambda: ResultadoModulo(ok=False, mensaje="sin wifi"))
    monkeypatch.setattr(srv, "descargar_servidores_completos",
                        lambda: ResultadoModulo(ok=False, mensaje="sin red"))
    monkeypatch.setattr(srv, "estado_vpn",
                        lambda: ResultadoModulo(ok=True, datos={}))
    monkeypatch.setattr(
        srv, "conectar_vpn",
        lambda servidor: ResultadoModulo(
            ok=False, mensaje="fallo de opciones",
            detalle_tecnico="Options warning: Bad backslash usage"))
    widget = netpage.crear_pagina_red(ContextoModulo(servicios=None))
    pagina = widget._pagina_controladora
    servidores = servidores_fake()
    pagina._conectar(servidores[0])
    limite = time.time() + 10
    while time.time() < limite and not pagina._lbl_vpn_detalle.text():
        app.processEvents()
        time.sleep(0.05)
    assert "Bad backslash" in pagina._lbl_vpn_detalle.text()
    assert "Detalle técnico" in pagina._lbl_vpn_detalle.text()
    widget.deleteLater()
    app.processEvents()
