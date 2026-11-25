"""Tests de los REFUERZOS de la v1.0.7 (puntos 4–7 + diagnóstico VPN).

Punto 4: exclusión de Defender del instalador (lógica de
interpretación y verificación) e integridad propia al arranque.
Punto 5: bandeja del sistema (menú, acciones, cierre a la bandeja).
Punto 6: el icono nuevo es transparente de verdad (verificación).
Punto 7 (v1.0.7): auto-actualizador de SoftEther — RETIRADO en la
1.0.10 con el cambio de motor a OpenVPN; sus equivalentes viven en
tests/test_v1010.py. Aquí queda el parser genérico de servicios
(sc query/qc), que el motor nuevo reutiliza.
"""
import json
import os
import struct
import sys
import zlib

import pytest

from antivirus_hogar_pc.winapi import defender, vpn_win

_OK = "The command completed successfully.\n"


# ---------------------------------------------------------------------------
# Punto 4 — Exclusión de Defender
# ---------------------------------------------------------------------------

def test_exclusion_aplicada():
    r = defender.interpretar_resultado_exclusion(
        {"app": True, "datos": True, "ya_estaban": False, "error": ""})
    assert r["estado"] == "aplicada" and r["avisar"] is False


def test_exclusion_ya_estaba():
    r = defender.interpretar_resultado_exclusion(
        {"app": True, "datos": True, "ya_estaban": True, "error": ""})
    assert r["estado"] == "ya_estaba" and r["avisar"] is False


def test_exclusion_bloqueada_por_politica_avisa():
    r = defender.interpretar_resultado_exclusion(
        {"app": False, "datos": False, "ya_estaban": False,
         "error": "Acceso denegado (protección contra alteraciones)"})
    assert r["estado"] == "bloqueada" and r["avisar"] is True
    assert "alteraciones" in r["detalle"]


def test_exclusion_sin_datos_no_finge():
    # Sin resultado del instalador NO se afirma nada: estado
    # «sin_datos» y queda registrado; el aviso al usuario es solo
    # para el bloqueo CONFIRMADO (política/alteraciones).
    for basura in (None, "", "no es json"):
        r = defender.interpretar_resultado_exclusion(basura)
        assert r["estado"] == "sin_datos" and r["avisar"] is False
    r = defender.interpretar_resultado_exclusion({"app": "quiza"})
    assert r["estado"] == "bloqueada" and r["avisar"] is True


def test_script_exclusion_es_declarado_y_verifica():
    ruta = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "packaging", "exclusion_defender.ps1")
    with open(ruta, encoding="utf-8") as f:
        ps1 = f.read()
    assert "Add-MpPreference" in ps1 and "-ExclusionPath" in ps1
    assert "Get-MpPreference" in ps1  # lee de vuelta: verifica
    instalador = os.path.join(os.path.dirname(ruta), "instalador.iss")
    with open(instalador, encoding="utf-8") as f:
        iss = f.read()
    assert "exclusion_defender.ps1" in iss
    assert "AplicarExclusionDefender" in iss
    assert "componentes.json" in iss


def test_rutas_exclusion_solo_las_propias(monkeypatch, tmp_path):
    from antivirus_hogar_pc import config

    monkeypatch.setattr(defender, "carpeta_instalacion",
                        lambda: r"C:\Program Files\Antivirus Hogar PC")
    monkeypatch.setattr(config, "carpeta_datos",
                        lambda: str(tmp_path / "AntivirusHogarPC"))
    rutas = defender.rutas_exclusion()
    assert rutas == (r"C:\Program Files\Antivirus Hogar PC",
                     str(tmp_path / "AntivirusHogarPC"))


def test_integridad_propia_ok_y_con_borrado(tmp_path):
    # El manifiesto del instalador es una LISTA de rutas relativas
    # que deben existir (así lo escribe instalador.iss).
    (tmp_path / "AntivirusHogarPC.exe").write_bytes(b"binario")
    (tmp_path / "icono.ico").write_bytes(b"icono")
    (tmp_path / "componentes.json").write_text(
        json.dumps(["AntivirusHogarPC.exe", "icono.ico"]),
        encoding="utf-8")
    ok = defender.verificar_integridad_propia(str(tmp_path))
    assert ok["ok"] is True and ok["con_manifiesto"] is True
    assert ok["faltan"] == []
    # Defender se lleva el .exe (el falso positivo): se detecta.
    (tmp_path / "AntivirusHogarPC.exe").unlink()
    mal = defender.verificar_integridad_propia(str(tmp_path))
    assert mal["ok"] is False
    assert mal["faltan"] == ["AntivirusHogarPC.exe"]


def test_comprobar_al_arranque_avisa_si_bloqueada(monkeypatch):
    registros = []
    monkeypatch.setattr(
        defender, "leer_resultado_instalador",
        lambda: {"app": False, "datos": False, "ya_estaban": False,
                 "error": "bloqueado"})
    monkeypatch.setattr(defender, "verificar_integridad_propia",
                        lambda: {"ok": True, "faltan": [],
                                 "con_manifiesto": True})
    salida = defender.comprobar_al_arranque(
        lambda tipo, detalle: registros.append((tipo, detalle)))
    assert salida["aviso"] and "Seguridad de Windows" in salida["aviso"]
    assert any("Defender" in d for _t, d in registros)
    # Y si la exclusión quedó aplicada, NO hay aviso.
    monkeypatch.setattr(
        defender, "leer_resultado_instalador",
        lambda: {"app": True, "datos": True, "ya_estaban": True,
                 "error": ""})
    salida2 = defender.comprobar_al_arranque(lambda t, d: None)
    assert salida2["aviso"] is None


# ---------------------------------------------------------------------------
# Punto 5 — Bandeja del sistema
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_bandeja_menu_y_acciones(qt_app):
    from PySide6.QtGui import QIcon

    from antivirus_hogar_pc.ui.bandeja import Bandeja

    llamadas = []
    bandeja = Bandeja(QIcon(), lambda: llamadas.append("abrir"),
                      lambda: llamadas.append("escaneo"),
                      lambda: llamadas.append("salir"))
    textos = [a.text() for a in bandeja.menu.actions() if a.text()]
    assert textos == ["Abrir", "Escaneo rápido", "Salir"]
    bandeja.accion_escaneo.trigger()
    bandeja.accion_abrir.trigger()
    bandeja.accion_salir.trigger()
    assert llamadas == ["escaneo", "abrir", "salir"]
    # Doble clic abre; un clic normal no.
    from PySide6.QtWidgets import QSystemTrayIcon

    bandeja._activado(QSystemTrayIcon.ActivationReason.DoubleClick)
    bandeja._activado(QSystemTrayIcon.ActivationReason.Trigger)
    assert llamadas.count("abrir") == 2
    bandeja.avisar("t", "m")  # no debe romper aunque no haya bandeja real
    bandeja.ocultar()


def test_cerrar_ventana_oculta_a_la_bandeja(qt_app):
    from antivirus_hogar_pc.ui.main_window import VentanaPrincipal
    from antivirus_hogar_pc.ui.services import ServiciosApp

    class _BandejaFalsa:
        def __init__(self):
            self.avisos = []

        def avisar(self, titulo, mensaje):
            self.avisos.append((titulo, mensaje))

    ventana = VentanaPrincipal(ServiciosApp())
    falsa = _BandejaFalsa()
    ventana.fijar_bandeja(falsa)
    ventana.show()
    ventana.close()  # cerrar NO cierra: se oculta a la bandeja
    assert not ventana.isVisible()
    assert len(falsa.avisos) == 1  # avisa una sola vez por sesión
    ventana.show()
    ventana.close()
    assert len(falsa.avisos) == 1
    ventana.salir()  # «Salir» sí cierra de verdad
    assert ventana._saliendo is True


# ---------------------------------------------------------------------------
# Punto 6 — Icono transparente (la verificación ampliada)
# ---------------------------------------------------------------------------

def _cargar_verificador():
    import importlib.util

    ruta = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "scripts", "verificar_icono.py")
    espec = importlib.util.spec_from_file_location("verificar_icono", ruta)
    modulo = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(modulo)
    return modulo


def test_icono_nuevo_es_transparente():
    verificador = _cargar_verificador()
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for ico in (os.path.join(raiz, "packaging", "icono.ico"),
                os.path.join(raiz, "antivirus_hogar_pc", "assets",
                             "icono_app.ico")):
        entradas = verificador._entradas_ico(ico)
        mayor = max(entradas, key=lambda e: e["ancho"])
        assert mayor["ancho"] == 256
        assert verificador._comprobar_transparencia(
            mayor["datos"], "prueba") is True


def _png_rgb_solido(ancho=64, alto=64, rgb=(200, 30, 30)) -> bytes:
    """Un PNG RGB (SIN canal alfa) mínimo, hecho a mano sin PIL."""
    def trozo(tipo: bytes, datos: bytes) -> bytes:
        crc = zlib.crc32(tipo + datos) & 0xFFFFFFFF
        return struct.pack(">I", len(datos)) + tipo + datos \
            + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0)
    fila = b"\x00" + bytes(rgb) * ancho
    idat = zlib.compress(fila * alto)
    return (b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", ihdr)
            + trozo(b"IDAT", idat) + trozo(b"IEND", b""))


def test_verificacion_rechaza_un_png_opaco():
    verificador = _cargar_verificador()
    assert verificador._comprobar_transparencia(
        _png_rgb_solido(), "prueba") is False



# ---------------------------------------------------------------------------
# Diagnóstico: parser genérico de servicios (sc query / sc qc)
# ---------------------------------------------------------------------------

def test_sc_query_y_qc():
    assert vpn_win.interpretar_sc_query(
        "[SC] OpenService FAILED 1060:\nThe specified service does not "
        "exist.") == {"registrado": False, "corriendo": False}
    corriendo = vpn_win.interpretar_sc_query(
        "SERVICE_NAME: OpenVPNServiceInteractive\nSTATE : 4 RUNNING")
    assert corriendo == {"registrado": True, "corriendo": True}
    assert vpn_win.interpretar_sc_qc(
        "START_TYPE : 2 AUTO_START")["inicio"] == "auto"
    assert vpn_win.interpretar_sc_qc(
        "START_TYPE : 3 DEMAND_START")["inicio"] == "manual"
