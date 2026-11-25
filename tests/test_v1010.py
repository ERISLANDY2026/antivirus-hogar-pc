"""v1.0.10 — Cambio de motor VPN: fuera SoftEther, entra OpenVPN.

1. Guardas del paquete: SoftEther NO está (ni payload, ni servicio,
   ni vpncmd, ni su actualizador) y OpenVPN SÍ (instalador oficial
   verificado por tamaño y huella en el workflow, instalación
   silenciosa y retirada limpia de los restos de SoftEther).
2. Botones «Conectar» cortados (reporte de la 1.0.9): la fila de
   la tabla mide 42 px y el botón cabe entero (verificación
   geométrica offscreen, no solo de código).
3. Motor OpenVPN (simulado por sus dos puertas: el proceso y la
   interfaz de gestión): preparar el perfil de VPN Gate, conectar
   con el túnel confirmado (CONNECTED,SUCCESS), errores típicos
   con su mensaje en español y la causa real del registro,
   estado y desconexión por la interfaz.
4. Auto-actualizador de OpenVPN con las 4 condiciones del
   usuario: chequeo cada 3 días contra fuentes oficiales,
   verificación del paquete ANTES de aplicar (tamaño, MSI y
   firma), diferido con túnel activo, verificación tras aplicar
   y REVERSIÓN a la versión anterior si algo queda mal.
"""
import hashlib
import json
import os

import pytest

RAIZ = os.path.join(os.path.dirname(__file__), "..")


def _leer(ruta_relativa: str) -> str:
    with open(os.path.join(RAIZ, ruta_relativa), encoding="utf-8") as f:
        return f.read()


# === 1. Guardas del paquete =====================================================

def test_sin_softether_en_el_paquete_ni_en_el_motor():
    iss = _leer(os.path.join("packaging", "instalador.iss"))
    # Sin payload de SoftEther y sin su preparación de tarjeta.
    assert "softether\\client" not in iss
    assert "RegistrarServicioSoftEther" not in iss
    assert "NicCreate" not in iss and "/add-driver" not in iss
    assert "PrepararTarjetaVirtualSoftEther" not in iss
    yml = _leer(os.path.join(".github", "workflows", "build-windows.yml"))
    assert "softether-vpnclient" not in yml        # ya no se descarga
    assert "SoftEtherVPN_Stable" not in yml
    assert "56249368" not in yml
    # El motor y la capa de servicios ya no conocen SoftEther
    # (las menciones históricas del docstring inicial de vpn_win
    # no cuentan: lo que no puede quedar es código suyo).
    vpn = _leer(os.path.join(
        "antivirus_hogar_pc", "winapi", "vpn_win.py"))
    cuerpo_vpn = vpn.split('"""', 2)[2]  # fuera el docstring inicial
    assert "vpncmd" not in cuerpo_vpn.lower()
    for simbolo in ("conectar_softether", "estado_softether",
                    "desconectar_softether", "softether_instalado",
                    "asegurar_cuenta", "NicCreate", "Neo6"):
        assert simbolo not in cuerpo_vpn, simbolo
    srv = _leer(os.path.join(
        "antivirus_hogar_pc", "modules", "net", "servicios_red.py"))
    assert "softether" not in srv.lower()
    main = _leer(os.path.join("antivirus_hogar_pc", "ui", "main.py"))
    assert "softether_update" not in main
    # Ni el módulo del actualizador ni la carpeta del payload existen.
    assert not os.path.exists(os.path.join(
        RAIZ, "antivirus_hogar_pc", "winapi", "softether_update.py"))
    assert not os.path.isdir(os.path.join(RAIZ, "packaging", "softether"))


def test_openvpn_presente_y_verificado_en_el_paquete():
    iss = _leer(os.path.join("packaging", "instalador.iss"))
    assert '#define AppVersion "1.0.11"' in iss  # v1.0.11: vigente
    assert "openvpn\\OpenVPN-2.7.9-I002-amd64.msi" in iss
    assert "msiexec" in iss and "/quiet" in iss  # instalación silenciosa
    # La retirada limpia de los restos de SoftEther SÍ está.
    assert "RetirarRestosSoftEther" in iss
    assert "openvpn-instalacion.txt" in iss
    yml = _leer(os.path.join(".github", "workflows", "build-windows.yml"))
    assert ("https://swupdate.openvpn.org/community/releases/"
            "OpenVPN-2.7.9-I002-amd64.msi") in yml
    assert "5939200" in yml  # tamaño oficial verificado
    assert ("D050EFADC6CABC4E304EB810DD7FEDFC54B859D34730AB9CDCB22D61EB"
            "86AB7A") in yml  # SHA-256 oficial fijado
    assert os.path.isfile(os.path.join(
        RAIZ, "packaging", "openvpn", "LEEME.md"))


def test_main_arranca_el_actualizador_de_openvpn():
    main = _leer(os.path.join("antivirus_hogar_pc", "ui", "main.py"))
    assert "openvpn_update" in main
    assert "chequear_y_aplicar" in main


# === 2. Botones «Conectar» sin corte inferior ===================================

def test_altura_de_fila_corregida_en_el_codigo():
    fuente = _leer(os.path.join(
        "antivirus_hogar_pc", "modules", "net", "page.py"))
    assert "setDefaultSectionSize(42)" in fuente
    assert "resizeRowsToContents()" in fuente


def test_boton_conectar_cabe_entero_en_su_fila(monkeypatch):
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QPushButton

    from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo
    from antivirus_hogar_pc.modules.net import page as netpage
    from antivirus_hogar_pc.modules.net import servicios_red as srv
    from antivirus_hogar_pc.modules.net.fake import servidores_fake
    from antivirus_hogar_pc.ui import theme

    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(theme.QSS)
    # Sin red en la prueba: las cargas automáticas de la página se
    # quedan en respuestas vacías (mismo patrón que la captura).
    # Con monkeypatch: los stubs se revierten al salir del test.
    monkeypatch.setattr(srv, "informe_wifi",
                        lambda: ResultadoModulo(ok=False,
                                                mensaje="sin wifi"))
    monkeypatch.setattr(srv, "descargar_servidores_completos",
                        lambda: ResultadoModulo(ok=False,
                                                mensaje="sin red (prueba)"))
    monkeypatch.setattr(srv, "estado_vpn",
                        lambda: ResultadoModulo(ok=True, datos={}))
    widget = netpage.crear_pagina_red(ContextoModulo(servicios=None))
    pagina = widget._pagina_controladora
    pagina._servidores_cargados(
        ResultadoModulo(ok=True, datos=servidores_fake()))
    widget.resize(880, 900)
    widget.show()
    for _ in range(20):
        app.processEvents()
    tabla = pagina._tabla_vpn
    assert tabla.verticalHeader().defaultSectionSize() == 42
    celda = tabla.cellWidget(0, 5)
    boton = celda.findChildren(QPushButton)[0]
    assert boton.text() == "Conectar"
    # El botón, con sus márgenes de celda (2 px por lado), cabe
    # ENTERO en la fila: nada de corte por abajo.
    assert tabla.rowHeight(0) >= 42
    # La celda puede medir 1 px menos que la fila (la línea de la
    # rejilla); lo que importa es que el botón quepa entero en ella.
    assert celda.height() >= tabla.rowHeight(0) - 1
    assert boton.height() + 4 <= celda.height()
    assert boton.geometry().bottom() < celda.height()
    widget.deleteLater()
    app.processEvents()


# === 3. Motor OpenVPN (simulado) ================================================

_ESTADO_CONECTADO = (
    ">INFO:OpenVPN Management Interface Version 5 -- type 'help'\r\n"
    "1732464000,CONNECTED,SUCCESS,10.211.1.5,203.0.113.7,443,,\r\n"
    "END\r\n")
_ESTADO_CONECTANDO = (
    "1732464000,RECONNECTING,auth-failure,,,,,\r\nEND\r\n")

_PERFIL_VPNGATE = (
    "client\n"
    "dev tun\n"
    "proto udp\n"
    "remote vpn123.opengw.net 1194\n"
    "cipher AES-128-CBC\n"
    "auth SHA1\n"
    "auth-user-pass\n"
    "<ca>\n-----BEGIN CERTIFICATE-----\nMIIfalso\n"
    "-----END CERTIFICATE-----\n</ca>\n")


def test_interpretar_estado_mgmt():
    from antivirus_hogar_pc.winapi.vpn_win import interpretar_estado_mgmt

    r = interpretar_estado_mgmt(_ESTADO_CONECTADO)
    assert r["conectado"] is True and r["estado"] == "CONNECTED"
    assert r["ip_local"] == "10.211.1.5"
    r2 = interpretar_estado_mgmt(_ESTADO_CONECTANDO)
    assert r2["conectado"] is False and r2["estado"] == "RECONNECTING"
    # La notificación en tiempo real (>STATE:) también se interpreta.
    r3 = interpretar_estado_mgmt(
        ">STATE:1732464000,CONNECTED,SUCCESS,10.0.0.2,1.2.3.4,443,,\n")
    assert r3["conectado"] is True
    assert interpretar_estado_mgmt("")["conectado"] is False


def test_preparar_perfil_vpngate():
    from antivirus_hogar_pc.winapi.vpn_win import preparar_perfil_vpngate

    salida = preparar_perfil_vpngate(_PERFIL_VPNGATE, r"C:\datos\cred.txt")
    # Las credenciales de la app, una sola vez y con su ruta.
    assert salida.count("auth-user-pass") == 1
    # v1.0.11: la ruta va ESCAPADA con barras dobles. La 1.0.10 la
    # escribía con barras simples y este test lo EXIGÍA: OpenVPN
    # 2.7.9 lo trata como error fatal de opciones («Bad backslash»)
    # y muere antes de abrir su registro — fue el fallo real en la
    # PC del usuario con todos los servidores.
    assert 'auth-user-pass "C:\\\\datos\\\\cred.txt"' in salida
    assert 'auth-user-pass "C:\\datos\\cred.txt"' not in salida
    # El cifrado viejo del perfil queda como respaldo de negociación.
    assert "data-ciphers-fallback AES-128-CBC" in salida
    # El resto del perfil no se toca.
    assert "remote vpn123.opengw.net 1194" in salida
    assert "MIIfalso" in salida


def test_interpretar_version_y_tap():
    from antivirus_hogar_pc.winapi import vpn_win

    assert vpn_win.interpretar_version_openvpn(
        "OpenVPN 2.7.9 x86_64-w64-mingw32 [SSL (OpenSSL)]\n") == "2.7.9"
    assert vpn_win.interpretar_version_openvpn("ruido") == ""
    assert vpn_win.interpretar_adaptadores_tap(
        "OpenVPN TAP-Windows6|TAP-Windows Adapter V9") is True
    assert vpn_win.interpretar_adaptadores_tap(
        "Wi-Fi|Intel(R) Dual Band Wireless-AC 8265") is False


class _ProcesoFalso:
    def __init__(self, vivo=True):
        self._vivo = vivo
        self.pid = 4242
        self.esperado = False

    def poll(self):
        return None if self._vivo else 1

    def wait(self, timeout=None):
        self.esperado = True
        return 0

    def terminate(self):
        self._vivo = False


def _motor_falso(monkeypatch, tmp_path, estado=_ESTADO_CONECTADO,
                 proceso=None, log=""):
    """vpn_win con el motor simulado por sus dos puertas."""
    from antivirus_hogar_pc.winapi import vpn_win

    carpeta = tmp_path / "vpn"
    carpeta.mkdir(exist_ok=True)
    monkeypatch.setattr(vpn_win, "ruta_openvpn_exe",
                        lambda: r"C:\Program Files\OpenVPN\bin\openvpn.exe")
    monkeypatch.setattr(vpn_win, "carpeta_perfiles_vpn",
                        lambda: str(carpeta))
    comandos = []

    def falso_mgmt(puerto, comando, timeout=10):
        comandos.append(comando)
        if comando == "state":
            return estado
        return "SUCCESS: signal SIGTERM thrown"

    def falso_lanzar(argumentos, carpeta_trabajo, ruta_salida=""):
        if log:
            ruta_log = argumentos[argumentos.index("--log-append") + 1]
            with open(ruta_log, "w", encoding="utf-8") as f:
                f.write(log)
        return proceso if proceso is not None else _ProcesoFalso()

    monkeypatch.setattr(vpn_win, "_mgmt_enviar", falso_mgmt)
    monkeypatch.setattr(vpn_win, "_lanzar_openvpn", falso_lanzar)
    vpn_win._PROCESO = None
    return vpn_win, comandos, carpeta


def test_conectar_openvpn_flujo_completo(monkeypatch, tmp_path):
    vpn_win, comandos, carpeta = _motor_falso(monkeypatch, tmp_path)
    res = vpn_win.conectar_openvpn(_PERFIL_VPNGATE, "vpn123.opengw.net",
                                   espera=5)
    assert res["ok"] is True
    assert res["datos"]["via"] == "openvpn"
    assert "state" in comandos  # el túnel se CONFIRMÓ por la interfaz
    # El perfil preparado y las credenciales quedaron en la carpeta.
    perfil = (carpeta / "vpngate-activo.ovpn").read_text(encoding="utf-8")
    assert "auth-user-pass" in perfil
    cred = (carpeta / "vpngate-credenciales.txt").read_text(encoding="utf-8")
    assert cred.splitlines() == ["vpn", "vpn"]
    # Estado: la interfaz dice que el túnel está arriba.
    estado = vpn_win.estado_openvpn()
    # v1.0.11: el estado trae además «conectando» (la sesión en
    # curso sin confirmar); confirmado el túnel, queda en False.
    assert estado == {"instalado": True, "conectado": True,
                      "hostname": "vpn123.opengw.net",
                      "conectando": False}
    # Desconexión por la interfaz (signal SIGTERM), no a lo bruto.
    desc = vpn_win.desconectar_openvpn()
    assert desc["ok"] is True
    assert "signal SIGTERM" in comandos


def test_conectar_openvpn_error_de_autenticacion_en_espanol(
        monkeypatch, tmp_path):
    log = ("2026-11-25 08:00:00 AUTH_FAILED,Username/Password "
           "authentication failed\n"
           "2026-11-25 08:00:00 Exiting due to fatal error\n")
    vpn_win, _c, _carpeta = _motor_falso(
        monkeypatch, tmp_path, proceso=_ProcesoFalso(vivo=False), log=log)
    res = vpn_win.conectar_openvpn(_PERFIL_VPNGATE, "vpn123.opengw.net",
                                   espera=5)
    assert res["ok"] is False
    assert "autenticación" in res["mensaje"]
    assert "AUTH_FAILED" in res["detalle"]  # la causa real, del registro


def test_conectar_openvpn_sin_confirmacion_a_tiempo(monkeypatch, tmp_path):
    vpn_win, _c, _carpeta = _motor_falso(
        monkeypatch, tmp_path, estado=_ESTADO_CONECTANDO)
    res = vpn_win.conectar_openvpn(_PERFIL_VPNGATE, "vpn123.opengw.net",
                                   espera=5)
    assert res["ok"] is False
    assert "no se confirmó a tiempo" in res["mensaje"]


def test_cada_servidor_de_la_semilla_genera_su_ovpn():
    from antivirus_hogar_pc import config
    from antivirus_hogar_pc.core import vpngate
    from antivirus_hogar_pc.winapi.vpn_win import preparar_perfil_vpngate

    servidores, _fuente = vpngate.leer_semilla_vpngate(
        config.carpeta_activos())
    assert servidores, "la semilla de VPN Gate debe poblar la lista"
    for s in servidores:
        assert s.hostname  # sin host no hay conexión posible
        ovpn = s.generar_ovpn()
        assert "remote" in ovpn  # el perfil trae su servidor
        preparado = preparar_perfil_vpngate(ovpn, "cred.txt")
        assert "auth-user-pass" in preparado


# === 4. Auto-actualizador de OpenVPN =============================================

_MSI_FALSO = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 2040
_HTML_DESCARGAS = (
    '<a href="https://swupdate.openvpn.org/community/releases/'
    'OpenVPN-2.7.9-I002-amd64.msi">Download OpenVPN-2.7.9-I002-amd64.msi</a>')
_HTML_DESCARGAS_NUEVA = (
    '<a href="https://swupdate.openvpn.org/community/releases/'
    'OpenVPN-2.7.10-I001-amd64.msi">Download '
    'OpenVPN-2.7.10-I001-amd64.msi</a>')


def test_versiones_del_actualizador():
    from antivirus_hogar_pc.winapi import openvpn_update as ou

    assert ou.version_desde_nombre("OpenVPN-2.7.9-I002-amd64.msi") == \
        (2, 7, 9, 2)
    assert ou.version_desde_nombre("otra-cosa.msi") is None
    assert ou.nombre_instalador((2, 7, 10, 1)) == \
        "OpenVPN-2.7.10-I001-amd64.msi"
    assert ou.comparar_versiones((2, 7, 10, 1), (2, 7, 9, 2)) == 1
    assert ou.comparar_versiones((2, 7, 9, 2), (2, 7, 9, 2)) == 0
    assert ou.texto_version((2, 7, 9, 2)) == "2.7.9 (instalador I002)"


def test_cadencia_tres_dias_openvpn():
    from antivirus_hogar_pc.winapi import openvpn_update as ou

    ahora = 1_000_000.0
    assert ou.toca_chequear(ahora, {}) is True
    assert ou.toca_chequear(ahora, {"ultimo_chequeo": ahora - 2 * 86400}) \
        is False
    assert ou.toca_chequear(
        ahora, {"ultimo_chequeo": ahora - 3 * 86400 - 1}) is True


def test_consultar_fuentes_la_mayor_manda():
    from antivirus_hogar_pc.winapi import openvpn_update as ou

    def descargar(url):
        if "community-downloads" in url:
            return _HTML_DESCARGAS
        return json.dumps([{"assets": [
            {"name": "OpenVPN-2.7.10-I001-amd64.msi"}]}])

    salida = ou.consultar_fuentes(descargar)
    assert salida["version"] == (2, 7, 10, 1)
    assert salida["url"] == (
        "https://swupdate.openvpn.org/community/releases/"
        "OpenVPN-2.7.10-I001-amd64.msi")
    assert salida["fallos"] == []

    def caidas(_url):
        raise OSError("sin red")

    salida2 = ou.consultar_fuentes(caidas)
    assert salida2["version"] is None
    assert len(salida2["fallos"]) == len(ou.FUENTES)


def test_verificar_paquete_msi(tmp_path):
    from antivirus_hogar_pc.winapi import openvpn_update as ou

    ruta = tmp_path / "OpenVPN-2.7.10-I001-amd64.msi"
    ruta.write_bytes(_MSI_FALSO)
    ok = ou.verificar_paquete_msi(str(ruta), len(_MSI_FALSO))
    assert ok["ok"] is True
    assert ok["sha256"] == hashlib.sha256(_MSI_FALSO).hexdigest()
    mal_tamano = ou.verificar_paquete_msi(str(ruta), len(_MSI_FALSO) + 1)
    assert mal_tamano["ok"] is False and "pesa" in mal_tamano["causa"]
    ruta2 = tmp_path / "falso.msi"
    ruta2.write_bytes(b"NO ES UN MSI" + b"\0" * 100)
    mal_msi = ou.verificar_paquete_msi(str(ruta2), 0)
    assert mal_msi["ok"] is False and "MSI" in mal_msi["causa"]


def test_interpretar_firma_solo_openvpn_valida():
    from antivirus_hogar_pc.winapi import openvpn_update as ou

    buena = json.dumps({"estado": "Valid",
                        "firmante": "CN=OpenVPN, Inc., O=OpenVPN, Inc."})
    assert ou.interpretar_firma(buena)["valida"] is True
    otro = json.dumps({"estado": "Valid", "firmante": "CN=ACME Corp"})
    assert ou.interpretar_firma(otro)["valida"] is False
    sin_firma = json.dumps({"estado": "NotSigned", "firmante": ""})
    assert ou.interpretar_firma(sin_firma)["valida"] is False
    assert ou.interpretar_firma("no es json")["valida"] is False


def _preparar_actualizador(monkeypatch, tmp_path):
    """openvpn_update con la carpeta de datos en tmp y red simulada."""
    from antivirus_hogar_pc import config
    from antivirus_hogar_pc.core import updater
    from antivirus_hogar_pc.winapi import openvpn_update as ou

    monkeypatch.setattr(config, "carpeta_datos", lambda: str(tmp_path))
    monkeypatch.setattr(ou, "version_instalada", lambda: (2, 7, 9, 2))

    def descargar_archivo_falso(url, destino, **_kw):
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "wb") as f:
            f.write(_MSI_FALSO)

    monkeypatch.setattr(updater, "descargar_archivo", descargar_archivo_falso)
    return ou


def test_chequear_deja_pendiente_solo_lo_verificado(monkeypatch, tmp_path):
    ou = _preparar_actualizador(monkeypatch, tmp_path)
    registros = []
    salida = ou.chequear(
        lambda t, d: registros.append(d),
        descargar=lambda url: _HTML_DESCARGAS_NUEVA
        if "community-downloads" in url else (_ for _ in ()).throw(
            OSError("github caido")),
        tamano_remoto=lambda url: len(_MSI_FALSO),
        verificar_firma=lambda ruta: {"valida": True,
                                      "firmante": "OpenVPN, Inc."},
        forzar=True)
    assert salida["motivo"] == "pendiente"
    estado = ou._leer_estado()
    assert estado["pendiente"]["version"] == [2, 7, 10, 1]
    assert estado["pendiente"]["sha256"] == \
        hashlib.sha256(_MSI_FALSO).hexdigest()
    assert any("verificada" in d for d in registros)


def test_chequear_descarta_lo_que_no_pasa_la_firma(monkeypatch, tmp_path):
    ou = _preparar_actualizador(monkeypatch, tmp_path)
    salida = ou.chequear(
        lambda t, d: None,
        descargar=lambda url: _HTML_DESCARGAS_NUEVA,
        tamano_remoto=lambda url: len(_MSI_FALSO),
        verificar_firma=lambda ruta: {"valida": False, "firmante": ""},
        forzar=True)
    assert salida["motivo"] == "firma"
    assert ou._leer_estado().get("pendiente") is None
    # El paquete descartado no queda en la carpeta de descargas.
    carpeta = tmp_path / "actualizaciones"
    assert not carpeta.exists() or not list(carpeta.iterdir())


def _estado_con_pendiente(ou, tmp_path):
    nuevo = tmp_path / "OpenVPN-2.7.10-I001-amd64.msi"
    nuevo.write_bytes(_MSI_FALSO)
    anterior = tmp_path / "OpenVPN-2.7.9-I002-amd64.msi"
    anterior.write_bytes(_MSI_FALSO)
    ou._guardar_estado({"pendiente": {
        "version": [2, 7, 10, 1], "nombre": nuevo.name,
        "url": "https://swupdate.openvpn.org/community/releases/"
               "OpenVPN-2.7.10-I001-amd64.msi",
        "tamano": len(_MSI_FALSO),
        "sha256": hashlib.sha256(_MSI_FALSO).hexdigest(),
        "instalador": str(nuevo), "desde": "2.7.9 (instalador I002)",
        "anterior": str(anterior)}})
    return nuevo, anterior


def test_aplicar_diferido_con_tunel_activo(monkeypatch, tmp_path):
    from antivirus_hogar_pc.winapi import vpn_win

    ou = _preparar_actualizador(monkeypatch, tmp_path)
    _estado_con_pendiente(ou, tmp_path)
    monkeypatch.setattr(vpn_win, "hay_tunel_openvpn", lambda: True)

    def prohibido(*_a, **_k):
        raise AssertionError("con túnel activo no se aplica nada")

    salida = ou.aplicar_pendiente(lambda t, d: None, ejecutar=prohibido)
    assert salida["aplicada"] is False and salida.get("diferida") is True
    assert ou._leer_estado()["pendiente"] is not None  # sigue pendiente


def test_aplicar_ok_verifica_y_marca(monkeypatch, tmp_path):
    from antivirus_hogar_pc.winapi import vpn_win

    ou = _preparar_actualizador(monkeypatch, tmp_path)
    _estado_con_pendiente(ou, tmp_path)
    monkeypatch.setattr(vpn_win, "hay_tunel_openvpn", lambda: False)
    monkeypatch.setattr(ou, "es_windows", lambda: True)
    llamadas = []

    def ejecutar(ruta, nombre):
        llamadas.append((ruta, nombre))
        return {"codigo": 0, "copia": True}

    salida = ou.aplicar_pendiente(
        lambda t, d: None, verificar=lambda v=None: {
            "ok": True, "fallos": [], "diagnostico": {}},
        ejecutar=ejecutar)
    assert salida["aplicada"] is True
    assert len(llamadas) == 1
    estado = ou._leer_estado()
    assert estado["version_aplicada"] == [2, 7, 10, 1]
    assert estado["pendiente"] is None
    # El respaldo del instalador anterior quedó guardado.
    assert (tmp_path / "openvpn-anterior.msi").is_file()


def test_aplicar_revierte_si_la_verificacion_falla(monkeypatch, tmp_path):
    from antivirus_hogar_pc.winapi import vpn_win

    ou = _preparar_actualizador(monkeypatch, tmp_path)
    _estado_con_pendiente(ou, tmp_path)
    monkeypatch.setattr(vpn_win, "hay_tunel_openvpn", lambda: False)
    monkeypatch.setattr(ou, "es_windows", lambda: True)
    llamadas = []
    verificaciones = iter([
        {"ok": False, "fallos": ["la tarjeta TAP-Windows no aparece "
                                 "tras la actualización"],
         "diagnostico": {}},
        {"ok": True, "fallos": [], "diagnostico": {}},
    ])
    registros = []

    def ejecutar(ruta, nombre):
        llamadas.append(ruta)
        return {"codigo": 0, "copia": True}

    salida = ou.aplicar_pendiente(
        lambda t, d: registros.append(d),
        verificar=lambda v=None: next(verificaciones),
        ejecutar=ejecutar)
    assert salida["aplicada"] is False
    assert salida["motivo"] == "revertida" and salida["revertido"] is True
    assert len(llamadas) == 2  # aplicar + revertir
    assert llamadas[1].endswith("openvpn-anterior.msi")
    assert any("REVIERTE" in d for d in registros)
    estado = ou._leer_estado()
    assert estado["pendiente"] is None
    assert estado["ultima_reversion"]["version_fallida"] == [2, 7, 10, 1]


def test_aplicar_msiexec_fallido_no_toca_nada(monkeypatch, tmp_path):
    from antivirus_hogar_pc.winapi import vpn_win

    ou = _preparar_actualizador(monkeypatch, tmp_path)
    _estado_con_pendiente(ou, tmp_path)
    monkeypatch.setattr(vpn_win, "hay_tunel_openvpn", lambda: False)
    monkeypatch.setattr(ou, "es_windows", lambda: True)
    salida = ou.aplicar_pendiente(
        lambda t, d: None,
        verificar=lambda v=None: (_ for _ in ()).throw(
            AssertionError("sin instalación no hay verificación")),
        ejecutar=lambda ruta, nombre: {"codigo": 1603, "copia": False})
    assert salida["aplicada"] is False and salida["motivo"] == "msiexec"
    assert ou._leer_estado()["pendiente"] is not None  # queda para reintentar


def test_verificar_integracion_y_resincronizar(monkeypatch):
    from antivirus_hogar_pc.winapi import openvpn_update as ou
    from antivirus_hogar_pc.winapi import vpn_win

    sano = {"instalado": True, "ruta_exe": "x", "version": "2.7.10",
            "servicio": {"registrado": True, "corriendo": True},
            "tap": True, "conectado": False}
    monkeypatch.setattr(vpn_win, "diagnostico_openvpn", lambda: dict(sano))
    assert ou.verificar_integracion((2, 7, 10, 1))["ok"] is True
    assert ou.resincronizar(lambda t, d: None)["ok"] is True

    sin_tap = dict(sano, tap=False)
    monkeypatch.setattr(vpn_win, "diagnostico_openvpn", lambda: sin_tap)
    mal = ou.verificar_integracion((2, 7, 10, 1))
    assert mal["ok"] is False and any("TAP" in f for f in mal["fallos"])
    assert ou.resincronizar(lambda t, d: None)["ok"] is False

    viejo = dict(sano, version="2.7.9")
    monkeypatch.setattr(vpn_win, "diagnostico_openvpn", lambda: viejo)
    mal2 = ou.verificar_integracion((2, 7, 10, 1))
    assert mal2["ok"] is False  # la versión no llegó a la esperada
