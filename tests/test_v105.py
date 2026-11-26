"""Suite v1.0.5 — Antivirus Hogar PC.

Cubre: migración del canal de actualización, descarga resistente con
reanudación, iconos 3D del panel + tema cristal + radar militar,
optimización de volúmenes oculta con progreso real, velocidad en
vivo, Wi-Fi interactivo, VPN Gate semilla-primero, cadena de
confirmación de drivers (Catálogo → WU → almacén) con causa breve,
icono espartano de la app, arranque con Windows + rutina automática,
programaciones (persistencia, próxima ejecución, disparador) y la
pantalla «Versión de la app».
"""
import json
import os
import threading
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _esperar(app, condicion, segundos: float = 10.0) -> bool:
    limite = time.time() + segundos
    while time.time() < limite:
        app.processEvents()
        if condicion():
            return True
        time.sleep(0.03)
    app.processEvents()
    return condicion()


# === 1. Migración del canal (autocorrección de ajustes) ========================

def _cargar_ajustes(monkeypatch, tmp_path, guardados):
    from antivirus_hogar_pc import config

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    carpeta = config.carpeta_datos()
    if guardados is not None:
        with open(os.path.join(carpeta, "ajustes.json"), "w",
                  encoding="utf-8") as f:
            json.dump(guardados, f)
    from antivirus_hogar_pc.ui.services import Ajustes

    return Ajustes.cargar(), os.path.join(carpeta, "ajustes.json")


def test_migracion_url_envenenada_se_cura(monkeypatch, tmp_path):
    from antivirus_hogar_pc import config

    ajustes, ruta = _cargar_ajustes(monkeypatch, tmp_path, {
        "url_actualizacion":
            "https://drive.usercontent.google.com/download"
            "?id=1BpcVersionJsonPendiente&export=download",
        "letra_grande": True})
    assert ajustes.url_actualizacion == config.UPDATE_VERSION_URL
    assert ajustes.letra_grande is True  # el resto no se toca
    with open(ruta, encoding="utf-8") as f:
        assert json.load(f)["url_actualizacion"] == config.UPDATE_VERSION_URL


def test_migracion_url_distinta_se_sustituye(monkeypatch, tmp_path):
    from antivirus_hogar_pc import config

    ajustes, _ = _cargar_ajustes(monkeypatch, tmp_path, {
        "url_actualizacion": "https://ejemplo.invalid/version.json"})
    assert ajustes.url_actualizacion == config.UPDATE_VERSION_URL


def test_url_buena_no_se_toca(monkeypatch, tmp_path):
    from antivirus_hogar_pc import config

    ajustes, _ = _cargar_ajustes(monkeypatch, tmp_path, {
        "url_actualizacion": config.UPDATE_VERSION_URL,
        "fondo_animado": False})
    assert ajustes.url_actualizacion == config.UPDATE_VERSION_URL
    assert ajustes.fondo_animado is False


def test_sin_archivo_la_url_es_la_del_codigo(monkeypatch, tmp_path):
    from antivirus_hogar_pc import config

    ajustes, _ = _cargar_ajustes(monkeypatch, tmp_path, None)
    assert ajustes.url_actualizacion == config.UPDATE_VERSION_URL


# === 2. Descarga resistente (reintentos + reanudación Range) ===================

def _servidor_descarga(datos: bytes, cortes: int = 1, modo: str = "cortar"):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    estado = {"peticiones": 0, "rangos": []}

    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            estado["peticiones"] += 1
            rango = self.headers.get("Range")
            estado["rangos"].append(rango)
            if modo == "404":
                self.send_response(404)
                self.end_headers()
                return
            if rango:
                ini = int(rango.split("=")[1].split("-")[0])
                cuerpo = datos[ini:]
                self.send_response(206)
                self.send_header(
                    "Content-Range",
                    f"bytes {ini}-{len(datos) - 1}/{len(datos)}")
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            if estado["peticiones"] <= cortes:
                self.wfile.write(datos[: len(datos) // 2])
                self.wfile.flush()
                self.connection.shutdown(1)
                self.connection.close()
                return
            self.wfile.write(datos)

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor, estado


def test_descarga_se_reanuda_tras_corte(tmp_path):
    from antivirus_hogar_pc.core.updater import descargar_archivo

    datos = bytes(range(256)) * 400  # 102 400 bytes
    servidor, estado = _servidor_descarga(datos, cortes=1)
    try:
        url = f"http://127.0.0.1:{servidor.server_address[1]}/inst.exe"
        destino = str(tmp_path / "inst.exe")
        descargar_archivo(url, destino, reintentos=3, pausa=0.01)
        with open(destino, "rb") as f:
            assert f.read() == datos
        # La reanudación pidió Range desde la mitad ya escrita.
        assert any(r == f"bytes={len(datos) // 2}-" for r in estado["rangos"])
    finally:
        servidor.shutdown()


def test_descarga_sin_cortes_una_sola_peticion(tmp_path):
    from antivirus_hogar_pc.core.updater import descargar_archivo

    datos = b"x" * 5000
    servidor, estado = _servidor_descarga(datos, cortes=0)
    try:
        url = f"http://127.0.0.1:{servidor.server_address[1]}/f.bin"
        destino = str(tmp_path / "f.bin")
        descargar_archivo(url, destino, reintentos=3, pausa=0.01)
        assert estado["peticiones"] == 1
        with open(destino, "rb") as f:
            assert f.read() == datos
    finally:
        servidor.shutdown()


def test_descarga_404_no_reintenta(tmp_path):
    import urllib.error

    from antivirus_hogar_pc.core.updater import descargar_archivo

    servidor, estado = _servidor_descarga(b"", modo="404")
    try:
        url = f"http://127.0.0.1:{servidor.server_address[1]}/no.exe"
        with pytest.raises(urllib.error.HTTPError):
            descargar_archivo(url, str(tmp_path / "no.exe"),
                              reintentos=3, pausa=0.01)
        assert estado["peticiones"] == 1
    finally:
        servidor.shutdown()


# === 3. Optimizar volúmenes: parser de progreso + lanzamiento oculto ==========

def test_parser_progreso_defrag_porcentaje_y_fase():
    from antivirus_hogar_pc.modules.system.smart_logic import (
        interpretar_progreso_optimizacion)

    p = interpretar_progreso_optimizacion(
        "Análisis: 100% completado.\nDesfragmentando: pasada 2 - 37%")
    assert p.porcentaje == 37
    assert "pasada 2" in p.fase.lower()


def test_parser_progreso_trim_sin_porcentaje():
    from antivirus_hogar_pc.modules.system.smart_logic import (
        interpretar_progreso_optimizacion)

    p = interpretar_progreso_optimizacion("ReTrim: optimizando el volumen")
    assert p.porcentaje is None
    assert p.fase  # hay fase en texto aunque no haya % fiable


def test_parser_progreso_vacio_es_generico():
    from antivirus_hogar_pc.modules.system.smart_logic import (
        interpretar_progreso_optimizacion)

    p = interpretar_progreso_optimizacion("")
    assert p.porcentaje is None
    assert p.fase


def test_lanzamiento_elevado_es_oculto(monkeypatch):
    import subprocess

    from antivirus_hogar_pc.winapi import powershell

    monkeypatch.setattr(powershell, "es_windows", lambda: True)
    capturado = {}

    class _Proc:
        returncode = 0
        stdout = "4321"
        stderr = ""

    def _run(args, **kwargs):
        capturado["args"] = args
        capturado["kwargs"] = kwargs
        return _Proc()

    monkeypatch.setattr(subprocess, "run", _run)
    pid = powershell.lanzar_elevado_oculto("Optimize-Volume -DriveLetter C")
    assert pid == 4321
    comando = " ".join(capturado["args"])
    assert "-WindowStyle Hidden" in comando  # la ventana NO se abre
    assert capturado["kwargs"].get("creationflags", 0) == \
        getattr(subprocess, "CREATE_NO_WINDOW", 0)


def test_optimizar_volumen_progreso_y_resultado(monkeypatch):
    """v1.0.15: la vía es defrag.exe — el guion falso deja su salida
    con % y el resultado con EXITCODE=0; el veredicto es el cierto
    («Optimización finalizada») y el progreso sale de defrag."""
    from antivirus_hogar_pc.winapi import disks

    monkeypatch.setattr(disks, "es_windows", lambda: True)
    rutas = {}

    def _script(letra, es_ssd, ruta_salida, ruta_resultado):
        rutas["salida"] = ruta_salida
        rutas["resultado"] = ruta_resultado
        return "script"

    def _lanzar(script):
        def _trabajo():
            time.sleep(0.15)
            with open(rutas["salida"], "w", encoding="utf-8") as f:
                f.write("Defragmentation: 42%\n")
            time.sleep(0.15)
            with open(rutas["resultado"], "w", encoding="utf-8") as f:
                f.write("PRECHECK=OK\nEXITCODE=0\n")

        threading.Thread(target=_trabajo, daemon=True).start()
        return 999

    monkeypatch.setattr(disks, "_script_defrag", _script)
    monkeypatch.setattr(disks, "lanzar_elevado_oculto", _lanzar)
    monkeypatch.setattr(disks, "_proceso_vivo", lambda pid: True)
    eventos = []
    res = disks.optimizar_volumen(
        "C", False,
        al_progreso=lambda fase, pct: eventos.append((fase, pct)),
        timeout=30, intervalo=0.05)
    assert res["ok"] is True
    assert res["mensaje"].startswith("Optimización finalizada")
    assert any(pct == 42 for _f, pct in eventos), eventos
    assert eventos[-1] == ("Completado", 100)


def test_pagina_discos_muestra_progreso_optimizacion(monkeypatch):
    app = _app()
    from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo
    from antivirus_hogar_pc.modules.system import page as pagina_discos
    from antivirus_hogar_pc.modules.system import servicios_sistema as svc

    monkeypatch.setattr(
        svc, "salud_discos",
        lambda: ResultadoModulo(ok=True, mensaje="Listo.", datos={
            "discos": [], "fisicos": [],
            "volumenes": [{"letra": "C", "etiqueta": "Windows",
                           "libre": 10, "tamano": 100}]}))
    monkeypatch.setattr(svc, "tipo_de_volumen", lambda f, v: "HDD")

    def _optimizar(letra, es_ssd, al_progreso=None):
        al_progreso("Desfragmentando pasada 1", 42)
        return ResultadoModulo(
            ok=True, mensaje="Windows optimizó la unidad C: en segundo plano.")

    monkeypatch.setattr(svc, "optimizar_volumen", _optimizar)
    monkeypatch.setattr(pagina_discos, "_confirmar", lambda *a: True)
    pagina = pagina_discos.crear_pagina_discos(
        ContextoModulo(servicios=None))
    from PySide6.QtWidgets import QPushButton

    btn_analizar = next(b for b in pagina.findChildren(QPushButton)
                        if b.text() == "Analizar discos")
    btn_analizar.click()
    assert _esperar(app, lambda: len(pagina._botones_opt) == 1)
    pagina._botones_opt[0].click()
    assert _esperar(
        app, lambda: "optimizó" in pagina._lbl_opt.text())
    pagina.deleteLater()
    app.processEvents()


# === 4. Velocidad en vivo =======================================================

class _RelojFalso:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += 0.2
        return self.t


class _TransporteFalso:
    def descargar(self, url, timeout, al_bloque):
        if "bytes=0" in url:
            return 0
        total = 0
        for _ in range(5):
            total += 2_000_000
            al_bloque(total)
        return total

    def subir(self, url, datos, timeout, al_bloque):
        total = 0
        for _ in range(4):
            total += 1_000_000
            al_bloque(total)
        return total


def test_velocidad_en_vivo_emite_durante_y_mide_ambas():
    from antivirus_hogar_pc.core.velocidad import medir_velocidad_en_vivo

    eventos = []
    res = medir_velocidad_en_vivo(
        al_progreso=lambda fase, mbps: eventos.append((fase, mbps)),
        transporte=_TransporteFalso(), reloj=_RelojFalso(),
        bytes_bajada=5000, bytes_subida=2000)
    assert res["ok"] is True
    assert res["bajada_mbps"] > 0 and res["subida_mbps"] > 0
    fases = [f for f, _m in eventos]
    # DURANTE: más de un aviso de bajada y la bajada va antes que la subida.
    assert fases.count("bajada") >= 2
    assert fases.index("bajada") < fases.index("subida")


def test_velocidad_sin_conexion_da_causa():
    from antivirus_hogar_pc.core.velocidad import medir_velocidad_en_vivo

    class _TransporteCaido:
        def descargar(self, url, timeout, al_bloque):
            raise OSError("sin red")

        def subir(self, url, datos, timeout, al_bloque):
            raise OSError("sin red")

    res = medir_velocidad_en_vivo(transporte=_TransporteCaido(),
                                  reloj=_RelojFalso())
    assert res["ok"] is False
    assert res["causa"]


# === 5. Wi-Fi: parseo + frecuencia ==============================================

_NETSH_ES = """Nombre                   : Wi-Fi
Descripción              : Intel Wireless
Estado                   : conectado
SSID                     : CasaGuerra
Tipo de red              : Infraestructura
Tipo de radio            : 802.11ac
Autenticación            : WPA2-Personal
Cifrado                  : CCMP
Banda                    : 5 GHz
Canal                    : 36
Velocidad de recepción (Mbps) : 866.7
Velocidad de transmisión (Mbps) : 866,7
Señal                    : 92%
"""


def test_wifi_parsea_ssid_senal_canal_y_enlace():
    from antivirus_hogar_pc.core.wifi_parse import (
        frecuencia_mhz, parsear_netsh_wlan)

    info = parsear_netsh_wlan(_NETSH_ES)
    assert info.ssid == "CasaGuerra"
    assert info.conectada is True
    assert info.senal_pct == 92
    assert info.canal == "36"
    assert info.velocidad_rx_mbps == 866.7
    assert info.velocidad_tx_mbps == 866.7  # coma decimal tolerada
    assert frecuencia_mhz(info.banda, info.canal) == 5180
    assert frecuencia_mhz("2.4 GHz", "6") == 2437


def test_wifi_sin_interfaz_no_inventa():
    from antivirus_hogar_pc.core.wifi_parse import parsear_netsh_wlan

    info = parsear_netsh_wlan(
        "No hay ninguna interfaz inalámbrica en el sistema.")
    assert info.conectada is False
    assert info.ssid == ""


# === 6. Wi-Fi interactivo en la página ==========================================

def _pagina_red_con_parches(monkeypatch, informe):
    from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo
    from antivirus_hogar_pc.modules.net import page as pagina_red
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    monkeypatch.setattr(srv, "informe_wifi", lambda: informe)
    monkeypatch.setattr(
        srv, "ip_publica",
        lambda: ResultadoModulo(ok=True, datos={"ip": "1.2.3.4"}))
    monkeypatch.setattr(
        srv, "estado_vpn",
        lambda: ResultadoModulo(ok=True, datos={"conectada": False}))
    monkeypatch.setattr(
        srv, "descargar_servidores_completos",
        lambda: srv.servidores_semilla())
    return pagina_red, ContextoModulo(servicios=None)


def test_pagina_wifi_muestra_ssid_y_detalles(monkeypatch):
    app = _app()
    from antivirus_hogar_pc.contracts import ResultadoModulo
    from antivirus_hogar_pc.core.wifi_parse import InfoWifi

    info = InfoWifi(nombre="Wi-Fi", ssid="CasaGuerra", senal_pct=92,
                    banda="5 GHz", canal="36", tipo_radio="802.11ac",
                    autenticacion="WPA2-Personal", cifrado="CCMP",
                    velocidad_rx_mbps=866.7, velocidad_tx_mbps=433.3)
    informe = ResultadoModulo(ok=True, datos={
        "info": info, "nivel": "bien", "frase": "Señal excelente.",
        "perfiles_guardados": ["CasaGuerra"], "perfil_red": "Privada",
        "red_local": {"interfaz": "Wi-Fi", "ip": "192.168.1.50",
                      "puerta_enlace": "192.168.1.1",
                      "dns": ["1.1.1.1", "8.8.8.8"]}})
    pagina_red, ctx = _pagina_red_con_parches(monkeypatch, informe)
    pagina = pagina_red._PaginaRed(ctx)
    _scroll = pagina.widget()
    from PySide6.QtWidgets import QPushButton

    btn = next(b for b in _scroll.findChildren(QPushButton)
               if b.text() == "Actualizar datos de Wi-Fi")
    btn.click()
    assert _esperar(app, lambda: "CasaGuerra" in pagina._btn_red_wifi.text())
    assert pagina._wifi_valores["ssid"].text() == "CasaGuerra"
    assert pagina._wifi_valores["senal"].text() == "92 %"
    assert pagina._wifi_valores["frecuencia"].text() == "5180 MHz"
    assert pagina._wifi_valores["ip"].text() == "192.168.1.50"
    assert pagina._wifi_valores["puerta"].text() == "192.168.1.1"
    assert "1.1.1.1" in pagina._wifi_valores["dns"].text()
    assert "866.7" in pagina._wifi_valores["enlace"].text()
    # Interactivo: el panel arranca oculto y se despliega al tocar.
    assert pagina._panel_wifi.isHidden()
    pagina._btn_red_wifi.setChecked(True)
    assert not pagina._panel_wifi.isHidden()
    assert _esperar(app, lambda: not pagina._trabajos)
    pagina.deleteLater()
    app.processEvents()


def test_pagina_wifi_por_cable_lo_dice_claro(monkeypatch):
    app = _app()
    from antivirus_hogar_pc.contracts import ResultadoModulo
    from antivirus_hogar_pc.core.wifi_parse import InfoWifi

    informe = ResultadoModulo(ok=True, datos={
        "info": InfoWifi(), "nivel": "sin_datos", "frase": "",
        "perfiles_guardados": [], "perfil_red": "",
        "red_local": {"interfaz": "Ethernet", "ip": "192.168.1.60",
                      "puerta_enlace": "192.168.1.1", "dns": []}})
    pagina_red, ctx = _pagina_red_con_parches(monkeypatch, informe)
    pagina = pagina_red._PaginaRed(ctx)
    _scroll = pagina.widget()
    from PySide6.QtWidgets import QPushButton

    btn = next(b for b in _scroll.findChildren(QPushButton)
               if b.text() == "Actualizar datos de Wi-Fi")
    btn.click()
    assert _esperar(
        app, lambda: "Sin red Wi-Fi" in pagina._btn_red_wifi.text())
    assert "cable" in pagina._lbl_wifi_detalle.text()
    assert pagina._wifi_valores["ip"].text() == "192.168.1.60"
    assert _esperar(app, lambda: not pagina._trabajos)
    pagina.deleteLater()
    app.processEvents()


def test_pagina_velocidad_en_vivo(monkeypatch):
    app = _app()
    from antivirus_hogar_pc.contracts import ResultadoModulo
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    def _viva(al_progreso=None):
        al_progreso("bajada", 40.0)
        al_progreso("bajada", 82.5)
        al_progreso("subida", 21.0)
        return ResultadoModulo(ok=True, datos={
            "ping_ms": 12, "bajada_mbps": 82.5, "subida_mbps": 21.0})

    monkeypatch.setattr(srv, "prueba_velocidad_viva", _viva)
    pagina_red, ctx = _pagina_red_con_parches(
        monkeypatch, ResultadoModulo(ok=False, mensaje="sin wifi"))
    pagina = pagina_red._PaginaRed(ctx)
    _scroll = pagina.widget()
    from PySide6.QtWidgets import QPushButton

    btn = next(b for b in _scroll.findChildren(QPushButton)
               if b.text() == "Medir velocidad")
    btn.click()
    assert _esperar(app, lambda: pagina._val_bajada.text() == "82.5 Mbps")
    assert pagina._val_subida.text() == "21.0 Mbps"
    assert pagina._val_ping.text() == "12 ms"
    assert _esperar(app, lambda: not pagina._trabajos)
    pagina.deleteLater()
    app.processEvents()


# === 7. VPN Gate: cadena con plazo, semilla y página =============================

_CSV_VPN = """#HostName,IP,Score,Ping,Speed,CountryLong,CountryShort,NumVpnSessions,Uptime,TotalUsers,TotalTraffic,LogType,Operator,Message,OpenVPN_ConfigData_Base64
JP1,203.0.113.1,100,10,5000000,Japan,JP,1,2,3,4,2weeks,op,,ZA==
JP2,203.0.113.2,90,20,4000000,Japan,JP,1,2,3,4,2weeks,op,,ZA==
US1,198.51.100.1,80,30,3000000,United States,US,1,2,3,4,2weeks,op,,ZA==
"""


def test_vpn_cadena_respeta_el_plazo_total():
    from antivirus_hogar_pc.core.vpngate import descargar_lista_con_respaldo

    reloj_falso = {"t": 0.0}
    llamadas = {"n": 0}

    def _reloj():
        reloj_falso["t"] += 40.0
        return reloj_falso["t"]

    def _descargador_lento(url, timeout):
        llamadas["n"] += 1
        raise OSError("gotea")

    with pytest.raises(RuntimeError):
        descargar_lista_con_respaldo(
            ["https://a", "https://b", "http://c"],
            descargador=_descargador_lento, dormir=lambda s: None,
            plazo_total=75.0, reloj=_reloj)
    # Con el plazo, la cadena se rinde tras ~2 intentos (75 s de reloj
    # simulado) en vez de estirar 3 URLs × reintentos sin fin.
    assert llamadas["n"] <= 3


def test_vpn_semilla_local_tiene_servidores_y_paises():
    from antivirus_hogar_pc import config
    from antivirus_hogar_pc.core.vpngate import leer_semilla_vpngate

    servidores, _fecha = leer_semilla_vpngate(config.carpeta_activos())
    assert len(servidores) >= 30
    assert len({s.pais for s in servidores}) >= 5


def test_vpn_pagina_semilla_primero_y_barra_temporal(monkeypatch):
    app = _app()
    from antivirus_hogar_pc.contracts import ResultadoModulo
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    pagina_red, ctx = _pagina_red_con_parches(
        monkeypatch, ResultadoModulo(ok=False, mensaje="sin wifi"))

    def _lenta():
        time.sleep(0.4)
        base = srv.servidores_semilla()
        datos = dict(base.datos or {})
        datos["es_semilla"] = False
        return ResultadoModulo(
            ok=True,
            mensaje="35 servidores · 9 países · Fuente: VPN Gate en vivo",
            datos=datos)

    monkeypatch.setattr(srv, "descargar_servidores_completos", _lenta)
    pagina = pagina_red._PaginaRed(ctx)
    _scroll = pagina.widget()
    # La página pide la lista sola al abrirse (QTimer 0): la semilla
    # puebla el desplegable SIN esperar a la red.
    assert _esperar(app, lambda: pagina._combo_pais.count() > 5,
                    segundos=3)
    assert not pagina._barra_vpn.isHidden()  # actualizando: barra visible
    assert _esperar(app, lambda: not pagina._trabajos)
    assert pagina._barra_vpn.isHidden()  # al terminar desaparece
    assert "Fuente:" in pagina._lbl_vpn.text()
    pagina.deleteLater()
    app.processEvents()


# === 8. Drivers: cadena Catálogo → WU → almacén, causa breve ====================

_HTML_CATALOGO = """<html><body><table>
<tr><td>Title</td><td>Products</td><td>Classification</td>
<td>Last Updated</td><td>Version</td><td>Size</td></tr>
<tr><td>Realtek - Net - 10.60.615.2022</td><td>Windows 10 and later</td>
<td>Drivers</td><td>7/14/2023</td><td>10.60.615.2022</td><td>5 MB</td></tr>
</table></body></html>"""


def _driver(nombre="Adaptador de red", version="10.60.615.2022",
            fecha="14/07/2023", fabricante="Realtek", inf="oem1.inf",
            device_id=r"PCI\VEN_10EC&DEV_8168&SUBSYS_833110F7&REV_31\4&1"):
    from antivirus_hogar_pc.core.drivers_logic import DriverInstalado

    return DriverInstalado(nombre, version, fecha, fabricante, inf,
                           device_id, True)


def test_catalogo_parsea_y_confirma_sin_windows_update():
    from antivirus_hogar_pc.core.drivers_logic import (
        parsear_catalogo_html, veredicto_catalogo)

    resultados = parsear_catalogo_html(_HTML_CATALOGO)
    assert len(resultados) == 1
    assert resultados[0]["version"] == "10.60.615.2022"
    veredicto = veredicto_catalogo(_driver(), resultados)
    assert veredicto is not None and veredicto.estado == "al_dia"
    assert veredicto.fuente == "Catálogo de Microsoft"


def test_catalogo_detecta_version_mas_nueva():
    from antivirus_hogar_pc.core.drivers_logic import (
        parsear_catalogo_html, veredicto_catalogo)

    viejo = _driver(version="1.0", fecha="01/01/2020")
    veredicto = veredicto_catalogo(viejo, parsear_catalogo_html(_HTML_CATALOGO))
    assert veredicto is not None
    assert veredicto.estado == "hay_uno_mas_nuevo"


def test_cadena_consulta_todas_las_fuentes_y_manda_la_mas_reciente(monkeypatch):
    """v1.0.18 (nota 10) — SUSTITUYE a
    test_cadena_confirma_por_catalogo_sin_llamar_a_wu (v1.0.5).

    El usuario ordenó expresamente consultar TODAS las fuentes
    para CADA driver y quedarse con la versión más reciente:
    aunque el Catálogo confirme «al día», Windows Update se
    consulta igual, y si ofrece una versión más nueva, ESE es el
    veredicto final, con su fuente indicada."""
    from antivirus_hogar_pc.core.drivers_logic import EstadoDriver
    from antivirus_hogar_pc.modules.system import servicios_sistema as svc
    from antivirus_hogar_pc.winapi import drivers_win

    d = _driver()  # instalada: 10.60.615.2022
    monkeypatch.setattr(
        svc, "_confirmar_por_catalogo",
        lambda drv: EstadoDriver(driver=drv, estado="al_dia",
                                 fuente="Catálogo de Microsoft",
                                 detalle="Confirmado por el Catálogo."))
    llamadas = []

    def _wu(*a, **k):
        llamadas.append(1)
        return [{"titulo": "Realtek Driver 99.0",
                 "id_hardware": [r"PCI\VEN_10EC&DEV_8168"],
                 "version": "99.0", "fecha": "2024-01-01"}]

    monkeypatch.setattr(drivers_win, "buscar_drivers_windows_update", _wu)
    monkeypatch.setattr(drivers_win, "paquetes_almacen_drivers", lambda: [])
    res = svc.escanear_drivers_paso2_buscar([d])
    assert llamadas, "Windows Update debió consultarse aunque el " \
                     "Catálogo ya había confirmado"
    estado = res.datos["estados"][0]
    assert estado.estado == "hay_uno_mas_nuevo"
    assert estado.fuente == "Windows Update"
    assert estado.version_candidata == "99.0"
    assert res.datos["conteos_fuentes"]["catalogo"] == 1
    assert res.datos["conteos_fuentes"]["windows_update"] == 1


def test_cadena_wu_agota_tiempo_y_la_cadena_sigue(monkeypatch):
    from antivirus_hogar_pc.core.drivers_logic import EstadoDriver
    from antivirus_hogar_pc.modules.system import servicios_sistema as svc
    from antivirus_hogar_pc.winapi import drivers_win

    d1, d2 = _driver(), _driver(nombre="Audio", device_id=r"USB\VID_1&X\2")
    monkeypatch.setattr(
        svc, "_confirmar_por_catalogo",
        lambda d: EstadoDriver(driver=d, estado="al_dia",
                               fuente="Catálogo de Microsoft")
        if d is d1 else None)

    def _wu_caido(*a, **k):
        raise TimeoutError(
            "Command 'powershell -Command $s = New-Object -ComObject "
            "Microsoft.Update.Session...' timed out after 900 seconds")

    monkeypatch.setattr(drivers_win, "buscar_drivers_windows_update",
                        _wu_caido)
    monkeypatch.setattr(drivers_win, "paquetes_almacen_drivers", lambda: [])
    res = svc.escanear_drivers_paso2_buscar([d1, d2])
    estados = {e.driver.dispositivo: e for e in res.datos["estados"]}
    assert estados["Adaptador de red"].estado == "al_dia"  # por Catálogo
    assert estados["Audio"].estado == "sin_datos"
    # La causa de la UI es breve y NO contiene el comando crudo.
    assert res.datos["causa_breve"] == \
        "Windows Update no respondió en el tiempo límite."
    assert "powershell" not in estados["Audio"].detalle.lower()
    assert "Microsoft.Update.Session" in res.datos["wu_causa"]  # dato técnico


def test_cadena_todas_las_fuentes_caen_causa_breve(monkeypatch):
    from antivirus_hogar_pc.modules.system import servicios_sistema as svc
    from antivirus_hogar_pc.winapi import drivers_win

    monkeypatch.setattr(svc, "_confirmar_por_catalogo", lambda d: None)
    monkeypatch.setattr(
        drivers_win, "buscar_drivers_windows_update",
        lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("HRESULT 0x80240022 powershell -Command secreto")))
    monkeypatch.setattr(drivers_win, "paquetes_almacen_drivers", lambda: [])
    res = svc.escanear_drivers_paso2_buscar([_driver()])
    estado = res.datos["estados"][0]
    assert estado.estado == "sin_datos"
    textos_ui = (res.mensaje + estado.detalle
                 + res.datos["causa_breve"]).lower()
    assert "powershell" not in textos_ui
    assert "0x80240022" not in textos_ui
    assert res.datos["causa_breve"] == \
        "Windows Update devolvió un error al buscar."
    assert "0x80240022" in res.detalle_tecnico  # solo al registro


def test_causa_breve_nunca_devuelve_el_comando():
    from antivirus_hogar_pc.core.drivers_logic import causa_breve_drivers

    cruda = ("Command 'powershell.exe -Command $s = New-Object "
             "-ComObject Microsoft.Update.Session' timed out")
    breve = causa_breve_drivers(cruda)
    assert breve == "Windows Update no respondió en el tiempo límite."
    assert "$" not in breve and "powershell" not in breve.lower()


def test_hwid_extraccion():
    from antivirus_hogar_pc.core.drivers_logic import (
        es_hwid_buscable, extraer_hwid)

    hwid = extraer_hwid(
        r"PCI\VEN_10EC&DEV_8168&SUBSYS_833110F7&REV_31\4&123&0&00E0")
    assert hwid == r"PCI\VEN_10EC&DEV_8168&SUBSYS_833110F7"
    assert es_hwid_buscable(hwid)
    assert not es_hwid_buscable("ID1")


# === 9. Iconos 3D, tema cristal y radar militar ==================================

def test_iconos_nav_son_grandes_y_en_colores():
    app = _app()
    from PySide6.QtGui import QImage

    from antivirus_hogar_pc.ui.iconos_nav import LADO, PALETA_NAV, pixmap_nav

    assert LADO >= 30
    for nombre in PALETA_NAV:
        pm = pixmap_nav(nombre)
        assert not pm.isNull()
        img = pm.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        colores = set()
        for x in range(0, img.width(), 3):
            for y in range(0, img.height(), 3):
                c = img.pixelColor(x, y)
                if c.alpha() > 200:
                    colores.add((c.red() // 32, c.green() // 32,
                                 c.blue() // 32))
        assert len(colores) >= 4, f"{nombre}: icono casi plano {colores}"


def test_animador_respeta_interruptor_apagado():
    app = _app()
    from PySide6.QtWidgets import QPushButton

    from antivirus_hogar_pc.ui.iconos_nav import AnimadorIconoNav

    boton = QPushButton("Inicio")
    animador = AnimadorIconoNav(boton, "inicio", animado=False)
    animador.fijar_activo(True)
    assert not animador.animando()  # apagado = estático, sin temporizador
    assert not boton.icon().isNull()
    boton.deleteLater()
    app.processEvents()


def test_tema_es_cristal_con_gradientes():
    from antivirus_hogar_pc.ui import theme

    assert "qlineargradient" in theme.QSS
    assert "rgba(" in theme.QSS  # paneles semitransparentes de cristal


def test_radar_militar_verde_con_amenazas():
    app = _app()
    from PySide6.QtGui import QImage

    from antivirus_hogar_pc.ui.fondo_radar import FondoRadar

    radar = FondoRadar(animado=False)
    assert radar.minimumHeight() >= 280  # escáner un poco más grande
    assert len(radar._amenazas) >= 10
    assert {a.tipo for a in radar._amenazas} <= {"virus", "bicho", "archivo"}
    radar.resize(560, 300)
    radar.show()
    app.processEvents()
    img = radar.grab().toImage().convertToFormat(QImage.Format.Format_RGB32)
    verdes = 0
    for x in range(0, img.width(), 6):
        for y in range(0, img.height(), 6):
            c = img.pixelColor(x, y)
            if c.green() > c.red() + 12 and c.green() > c.blue() + 6:
                verdes += 1
    assert verdes > 200  # domina el verde visión nocturna
    radar.deleteLater()
    app.processEvents()


# === 10. Icono espartano de la app ===============================================

def test_icono_espartano_multirresolucion():
    import struct

    ruta = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "packaging", "icono.ico"))
    datos = open(ruta, "rb").read()
    _res, _tipo, n = struct.unpack_from("<HHH", datos, 0)
    tamanos = set()
    for i in range(n):
        ancho, alto = struct.unpack_from("<BB", datos, 6 + i * 16)
        tamanos.add((ancho or 256, alto or 256))
    assert (256, 256) in tamanos
    assert (48, 48) in tamanos
    assert (16, 16) in tamanos
    assert len(datos) > 50_000  # una imagen real, no un glyph


def test_spec_e_instalador_usan_el_icono():
    raiz = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
    with open(os.path.join(raiz, "packaging", "antivirus-hogar-pc.spec"),
              encoding="utf-8") as f:
        assert 'icon=os.path.join(RAIZ, "packaging", "icono.ico")' in f.read()
    with open(os.path.join(raiz, "packaging", "instalador.iss"),
              encoding="utf-8") as f:
        assert "SetupIconFile=icono.ico" in f.read()


# === 11. Versión de la app ========================================================

def test_pagina_version_muestra_la_actual_y_sus_notas():
    app = _app()
    from PySide6.QtWidgets import QLabel

    from antivirus_hogar_pc import config
    from antivirus_hogar_pc.contracts import ContextoModulo
    from antivirus_hogar_pc.core.notas_version import notas_de
    from antivirus_hogar_pc.ui.version_page import crear_pagina_version

    pagina = crear_pagina_version(ContextoModulo(servicios=None))
    textos = [l.text() for l in pagina.findChildren(QLabel)]
    assert any(config.VERSION in t for t in textos)
    notas = notas_de(config.VERSION)
    assert notas and notas["novedades"]
    assert any(notas["novedades"][0][:30] in t for t in textos)
    # v1.0.18 (nota 5): la página de versión ya NO mezcla el
    # historial — vive en su propia página «Historial de la
    # aplicación», que sí lo trae completo.
    assert not any("1.0.4" in t for t in textos)
    pagina.deleteLater()
    from antivirus_hogar_pc.ui.historial_page import (
        crear_pagina_historial)

    pagina_h = crear_pagina_historial(ContextoModulo(servicios=None))
    textos_h = [l.text() for l in pagina_h.findChildren(QLabel)]
    assert any("1.0.4" in t for t in textos_h)
    assert any(config.VERSION in t for t in textos_h)
    pagina_h.deleteLater()
    app.processEvents()


def test_ventana_tiene_entradas_nuevas_tras_informes():
    app = _app()
    from PySide6.QtWidgets import QPushButton

    from antivirus_hogar_pc.ui.main_window import VentanaPrincipal
    from antivirus_hogar_pc.ui.services import ServiciosApp

    ventana = VentanaPrincipal(ServiciosApp())
    textos = [b.text() for b in ventana.findChildren(QPushButton)]
    assert "Versión de la app" in textos
    assert "Programador de tareas" in textos
    assert textos.index("Informes") < textos.index("Versión de la app")
    assert textos.index("Versión de la app") < \
        textos.index("Programador de tareas")
    assert textos.index("Programador de tareas") < textos.index("Ajustes")
    for clave in ("version", "programar", "panel"):
        boton = ventana._botones[clave]
        assert not boton.icon().isNull()
        assert boton.iconSize().width() >= 30
    ventana.ir_a("version")
    app.processEvents()
    ventana.ir_a("programar")
    app.processEvents()
    ventana.deleteLater()
    app.processEvents()


# === 12. Arranque con Windows + rutina automática =================================

def test_arranque_script_escribe_y_retira(monkeypatch):
    from antivirus_hogar_pc.winapi import arranque

    script_on = arranque.script_fijar_arranque(True, r"C:\App\AntivirusHogarPC.exe")
    assert "Set-ItemProperty" in script_on
    assert "--inicio-automatico" in script_on
    assert arranque.NOMBRE_VALOR in script_on
    script_off = arranque.script_fijar_arranque(False, r"C:\App\AntivirusHogarPC.exe")
    assert "Remove-ItemProperty" in script_off


def test_arranque_se_aplica_segun_interruptor(monkeypatch):
    from antivirus_hogar_pc.winapi import arranque

    llamadas = []
    monkeypatch.setattr(arranque, "es_windows", lambda: True)
    monkeypatch.setattr(
        arranque, "ejecutar_powershell",
        lambda script, timeout=60: llamadas.append(script) or "")
    arranque.fijar_arranque_windows(True, r"C:\App\A.exe")
    arranque.fijar_arranque_windows(False, r"C:\App\A.exe")
    assert "Set-ItemProperty" in llamadas[0]
    assert "Remove-ItemProperty" in llamadas[1]


def test_rutina_corre_en_fondo_y_deja_resumen(tmp_path, monkeypatch):
    from antivirus_hogar_pc import config
    from antivirus_hogar_pc.ui import rutina_auto

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    registros = []
    tareas = {
        "escaneo": lambda: "Escaneo rápido: 10 archivos, 0 hallazgos",
        "drivers": lambda: (_ for _ in ()).throw(RuntimeError("WU caído")),
        "limpieza": lambda: "Limpieza segura: 3 archivos borrados",
    }
    resumen = rutina_auto.ejecutar_rutina(
        tareas, lambda tipo, detalle: registros.append((tipo, detalle)),
        rutina_auto._escribir_resumen_archivo, ahora=lambda: 123.0)
    # Una tarea caída no detiene a las demás; todo queda registrado.
    assert resumen["resultados"]["escaneo"]["ok"] is True
    assert resumen["resultados"]["drivers"]["ok"] is False
    assert resumen["resultados"]["limpieza"]["ok"] is True
    assert len(registros) == 3
    assert all(t == "rutina-automatica" for t, _d in registros)
    guardado = rutina_auto.leer_resumen_rutina()
    assert guardado is not None and guardado["cuando"] == 123.0
    assert config.carpeta_datos()  # la carpeta usada es la de pruebas


def test_ajustes_arranque_y_rutina_por_defecto():
    from antivirus_hogar_pc.ui.services import Ajustes

    ajustes = Ajustes()
    assert ajustes.arranque_windows is True
    assert ajustes.rutina_automatica is True


# === 13. Programador de tareas =====================================================

def test_proxima_ejecucion_diaria():
    import datetime as dt

    from antivirus_hogar_pc.core.programaciones import (
        Programacion, proxima_ejecucion)

    prog = Programacion("firmas", activa=True, frecuencia="diaria",
                        hora="10:00")
    antes = dt.datetime(2026, 11, 24, 9, 0)   # martes 09:00
    assert proxima_ejecucion(prog, antes) == dt.datetime(2026, 11, 24, 10, 0)
    despues = dt.datetime(2026, 11, 24, 11, 0)
    assert proxima_ejecucion(prog, despues) == dt.datetime(2026, 11, 25, 10, 0)


def test_proxima_ejecucion_semanal():
    import datetime as dt

    from antivirus_hogar_pc.core.programaciones import (
        Programacion, proxima_ejecucion)

    prog = Programacion("escaneo-rapido", activa=True,
                        frecuencia="semanal", dia="domingo", hora="10:00")
    martes = dt.datetime(2026, 11, 24, 9, 0)  # 24/11/2026 es martes
    assert martes.weekday() == 1
    proxima = proxima_ejecucion(prog, martes)
    assert proxima == dt.datetime(2026, 11, 29, 10, 0)  # domingo 29
    domingo_tarde = dt.datetime(2026, 11, 29, 11, 0)
    assert proxima_ejecucion(prog, domingo_tarde) == \
        dt.datetime(2026, 12, 6, 10, 0)  # la semana siguiente
    inactiva = Programacion("drivers", activa=False)
    assert proxima_ejecucion(inactiva, martes) is None


def test_programaciones_persisten_en_ajustes(monkeypatch, tmp_path):
    from antivirus_hogar_pc.core.programaciones import (
        a_dicts, buscar, desde_dicts)
    from antivirus_hogar_pc.ui.services import Ajustes

    ajustes, ruta = _cargar_ajustes(monkeypatch, tmp_path, None)
    lista = desde_dicts(ajustes.programaciones)
    assert len(lista) == 6  # siempre las seis conocidas
    escaneo = buscar(lista, "escaneo-rapido")
    escaneo.hora = "07:30"
    escaneo.dia = "sábado"
    drivers = buscar(lista, "drivers")
    drivers.activa = True
    ajustes.programaciones = a_dicts(lista)
    ajustes.guardar()
    recargados = Ajustes.cargar()
    lista2 = desde_dicts(recargados.programaciones)
    assert buscar(lista2, "escaneo-rapido").hora == "07:30"
    assert buscar(lista2, "escaneo-rapido").dia == "sábado"
    assert buscar(lista2, "drivers").activa is True
    # Borrar una entrada guardada la devuelve a su valor por defecto.
    recargados.programaciones = [
        d for d in recargados.programaciones if d["id"] != "drivers"]
    lista3 = desde_dicts(recargados.programaciones)
    assert buscar(lista3, "drivers").activa is False


def test_disparador_ejecuta_la_tarea_y_registra():
    from antivirus_hogar_pc.core.programaciones import ejecutar_tarea_programada

    corridas = []
    registros = []
    guardados = {}

    def _tarea():
        corridas.append("firmas")
        return "Firmas actualizadas: 10 huellas."

    resultado = ejecutar_tarea_programada(
        "firmas", {"firmas": _tarea},
        lambda tipo, detalle: registros.append((tipo, detalle)),
        lambda id_, res: guardados.update({id_: res}),
        ahora=lambda: 555.0)
    assert corridas == ["firmas"]
    assert resultado["ok"] is True and resultado["cuando"] == 555.0
    assert guardados["firmas"]["resumen"].startswith("Firmas actualizadas")
    assert registros and registros[0][0] == "programada"


def test_comando_schtasks_programada():
    from antivirus_hogar_pc.winapi.tasks import (
        comando_crear_tarea_programada, nombre_tarea_programada)

    cmd = comando_crear_tarea_programada(
        r"C:\App\AntivirusHogarPC.exe", "escaneo-rapido", "semanal",
        "domingo", "10:00")
    texto = " ".join(cmd)
    assert nombre_tarea_programada("escaneo-rapido") in texto
    assert "--tarea-programada escaneo-rapido" in texto
    assert "WEEKLY" in texto and "SUN" in texto and "10:00" in texto
    cmd_diaria = comando_crear_tarea_programada(
        r"C:\App\AntivirusHogarPC.exe", "firmas", "diaria", "lunes", "09:00")
    assert "DAILY" in " ".join(cmd_diaria)


# === 14. Humo: la app arranca por su entrada real =================================

def test_la_app_arranca_por_main_sin_errores(tmp_path):
    """main() completo en subproceso (offscreen): debe quedarse en el
    bucle de eventos, sin ImportError ni traceback (regresión: QTimer
    importado desde QtWidgets rompía el arranque del ejecutable)."""
    import subprocess
    import sys

    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["XDG_DATA_HOME"] = str(tmp_path)
    env["LOCALAPPDATA"] = str(tmp_path)
    raiz = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
    try:
        proc = subprocess.run(
            [sys.executable, "-c",
             "from antivirus_hogar_pc.ui.main import main; "
             "raise SystemExit(main(['AntivirusHogarPC']))"],
            cwd=raiz, env=env, capture_output=True, text=True, timeout=8)
        salida = (proc.stdout or "") + (proc.stderr or "")
        raise AssertionError(
            f"la app terminó sola (rc={proc.returncode}): {salida[-800:]}")
    except subprocess.TimeoutExpired as e:
        salida = ((e.stdout or b"").decode(errors="replace")
                  + (e.stderr or b"").decode(errors="replace"))
        assert "ImportError" not in salida
        assert "Traceback" not in salida
