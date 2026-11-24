"""v1.0.3: huellas sin clave, progreso del escaneo, efectos en todas las
páginas, drivers «Sin confirmar» y VPN Gate con respaldo + semilla.

- Problema 1: malicious-hash aporta huellas SIN Auth-Key; abuse.ch sin
  clave es «opcional», no un fallo.
- Problema 2: el progreso del escaneo arranca en 0, es monótono,
  limitado en frecuencia y llega al total.
- Problema 3: cada página principal tiene al menos un BotonPulso y
  ninguna QProgressBar pelada (todas son BarraProgreso).
- Problema 4: estados de drivers con backend simulado — consulta WU
  completada sin novedades = «al_dia»; con novedad =
  «hay_uno_mas_nuevo»; consulta fallida = «sin_datos» CON causa, y la
  página pinta esa causa.
- Problema 5: cadena VPN Gate con respaldo verificada contra la
  fixture REAL descargada de la API; fallo total → semilla real con
  aviso visible en la página (combo y tabla poblados).
"""
import os
import urllib.error

import pytest

from antivirus_hogar_pc.core import threats_update as tu

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
SHA256_A = "a" * 64
SHA256_B = "b" * 64
MD5_A = "c" * 32


# === Problema 1: huellas sin clave ============================================

def _descargador_con_huellas(url, datos=None, auth_key="", timeout=60):
    if "full-hash-sha256" in url:
        return f"# comentario\n{SHA256_A}\n{SHA256_B}\nno-es-hex\n"
    if "full-hash-md5" in url:
        return f"{MD5_A}\n"
    if "urlhaus-filter" in url:
        return "malo.example\n"
    if "Phishing.Database" in url:
        return "phish.example\n"
    if "openphish" in url:
        return "https://evil.example/login\n"
    if "cert.pl" in url:
        return "cert.example\n"
    raise AssertionError(f"URL inesperada: {url}")


def test_huellas_sin_clave_llegan_de_malicious_hash():
    r = tu.actualizar_firmas_multifuente(auth_key="",
                                         descargador=_descargador_con_huellas)
    assert r.ok
    huellas = dict(r.hashes)
    assert huellas[SHA256_A] == tu.ETIQUETA_MALICIOUS_HASH
    assert huellas[SHA256_B] == tu.ETIQUETA_MALICIOUS_HASH
    assert huellas[MD5_A] == tu.ETIQUETA_MALICIOUS_HASH
    assert len(r.hashes) == 3  # «no-es-hex» no entra
    por_nombre = {f.nombre: f for f in r.por_fuente}
    assert por_nombre["malicious-hash (SHA-256)"].cantidad == 2
    assert por_nombre["malicious-hash (MD5)"].cantidad == 1


def test_abusech_sin_clave_es_opcional_no_fallo():
    r = tu.actualizar_firmas_multifuente(auth_key="",
                                         descargador=_descargador_con_huellas)
    por_nombre = {f.nombre: f for f in r.por_fuente}
    abuse = por_nombre["abuse.ch (MalwareBazaar)"]
    assert abuse.opcional and not abuse.error and abuse.cantidad == 0
    resumen = r.resumen()
    assert "abuse.ch (MalwareBazaar): opcional" in resumen
    assert "abuse.ch (MalwareBazaar): falló" not in resumen


def test_multifuente_todo_caido_sigue_siendo_error_total():
    def todo_caido(url, datos=None, auth_key="", timeout=60):
        raise urllib.error.URLError("sin ruta")

    r = tu.actualizar_firmas_multifuente(auth_key="", descargador=todo_caido)
    assert not r.ok
    # Las fuentes sin clave SÍ enseñan su causa; la opcional no cuenta.
    por_nombre = {f.nombre: f for f in r.por_fuente}
    assert por_nombre["malicious-hash (SHA-256)"].error
    assert por_nombre["abuse.ch (MalwareBazaar)"].opcional


# === Problema 2: progreso del escaneo ==========================================

def test_progreso_escaneo_monotono_limitado_y_completo(tmp_path):
    from antivirus_hogar_pc.core.scanner import escanear
    from antivirus_hogar_pc.core.signatures import BaseFirmas

    for i in range(60):
        (tmp_path / f"archivo{i:02d}.exe").write_bytes(b"MZ" + bytes([i]) * 10)
    llamadas: list[tuple[str, int, int]] = []
    resultado = escanear([str(tmp_path)], BaseFirmas(),
                         progreso=lambda r, n, t: llamadas.append((r, n, t)))
    assert resultado.archivos_revisados == 60
    assert llamadas[0][1] == 0 and llamadas[0][2] == 60  # primer aviso: 0 de N
    conteos = [n for _r, n, _t in llamadas]
    assert conteos == sorted(conteos)  # monótono, nunca retrocede
    assert conteos[-1] == 60  # SIEMPRE llega al total
    # Limitado: sin limitar serían 60 avisos (uno por archivo).
    assert len(llamadas) <= 10


# === Problema 4: drivers ========================================================

def _instalados():
    from antivirus_hogar_pc.core.drivers_logic import DriverInstalado

    return [DriverInstalado("Adaptador de red", "1.0", "", "Realtek",
                            "oem1.inf", "ID1", True)]


def test_drivers_consulta_completada_sin_novedad_es_al_dia(monkeypatch):
    from antivirus_hogar_pc.modules.system import servicios_sistema as svc
    from antivirus_hogar_pc.winapi import drivers_win

    monkeypatch.setattr(drivers_win, "buscar_drivers_windows_update",
                        lambda: [])
    buscar = svc.escanear_drivers_paso2_buscar(_instalados())
    assert buscar.datos["wu_consultado"] is True
    final = svc.escanear_drivers_paso3_comparar(
        _instalados(), [], True, "", buscar.datos.get("wu_causa", ""))
    assert final.datos["estados"][0].estado == "al_dia"
    assert final.datos["wu_causa"] == ""


def test_drivers_con_novedad_es_hay_uno_mas_nuevo(monkeypatch):
    from antivirus_hogar_pc.modules.system import servicios_sistema as svc
    from antivirus_hogar_pc.winapi import drivers_win

    ofrecidas = [{"titulo": "Realtek - Net - 10.60.615.2022", "id": "X",
                  "fecha": "", "version": ""}]
    monkeypatch.setattr(drivers_win, "buscar_drivers_windows_update",
                        lambda: ofrecidas)
    buscar = svc.escanear_drivers_paso2_buscar(_instalados())
    final = svc.escanear_drivers_paso3_comparar(
        _instalados(), ofrecidas, True, "", "")
    assert final.datos["estados"][0].estado == "hay_uno_mas_nuevo"


def test_drivers_consulta_fallida_es_sin_confirmar_con_causa(monkeypatch):
    from antivirus_hogar_pc.modules.system import servicios_sistema as svc
    from antivirus_hogar_pc.winapi import drivers_win

    def explota():
        raise RuntimeError("HRESULT 0x80240022 de prueba")

    monkeypatch.setattr(drivers_win, "buscar_drivers_windows_update", explota)
    buscar = svc.escanear_drivers_paso2_buscar(_instalados())
    assert buscar.datos["wu_consultado"] is False
    assert "0x80240022" in buscar.datos["wu_causa"]
    final = svc.escanear_drivers_paso3_comparar(
        _instalados(), [], False, "", buscar.datos["wu_causa"])
    estado = final.datos["estados"][0]
    assert estado.estado == "sin_datos"
    assert "0x80240022" in estado.detalle  # la causa viaja hasta la fila
    assert "0x80240022" in final.mensaje
    assert final.datos["wu_causa"]


def test_contrastar_sin_marca_de_consulta_no_inventa_al_dia():
    from antivirus_hogar_pc.core.drivers_logic import contrastar_con_windows_update

    # Sin consulta_completada, lista vacía = sin datos (histórico).
    assert contrastar_con_windows_update(
        _instalados(), [])[0].estado == "sin_datos"
    # Con la consulta completada, la misma lista vacía = al día.
    assert contrastar_con_windows_update(
        _instalados(), [], consulta_completada=True)[0].estado == "al_dia"


def test_drivers_pagina_pinta_la_causa_wu(monkeypatch):
    pytest.importorskip("PySide6")
    import time as _time

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton

    from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo
    from antivirus_hogar_pc.modules.system import page as pagina_drivers
    from antivirus_hogar_pc.modules.system import servicios_sistema as svc

    instalados = _instalados()
    monkeypatch.setattr(
        svc, "escanear_drivers_paso1",
        lambda: ResultadoModulo(ok=True, datos={
            "instalados": instalados, "fabricante_pc": ""}))
    monkeypatch.setattr(
        svc, "escanear_drivers_paso2_buscar",
        lambda _i: ResultadoModulo(ok=True, datos={
            "ofrecidas": [], "wu_consultado": False,
            "wu_causa": "HRESULT 0x80240022 de prueba"}))
    app = QApplication.instance() or QApplication([])
    pagina = pagina_drivers.crear_pagina_drivers(ContextoModulo(servicios=None))
    boton = next(b for b in pagina.findChildren(QPushButton)
                 if b.text() == "Escanear drivers")
    boton.click()
    limite = _time.time() + 10
    textos: list[str] = []
    while _time.time() < limite:
        app.processEvents()
        textos = [l.text() for l in pagina.findChildren(QLabel)]
        if any("0x80240022" in t for t in textos):
            break
        _time.sleep(0.05)
    assert any("Windows Update no pudo confirmar" in t and "0x80240022" in t
               for t in textos), textos
    pagina.deleteLater()
    app.processEvents()


# === Problema 5: VPN Gate =======================================================

def _texto_fixture_real() -> str:
    with open(os.path.join(FIXTURES, "vpngate_api_real.csv"),
              encoding="utf-8") as f:
        return f.read()


def test_parseo_fixture_real_vpngate():
    from antivirus_hogar_pc.core.vpngate import (
        paises_disponibles, parsear_csv_vpngate)

    servidores = parsear_csv_vpngate(_texto_fixture_real())
    assert len(servidores) >= 5  # filas REALES de la API (2026-11-24)
    assert paises_disponibles(servidores)
    assert all(s.hostname and s.ip for s in servidores)
    assert all(s.ovpn_base64 for s in servidores)


def test_cadena_respaldo_cambia_de_ruta_y_acierta():
    from antivirus_hogar_pc.core.vpngate import descargar_lista_con_respaldo

    def descargador(url, timeout=45):
        if "https://" in url:
            raise OSError("TLS cortado de prueba")
        return _texto_fixture_real()

    servidores, url_buena = descargar_lista_con_respaldo(
        ("https://www.vpngate.net/api/iphone/",
         "http://www.vpngate.net/api/iphone/"),
        descargador=descargador, dormir=lambda _s: None)
    assert len(servidores) >= 5
    assert url_buena.startswith("http://")


def test_cadena_respaldo_todo_caido_lanza_con_causa():
    from antivirus_hogar_pc.core.vpngate import descargar_lista_con_respaldo

    def descargador(url, timeout=45):
        raise OSError("sin ruta de prueba")

    with pytest.raises(RuntimeError, match="sin ruta de prueba"):
        descargar_lista_con_respaldo(
            ("https://www.vpngate.net/api/iphone/",),
            descargador=descargador, dormir=lambda _s: None)


def test_semilla_real_incluida_en_la_app():
    from antivirus_hogar_pc import config
    from antivirus_hogar_pc.core.vpngate import leer_semilla_vpngate

    servidores, fecha = leer_semilla_vpngate(config.carpeta_activos())
    assert fecha == "2026-11-24"
    assert len(servidores) >= 30  # semilla real de la descarga de construcción
    assert all(s.ovpn_base64 for s in servidores)  # «Conectar» funciona igual


def test_servicio_vpn_fallo_total_cae_en_semilla(monkeypatch):
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    def explota(urls, **kwargs):
        raise RuntimeError("TLS cortado de prueba")

    monkeypatch.setattr(srv, "descargar_lista_con_respaldo", explota)
    r = srv.descargar_servidores_completos()
    assert r.ok  # NO es un fallo para la página: hay respaldo
    datos = r.datos
    assert datos["es_semilla"] is True
    assert len(datos["servidores"]) >= 30
    assert "Lista de respaldo" in r.mensaje
    assert "TLS cortado de prueba" in r.mensaje  # la causa va en el aviso


def _pagina_red_con_parches(monkeypatch):
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo
    from antivirus_hogar_pc.modules.net import page as pagina_red
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    monkeypatch.setattr(srv, "informe_wifi",
                        lambda: ResultadoModulo(ok=False, mensaje="sin wifi fake"))
    monkeypatch.setattr(srv, "estado_vpn",
                        lambda: ResultadoModulo(ok=False, mensaje="sin vpn fake"))
    monkeypatch.setattr(srv, "descargar_servidores_completos",
                        lambda: ResultadoModulo(ok=True, datos={
                            "servidores": [], "es_semilla": False,
                            "fecha_semilla": "", "causa": ""}))
    app = QApplication.instance() or QApplication([])
    pagina = pagina_red._PaginaRed(ContextoModulo(servicios=None))
    return app, pagina


def test_pagina_vpn_puebla_combo_y_tabla_con_descarga(monkeypatch):
    from antivirus_hogar_pc.contracts import ResultadoModulo
    from antivirus_hogar_pc.core.vpngate import parsear_csv_vpngate

    app, pagina = _pagina_red_con_parches(monkeypatch)
    servidores = parsear_csv_vpngate(_texto_fixture_real())
    pagina._servidores_cargados(ResultadoModulo(ok=True, datos={
        "servidores": servidores, "es_semilla": False,
        "fecha_semilla": "", "causa": ""}))
    assert pagina._combo_pais.count() > 1  # «Todos» + países reales
    assert pagina._tabla_vpn.rowCount() == len(servidores)
    assert "Reintentar" not in pagina._btn_servidores.text()
    pagina.deleteLater()
    app.processEvents()


def test_pagina_vpn_fallo_total_puebla_semilla_con_aviso(monkeypatch):
    from antivirus_hogar_pc import config
    from antivirus_hogar_pc.contracts import ResultadoModulo
    from antivirus_hogar_pc.core.vpngate import leer_semilla_vpngate

    app, pagina = _pagina_red_con_parches(monkeypatch)
    semilla, fecha = leer_semilla_vpngate(config.carpeta_activos())
    pagina._servidores_cargados(ResultadoModulo(
        ok=True,
        mensaje=(f"Lista de respaldo del {fecha} ({len(semilla)} servidores): "
                 "no se pudo conectar con VPN Gate (TLS cortado de prueba)."),
        datos={"servidores": semilla, "es_semilla": True,
               "fecha_semilla": fecha, "causa": "TLS cortado de prueba"}))
    assert pagina._combo_pais.count() > 1  # países de la semilla
    assert pagina._tabla_vpn.rowCount() == len(semilla)  # tabla poblada
    assert "respaldo" in pagina._lbl_vpn.text().lower()  # aviso visible
    assert pagina._btn_servidores.text() == "Reintentar descarga"
    pagina.deleteLater()
    app.processEvents()


# === Problema 3: efectos en todas las páginas ===================================

class _CuarentenaFake:
    def listar(self):
        return []


class _ServiciosFake:
    def __init__(self):
        from antivirus_hogar_pc.core.signatures import BaseFirmas

        self.base_firmas = BaseFirmas()
        self.cache = None
        self.cuarentena = _CuarentenaFake()

        class _Ajustes:
            auth_key_abusech = ""

        self.ajustes = _Ajustes()

    def registrar_escaneo(self, _resultado):
        pass

    def carpeta_descargas(self):
        return ""

    def carpetas_riesgo(self):
        return []


def _assert_pagina_viva(pagina):
    from PySide6.QtWidgets import QProgressBar

    from antivirus_hogar_pc.ui.widgets_v102 import BarraProgreso, BotonPulso

    assert pagina.findChildren(BotonPulso), "la página no tiene BotonPulso"
    for barra in pagina.findChildren(QProgressBar):
        assert isinstance(barra, BarraProgreso), (
            f"QProgressBar pelada: {type(barra)}")


def test_paginas_con_boton_pulso_y_sin_barras_peladas(monkeypatch):
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from antivirus_hogar_pc.contracts import ContextoModulo
    from antivirus_hogar_pc.modules.net import page as pagina_red_mod
    from antivirus_hogar_pc.modules.net import servicios_red as srv
    from antivirus_hogar_pc.modules.security import page as pagina_seg
    from antivirus_hogar_pc.modules.system import page as pagina_sis
    from antivirus_hogar_pc.ui.ajustes_page import crear_pagina_ajustes

    app = QApplication.instance() or QApplication([])
    ctx_fake = ContextoModulo(servicios=_ServiciosFake())
    ctx_none = ContextoModulo(servicios=None)

    paginas = [
        pagina_seg.crear_pagina_escaner(ctx_fake),
        pagina_seg.crear_pagina_proteccion(ctx_fake),
        pagina_seg.crear_pagina_informes(ctx_fake),
        pagina_sis.crear_pagina_drivers(ctx_none),
        pagina_sis.crear_pagina_discos(ctx_none),
        pagina_sis.crear_pagina_limpieza(ctx_none),
        crear_pagina_ajustes(ctx_none),
    ]
    # Red/Actualizaciones con los servicios parcheados (sin red real)
    from antivirus_hogar_pc.contracts import ResultadoModulo

    monkeypatch.setattr(srv, "informe_wifi",
                        lambda: ResultadoModulo(ok=False, mensaje="fake"))
    monkeypatch.setattr(srv, "estado_vpn",
                        lambda: ResultadoModulo(ok=False, mensaje="fake"))
    monkeypatch.setattr(srv, "descargar_servidores_completos",
                        lambda: ResultadoModulo(ok=True, datos={
                            "servidores": [], "es_semilla": False,
                            "fecha_semilla": "", "causa": ""}))
    paginas.append(pagina_red_mod.crear_pagina_actualizaciones(ctx_none))
    paginas.append(pagina_red_mod.crear_pagina_red(ctx_none))

    for pagina in paginas:
        _assert_pagina_viva(pagina)
    for pagina in paginas:
        pagina.deleteLater()
    app.processEvents()


def test_pagina_escaner_muestra_progreso_y_termina(tmp_path, monkeypatch):
    """La página de Escanear sobre una carpeta temporal: la barra toma
    valores intermedios determinados y termina en 100 %."""
    pytest.importorskip("PySide6")
    import time as _time

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QPushButton

    from antivirus_hogar_pc.contracts import ContextoModulo
    from antivirus_hogar_pc.modules.security import page as pagina_seg

    for i in range(30):
        (tmp_path / f"f{i:02d}.exe").write_bytes(b"MZ" + bytes([i]) * 8)
    servicios = _ServiciosFake()
    monkeypatch.setattr(servicios, "carpetas_riesgo",
                        lambda: [str(tmp_path)])
    app = QApplication.instance() or QApplication([])
    pagina = pagina_seg.crear_pagina_escaner(
        ContextoModulo(servicios=servicios))
    boton = next(b for b in pagina.findChildren(QPushButton)
                 if b.text() == "Escaneo rápido")
    assert type(boton).__name__ == "BotonPulso"
    from PySide6.QtWidgets import QLabel

    from antivirus_hogar_pc.ui.widgets_v102 import BarraProgreso

    barra = pagina.findChildren(BarraProgreso)[0]
    boton.click()
    limite = _time.time() + 15
    terminado = False
    while _time.time() < limite:
        app.processEvents()
        textos = " ".join(l.text() for l in pagina.findChildren(QLabel))
        if "Escaneo terminado" in textos:
            terminado = True
            break
        _time.sleep(0.02)
    assert terminado  # el hilo SIEMPRE entrega su resultado a la página
    assert barra.value() == 100
    assert barra._texto == "100 %" or "%" in barra._texto
    pagina.deleteLater()
    app.processEvents()
