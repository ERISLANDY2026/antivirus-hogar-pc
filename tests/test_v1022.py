"""Pruebas de la v1.0.22 — las notas del usuario del 2026-11-27.

1. Renombre: «WAR — Home Guardian» (solo inglés) como nombre
   visible — ventana, bandeja, instalador, encabezado con su
   marca pintada — sin tocar rutas internas.
2. Verificación VPN rápida: la sonda del protocolo OpenVPN
   (core.sonda_rapida), el veredicto «online», el sello
   «✓ Online» en verde y la desaparición automática de los
   que no responden al terminar la ronda.
3. El botón «Diagnosticar integridad de la aplicación» abre
   su página (regresión del clic muerto desde la 1.0.19) y el
   diagnóstico corre y produce informe.
4. «Medir velocidad»: el ping se emite y se pinta en cuanto
   se mide, no al final de la prueba.
"""
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _esperar(app, condicion, segundos: float = 15.0) -> bool:
    limite = time.time() + segundos
    while time.time() < limite:
        app.processEvents()
        if condicion():
            return True
        time.sleep(0.03)
    app.processEvents()
    return condicion()


def _servidor(host, pais="Japan"):
    import base64

    from antivirus_hogar_pc.core.vpngate import ServidorVPN

    ovpn = f"client\nremote {host} 1194 udp\nproto udp\n"
    return ServidorVPN(
        hostname=host, ip="1.2.3.4", puntuacion=0, ping_ms=50,
        velocidad_bps=1000000, pais=pais, pais_corto="JP",
        sesiones=10, uptime=9999, total_usuarios=0, operador="op",
        mensaje="",
        ovpn_base64=base64.b64encode(ovpn.encode()).decode())


# === 1. Renombre y versión =====================================================

def test_version_1022_en_todos_los_sitios():
    from antivirus_hogar_pc import config
    from antivirus_hogar_pc.core import notas_version

    assert config.VERSION == "1.0.22"
    assert notas_version.NOTAS_VERSION[0]["version"] == "1.0.22"
    texto = " ".join(notas_version.NOTAS_VERSION[0]["novedades"])
    assert "WAR — Home Guardian" in texto
    assert "✓ Online" in texto
    raiz = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(raiz, "packaging", "instalador.iss"),
              encoding="utf-8") as f:
        iss = f.read()
    assert '#define AppVersion "1.0.22"' in iss
    assert '#define AppNombre "WAR — Home Guardian"' in iss
    # La carpeta de instalación NO se renombra (actualizar en
    # sitio sobre la de siempre) ni el ejecutable.
    assert "DefaultDirName={autopf}\\Antivirus Hogar PC" in iss
    assert '#define AppExe "AntivirusHogarPC.exe"' in iss


def test_nombre_visible_solo_ingles_y_rutas_internas_intactas():
    from antivirus_hogar_pc import NOMBRE_APP, config

    assert NOMBRE_APP == "WAR — Home Guardian"
    # Por dentro todo sigue igual: el ID de la app (carpeta de
    # datos) no cambia con el renombre.
    assert config.APP_ID == "AntivirusHogarPC"


def test_marca_war_se_construye_y_pinta():
    app = _app()
    from antivirus_hogar_pc.ui.marca_war import (
        TEXTO_SUB,
        TEXTO_WAR,
        MarcaWAR,
    )

    assert TEXTO_WAR == "WAR" and TEXTO_SUB == "Home Guardian"
    marca = MarcaWAR()
    assert marca.width() > 80 and marca.height() > 40
    marca.show()
    app.processEvents()
    imagen = marca.grab()
    assert not imagen.isNull()
    marca.deleteLater()
    app.processEvents()


def test_ventana_titulo_marca_y_bandeja(monkeypatch, tmp_path):
    app = _app()
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    from PySide6.QtGui import QIcon

    from antivirus_hogar_pc.ui.bandeja import Bandeja
    from antivirus_hogar_pc.ui.main_window import VentanaPrincipal
    from antivirus_hogar_pc.ui.marca_war import MarcaWAR
    from antivirus_hogar_pc.ui.services import ServiciosApp

    ventana = VentanaPrincipal(ServiciosApp())
    assert ventana.windowTitle() == "WAR — Home Guardian"
    assert ventana.findChild(MarcaWAR) is not None
    bandeja = Bandeja(QIcon(), lambda: None, lambda: None,
                      lambda: None)
    assert bandeja.tray.toolTip() == "WAR — Home Guardian"
    ventana.deleteLater()
    app.processEvents()


# === 2. La sonda rápida ==========================================================

def test_paquete_cliente_es_el_hard_reset_real():
    from antivirus_hogar_pc.core import sonda_rapida

    paquete = sonda_rapida.construir_paquete_cliente(b"\x01" * 8)
    assert paquete[0] == 0x38  # P_CONTROL_HARD_RESET_CLIENT_V2
    assert paquete[1:9] == b"\x01" * 8  # id de sesión
    assert len(paquete) == 22
    with pytest.raises(ValueError):
        sonda_rapida.construir_paquete_cliente(b"\x01")


def test_solo_el_hard_reset_del_servidor_marca_online():
    from antivirus_hogar_pc.core import sonda_rapida

    assert sonda_rapida.es_respuesta_servidor(b"\x40" + b"\x00" * 21)
    assert sonda_rapida.es_respuesta_servidor(b"\x42" + b"\x00" * 21)  # key-id 2
    # Ni el eco del paquete de cliente, ni otro servicio, ni vacío.
    assert not sonda_rapida.es_respuesta_servidor(b"\x38" + b"\x00" * 21)
    assert not sonda_rapida.es_respuesta_servidor(b"HTTP/1.1 200 OK")
    assert not sonda_rapida.es_respuesta_servidor(b"")
    assert not sonda_rapida.es_respuesta_servidor(None)


def test_sonda_udp_contra_servidor_de_mentira():
    import socket
    import threading

    from antivirus_hogar_pc.core import sonda_rapida

    # Hay entornos (la VM de construcción) cuya política
    # bloquea el envío UDP incluso a 127.0.0.1
    # (PermissionError): ahí la prueba se salta — en Windows
    # (CI y la PC del usuario) corre de verdad.
    try:
        _eco = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _eco.bind(("127.0.0.1", 0))
        _eco.sendto(b"x", _eco.getsockname())
        _eco.close()
    except PermissionError:
        pytest.skip("el entorno bloquea el envío UDP")

    servidor = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    servidor.bind(("127.0.0.1", 0))
    puerto = servidor.getsockname()[1]
    servidor.settimeout(5)

    def _responder():
        try:
            datos, origen = servidor.recvfrom(2048)
            assert datos[0] == 0x38  # llegó el hard-reset de cliente
            servidor.sendto(b"\x40" + b"\x00" * 21, origen)
        finally:
            servidor.close()

    hilo = threading.Thread(target=_responder, daemon=True)
    hilo.start()
    assert sonda_rapida.sondear("127.0.0.1", puerto, "udp",
                                timeout=3.0) is True
    hilo.join(timeout=5)


def test_sonda_udp_puerto_mudo_no_responde():
    import socket

    from antivirus_hogar_pc.core import sonda_rapida

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    puerto = s.getsockname()[1]
    s.close()  # nadie escucha: silencio (o ICMP inalcanzable)
    assert sonda_rapida.sondear("127.0.0.1", puerto, "udp",
                                timeout=0.6) is False
    assert sonda_rapida.sondear("", 0) is False


def test_sonda_tcp_con_prefijo_de_longitud():
    import socket
    import struct
    import threading

    from antivirus_hogar_pc.core import sonda_rapida

    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind(("127.0.0.1", 0))
    servidor.listen(1)
    puerto = servidor.getsockname()[1]

    def _responder():
        try:
            conn, _origen = servidor.accept()
            cab = conn.recv(2)
            (n,) = struct.unpack(">H", cab)
            datos = conn.recv(n)
            assert datos[0] == 0x38
            respuesta = b"\x40" + b"\x00" * 21
            conn.sendall(struct.pack(">H", len(respuesta)) + respuesta)
            conn.close()
        finally:
            servidor.close()

    hilo = threading.Thread(target=_responder, daemon=True)
    hilo.start()
    assert sonda_rapida.sondear("127.0.0.1", puerto, "tcp",
                                timeout=3.0) is True
    hilo.join(timeout=5)


def test_sondear_muchos_en_paralelo_y_con_cancelacion(monkeypatch):
    import threading

    from antivirus_hogar_pc.core import sonda_rapida

    monkeypatch.setattr(
        sonda_rapida, "sondear",
        lambda host, puerto, proto="udp", timeout=3.0:
        host.endswith("5"))
    destinos = {f"k{i}": (f"h{i}", 1194, "udp") for i in range(30)}
    vistos = []
    resultados = sonda_rapida.sondear_muchos(
        destinos,
        al_resultado=lambda c, r: vistos.append((c, r)),
        timeout=0.1)
    assert len(resultados) == 30
    assert resultados["k5"] is True and resultados["k15"] is True
    assert resultados["k0"] is False
    assert len(vistos) == 30

    cancelar = threading.Event()
    cancelar.set()
    resultados2 = sonda_rapida.sondear_muchos(
        destinos, timeout=0.1, cancelar=cancelar)
    assert resultados2 == {}


def test_veredicto_online_vigencia_y_rango():
    from antivirus_hogar_pc.core import fuentes_vpn as fuentes

    s = _servidor("a.jp")
    registro: dict = {}
    fuentes.registrar_veredicto(registro, s, "online", ahora=1000.0)
    estado, cuando = fuentes.veredicto_de(registro, s, ahora=1000.0)
    assert estado == "online" and cuando == 1000.0
    assert fuentes.rango_veredicto(registro, s, ahora=1000.0) == 0
    # Caducado (30 min después) vuelve a «sin verificar».
    estado2, _ = fuentes.veredicto_de(registro, s, ahora=1000.0 + 31 * 60)
    assert estado2 == "sin_verificar"
    assert fuentes.rango_veredicto(registro, s, ahora=1000.0 + 31 * 60) == 2


def test_ocultar_tras_ronda_la_regla_completa():
    from antivirus_hogar_pc.core import fuentes_vpn as fuentes

    ok = _servidor("ok.jp")
    caido = _servidor("caido.jp")
    lleno = _servidor("lleno.jp")
    fuera = _servidor("fuera.jp")
    veredictos: dict = {}
    fuentes.registrar_veredicto(veredictos, ok, "online", ahora=500.0)
    fuentes.registrar_veredicto(veredictos, lleno, "auth_failed",
                                ahora=500.0)
    ronda = {"cuando": 500.0, "resultados": {
        fuentes.clave_servidor(ok): True,
        fuentes.clave_servidor(caido): False,
        fuentes.clave_servidor(lleno): True,
    }}
    # Sin ronda no se oculta nada.
    assert not fuentes.ocultar_tras_ronda(veredictos, None, caido,
                                          ahora=500.0)
    assert not fuentes.ocultar_tras_ronda(veredictos, {}, caido,
                                          ahora=500.0)
    # El que no respondió desaparece; el que respondió, no.
    assert fuentes.ocultar_tras_ronda(veredictos, ronda, caido,
                                      ahora=500.0)
    assert not fuentes.ocultar_tras_ronda(veredictos, ronda, ok,
                                          ahora=500.0)
    # «auth_failed» contestó (lleno): no se oculta.
    assert not fuentes.ocultar_tras_ronda(veredictos, ronda, lleno,
                                          ahora=500.0)
    # El que no estaba en la ronda no se oculta.
    assert not fuentes.ocultar_tras_ronda(veredictos, ronda, fuera,
                                          ahora=500.0)
    # El conectado jamás se oculta, aunque no respondiera.
    assert not fuentes.ocultar_tras_ronda(
        veredictos, ronda, caido, ahora=500.0,
        hostname_conectado="caido.jp")
    # Un positivo vigente manda aunque la ronda lo perdiera.
    ronda2 = {"cuando": 500.0,
              "resultados": {fuentes.clave_servidor(ok): False}}
    assert not fuentes.ocultar_tras_ronda(veredictos, ronda2, ok,
                                          ahora=500.0)


def test_barrido_rapido_ronda_y_visibilidad(monkeypatch):
    from antivirus_hogar_pc.core import sonda_rapida
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    lista = [_servidor("ok.jp"), _servidor("caido.jp")]
    monkeypatch.setattr(srv, "_ULTIMA_LISTA", lista)
    monkeypatch.setattr(srv, "_VEREDICTOS", {})
    monkeypatch.setattr(srv, "_RONDA_ACTUAL", {})
    monkeypatch.setattr(srv, "_cargar_estado_fuentes", lambda: None)
    monkeypatch.setattr(srv, "_persistir_veredictos", lambda: None)
    monkeypatch.setattr(
        sonda_rapida, "sondear",
        lambda host, puerto, proto="udp", timeout=3.0: host == "ok.jp")
    # Antes de la ronda, todos visibles.
    assert srv.servidor_visible(lista[1]) is True
    res = srv.verificar_todos_los_servidores()
    assert res.datos["verificados"] == 1 and res.datos["fallidos"] == 1
    # Tras la ronda: el caído desaparece SOLO de la vista.
    assert srv.servidor_visible(lista[0]) is True
    assert srv.servidor_visible(lista[1]) is False
    # …pero sigue en la base interna para el próximo refresco.
    assert lista[1] in srv._ULTIMA_LISTA
    # Y si está conectado, jamás se oculta.
    assert srv.servidor_visible(lista[1],
                                hostname_conectado="caido.jp") is True


# === 3. El botón de diagnóstico (regresión) =======================================

def test_boton_diagnostico_abre_su_pagina_y_corre(monkeypatch, tmp_path):
    app = _app()
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    from PySide6.QtWidgets import QPushButton

    from antivirus_hogar_pc.ui.main_window import VentanaPrincipal
    from antivirus_hogar_pc.ui.services import ServiciosApp

    ventana = VentanaPrincipal(ServiciosApp())
    ventana.show()
    app.processEvents()
    # El botón REAL del panel izquierdo, pulsado de verdad.
    boton = ventana._botones["diagnostico"]
    assert isinstance(boton, QPushButton)
    boton.click()
    app.processEvents()
    pagina = ventana.pila.currentWidget()
    assert pagina is ventana._paginas["diagnostico"]
    # «Ejecutar el diagnóstico» corre y deja informe en pantalla.
    pagina.boton_correr_diagnostico.click()
    assert _esperar(
        app,
        lambda: "Diagnóstico de integridad" in
        pagina.area_informe_diagnostico.toPlainText(),
        segundos=30)
    ventana.deleteLater()
    app.processEvents()


# === 4. El ping en vivo ============================================================

def test_ping_se_emite_primero_y_con_su_valor():
    from antivirus_hogar_pc.core.velocidad import medir_velocidad_en_vivo

    class _Reloj:
        def __init__(self):
            self.t = 0.0

        def __call__(self):
            self.t += 0.2
            return self.t

    class _Transporte:
        def descargar(self, url, timeout, al_bloque):
            if "bytes=0" in url:
                return 0
            total = 0
            for _ in range(3):
                total += 1_000_000
                al_bloque(total)
            return total

        def subir(self, url, datos, timeout, al_bloque):
            al_bloque(len(datos))
            return len(datos)

    eventos = []
    res = medir_velocidad_en_vivo(
        al_progreso=lambda fase, v: eventos.append((fase, v)),
        transporte=_Transporte(), reloj=_Reloj(),
        bytes_bajada=3000, bytes_subida=1000)
    assert res["ok"] is True
    # La PRIMERA emisión es el ping, con su valor en ms, antes
    # de cualquier evento de bajada/subida.
    assert eventos[0][0] == "ping"
    assert eventos[0][1] == float(res["ping_ms"])
    assert [f for f, _v in eventos].index("ping") < \
        [f for f, _v in eventos].index("bajada")


def test_pagina_pinta_el_ping_en_cuanto_llega(monkeypatch):
    app = _app()
    from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo
    from antivirus_hogar_pc.modules.net import page as pagina_red
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    def _viva(al_progreso=None):
        # El ping llega y la prueba SIGUE (la bajada aún no):
        # la casilla debe pintarse antes del resultado final.
        al_progreso("ping", 33.0)
        time.sleep(1.2)
        al_progreso("bajada", 50.0)
        return ResultadoModulo(ok=True, datos={
            "ping_ms": 33, "bajada_mbps": 50.0, "subida_mbps": 9.0})

    monkeypatch.setattr(srv, "prueba_velocidad_viva", _viva)
    monkeypatch.setattr(srv, "informe_wifi",
                        lambda: ResultadoModulo(ok=False, mensaje="sin wifi"))
    monkeypatch.setattr(
        srv, "ip_publica",
        lambda: ResultadoModulo(ok=True, datos={"ip": "1.2.3.4"}))
    monkeypatch.setattr(
        srv, "estado_vpn",
        lambda: ResultadoModulo(ok=True, datos={"conectada": False}))
    monkeypatch.setattr(srv, "descargar_servidores_completos",
                        lambda: srv.servidores_semilla())
    pagina = pagina_red._PaginaRed(ContextoModulo(servicios=None))
    pagina._medir_velocidad()
    # Con la prueba AÚN en curso, el ping ya está pintado.
    assert _esperar(app, lambda: pagina._val_ping.text() == "33 ms",
                    segundos=5)
    assert pagina._trabajos  # la medición no ha terminado
    assert _esperar(app, lambda: not pagina._trabajos)
    assert pagina._val_ping.text() == "33 ms"
    assert pagina._val_bajada.text() == "50.0 Mbps"
    pagina.deleteLater()
    app.processEvents()
