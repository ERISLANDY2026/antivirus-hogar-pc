"""Tests de los REFUERZOS de la v1.0.7 (puntos 4–7 + diagnóstico VPN).

Punto 4: exclusión de Defender del instalador (lógica de
interpretación y verificación) e integridad propia al arranque.
Punto 5: bandeja del sistema (menú, acciones, cierre a la bandeja).
Punto 6: el icono nuevo es transparente de verdad (verificación).
Punto 7: auto-actualizador de SoftEther (cadencia, cadena de
fuentes, comparación de versiones, diferido con túnel, extractor
PE) y re-sincronización tras actualizar.
Diagnóstico VPN: vpncmd localizado/ausente, errores típicos con su
mensaje en español y la mini-diagnóstico de integración.
"""
import json
import os
import struct
import sys
import zlib

import pytest

from antivirus_hogar_pc.winapi import defender, softether_update, vpn_win

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
# Punto 7 — Versiones, fuentes y cadencia
# ---------------------------------------------------------------------------

def test_versiones_desde_las_fuentes():
    assert softether_update.version_desde_tag("v4.44-9807-rtm") == (4, 44, 9807)
    assert softether_update.version_desde_tag("v4.44-9807-beta") is None
    historia = ("SoftEther VPN 4.44 Build 9807 RTM (April 16, 2025)\n"
                "SoftEther VPN 4.43 Build 9799 Beta (March 12, 2025)\n")
    assert softether_update.version_desde_historia(historia) == (4, 44, 9807)
    listado = ('<a href="v4.44-9807-rtm-2025.04.16-tree/">x</a>'
               '<a href="v4.43-9799-beta-2025.03.12-tree/">y</a>')
    assert softether_update.version_desde_listado(listado) == (4, 44, 9807)
    assert softether_update.carpetas_desde_listado(listado) == {
        (4, 44, 9807): "v4.44-9807-rtm-2025.04.16-tree"}
    assert softether_update.comparar_versiones((4, 45, 1), (4, 44, 9807)) == 1
    assert softether_update.comparar_versiones((4, 44, 9807), (4, 44, 9807)) == 0
    assert softether_update.comparar_versiones((4, 43, 1), (4, 44, 9807)) == -1


def test_cadencia_de_tres_dias():
    ahora = 1_000_000.0
    assert softether_update.toca_chequear(ahora, {}) is True
    assert softether_update.toca_chequear(
        ahora, {"ultimo_chequeo": ahora - 2 * 86400}) is False
    assert softether_update.toca_chequear(
        ahora, {"ultimo_chequeo": ahora - 3 * 86400 - 1}) is True


def test_cadena_de_fuentes_pasa_a_la_siguiente():
    def descargar(url):
        if "softether.org" in url:
            return "SoftEther VPN 4.45 Build 9900 RTM (June 1, 2026)"
        raise OSError("fuente caida")

    salida = softether_update.consultar_fuentes(descargar)
    assert salida["version"] == (4, 45, 9900)
    assert "softether.org" in salida["fuente"]
    # GitHub cayó y el listado también (se consulta al final por la
    # carpeta): la cadena siguió y la historia oficial respondió.
    assert len(salida["fallos"]) == 2


def test_cadena_de_fuentes_todas_caidas():
    def descargar(_url):
        raise OSError("sin red")

    salida = softether_update.consultar_fuentes(descargar)
    assert salida["version"] is None
    assert len(salida["fallos"]) == len(softether_update.FUENTES)


def test_datos_descarga_desde_el_listado():
    listado = ("2026/06/01     4:56     60111222 "
               "softether-vpnclient-v4.45-9900-rtm-2026.06.01-"
               "windows-x86_x64-intel.exe")
    datos = softether_update.datos_descarga("v4.45-9900-rtm-2026.06.01-tree",
                                            lambda _u: listado)
    assert datos["tamano"] == 60111222
    assert datos["url"].endswith(datos["nombre"])
    assert "v4.45-9900-rtm-2026.06.01-tree" in datos["url"]


# ---------------------------------------------------------------------------
# Punto 7 — Extractor PE (instalador sintético con recursos DATAFILE)
# ---------------------------------------------------------------------------

def _pe_minimo_x64() -> bytes:
    """Un PE x64 mínimo pero válido para la validación estructural."""
    datos = bytearray(368)
    datos[0:2] = b"MZ"
    struct.pack_into("<I", datos, 0x3C, 64)
    datos[64:68] = b"PE\0\0"
    struct.pack_into("<H", datos, 64 + 4, 0x8664)  # Machine x64
    return bytes(datos)


def _instalador_sintetico(recursos: dict[str, bytes]) -> bytes:
    """Construye un PE con un árbol de recursos DATAFILE de verdad."""
    nombres = list(recursos)

    def cadena(texto: str) -> bytes:
        return struct.pack("<H", len(texto)) + texto.encode("utf-16-le")

    # Distribución: raíz, cadena DATAFILE, dir nombres, cadenas de
    # nombre, dirs idioma, entradas de datos, blobs.
    tam_raiz = 16 + 8
    off_cadena_tipo = tam_raiz
    off_dir_nombres = off_cadena_tipo + len(cadena("DATAFILE"))
    tam_dir_nombres = 16 + 8 * len(nombres)
    off = off_dir_nombres + tam_dir_nombres
    off_cadenas_nombre = {}
    for n in nombres:
        off_cadenas_nombre[n] = off
        off += len(cadena(n))
    off_dirs_idioma = {}
    for n in nombres:
        off_dirs_idioma[n] = off
        off += 16 + 8
    off_entradas = {}
    for n in nombres:
        off_entradas[n] = off
        off += 16
    off_blobs = {}
    for n in nombres:
        off_blobs[n] = off
        off += len(recursos[n])
    total = off

    rsrc = bytearray(total)
    # Raíz: 1 entrada con nombre (DATAFILE) → subdirectorio.
    struct.pack_into("<HH", rsrc, 12, 1, 0)
    struct.pack_into("<II", rsrc, 16, 0x80000000 | off_cadena_tipo,
                     0x80000000 | off_dir_nombres)
    rsrc[off_cadena_tipo:off_cadena_tipo + len(cadena("DATAFILE"))] = \
        cadena("DATAFILE")
    struct.pack_into("<HH", rsrc, off_dir_nombres + 12, len(nombres), 0)
    for i, n in enumerate(nombres):
        struct.pack_into("<II", rsrc, off_dir_nombres + 16 + i * 8,
                         0x80000000 | off_cadenas_nombre[n],
                         0x80000000 | off_dirs_idioma[n])
        rsrc[off_cadenas_nombre[n]:
             off_cadenas_nombre[n] + len(cadena(n))] = cadena(n)
        struct.pack_into("<HH", rsrc, off_dirs_idioma[n] + 12, 0, 1)
        struct.pack_into("<II", rsrc, off_dirs_idioma[n] + 16,
                         0, off_entradas[n])
        struct.pack_into("<II", rsrc, off_entradas[n],
                         0x1000 + off_blobs[n], len(recursos[n]))
        rsrc[off_blobs[n]:off_blobs[n] + len(recursos[n])] = recursos[n]

    cabecera = bytearray(368)
    cabecera[0:2] = b"MZ"
    struct.pack_into("<I", cabecera, 0x3C, 64)
    cabecera[64:68] = b"PE\0\0"
    struct.pack_into("<H", cabecera, 64 + 4, 0x8664)
    struct.pack_into("<H", cabecera, 64 + 6, 1)      # 1 sección
    struct.pack_into("<H", cabecera, 64 + 20, 240)   # cabecera opcional
    opt = 64 + 24
    struct.pack_into("<H", cabecera, opt, 0x20B)     # PE32+
    struct.pack_into("<II", cabecera, opt + 96 + 16, 0x1000, len(rsrc))
    sec = opt + 240
    cabecera[sec:sec + 6] = b".rsrc\0\0"[:6]
    struct.pack_into("<IIII", cabecera, sec + 8, len(rsrc), 0x1000,
                     len(rsrc), 368)
    return bytes(cabecera) + bytes(rsrc)


def _recurso_comprimido(datos: bytes) -> bytes:
    return struct.pack("<I", len(datos)) + zlib.compress(datos)


def test_extractor_datafile_y_preparar_cliente(tmp_path):
    pe = _pe_minimo_x64()
    instalador = _instalador_sintetico({
        "VPNCLIENT_X64.EXE": _recurso_comprimido(pe),
        "VPNCMD_X64.EXE": _recurso_comprimido(pe),
        "VPNCMGR_X64.EXE": _recurso_comprimido(pe),
        "RAW_HAMCORE.SE2": b"HamCore" + b"\0" * 32,
    })
    crudos = softether_update.extraer_datafile(instalador)
    assert set(crudos) == {"VPNCLIENT_X64.EXE", "VPNCMD_X64.EXE",
                           "VPNCMGR_X64.EXE", "RAW_HAMCORE.SE2"}
    escritos = softether_update.preparar_cliente(
        instalador, str(tmp_path / "cliente"))
    assert escritos["vpncmd_x64.exe"] == len(pe)
    assert escritos["hamcore.se2"] == 39
    with pytest.raises(ValueError):
        softether_update.extraer_datafile(b"no es un PE")


# ---------------------------------------------------------------------------
# Punto 7 — Diferido con túnel activo y re-sincronización
# ---------------------------------------------------------------------------

class _VpncmdResync:
    """vpncmd falso para la re-sincronización (perfil presente o no)."""

    def __init__(self, con_cuenta=True):
        self.con_cuenta = con_cuenta
        self.comandos = []

    def __call__(self, argumentos, timeout=60):
        comando = argumentos[0]
        self.comandos.append(comando)
        if comando == "NicList":
            return 0, "Virtual Network Adapter Name|Status\nVPN|Enabled\n" + _OK
        if comando == "AccountList":
            filas = "VPN Connection Setting Name|Status\n---\n"
            if self.con_cuenta:
                filas += "AntivirusHogarVPN|Disconnected\n"
            return 0, filas + _OK
        if comando in ("AccountCreate", "AccountPasswordSet", "NicCreate"):
            if comando == "AccountCreate":
                self.con_cuenta = True
            return 0, _OK
        if comando == "AccountStatusGet":
            return 0, "Session Status|Not Connected\n" + _OK
        raise AssertionError(f"comando inesperado: {argumentos}")


def _preparar_resync(monkeypatch, tmp_path, falso, servicio_registrado=True,
                     ruta=r"C:\nueva\ruta\vpncmd_x64.exe"):
    from antivirus_hogar_pc import config

    monkeypatch.setattr(config, "carpeta_datos", lambda: str(tmp_path))
    monkeypatch.setattr(vpn_win, "ruta_vpncmd", lambda: ruta)
    monkeypatch.setattr(vpn_win, "_ejecutar_vpncmd", falso)
    monkeypatch.setattr(
        vpn_win, "estado_servicio_softether",
        lambda: {"registrado": servicio_registrado, "corriendo": True,
                 "inicio": "auto"})


def test_resincronizacion_perfil_intacto(tmp_path, monkeypatch):
    falso = _VpncmdResync(con_cuenta=True)
    _preparar_resync(monkeypatch, tmp_path, falso)
    salida = softether_update.resincronizar(lambda t, d: None)
    assert salida["ok"] is True
    assert "AccountCreate" not in falso.comandos


def test_resincronizacion_recrea_el_perfil_borrado(tmp_path, monkeypatch):
    falso = _VpncmdResync(con_cuenta=False)
    _preparar_resync(monkeypatch, tmp_path, falso)
    (tmp_path / "vpn_estado.json").write_text(
        json.dumps({"hostname": "vpn123.opengw.net"}), encoding="utf-8")
    salida = softether_update.resincronizar(lambda t, d: None)
    assert salida["ok"] is True
    assert "AccountCreate" in falso.comandos  # se recreó sola


def test_resincronizacion_servicio_sin_registrar_se_reporta(
        tmp_path, monkeypatch):
    falso = _VpncmdResync()
    _preparar_resync(monkeypatch, tmp_path, falso,
                     servicio_registrado=False)
    salida = softether_update.resincronizar(lambda t, d: None)
    assert salida["ok"] is False
    assert "no quedó registrado" in salida["detalle"]  # no se finge


def test_resincronizacion_vpncmd_ausente(tmp_path, monkeypatch):
    _preparar_resync(monkeypatch, tmp_path, _VpncmdResync(), ruta="")
    salida = softether_update.resincronizar(lambda t, d: None)
    assert salida["ok"] is False
    assert "no se localiza" in salida["detalle"]


def test_aplicacion_diferida_con_tunel_activo(tmp_path, monkeypatch):
    from antivirus_hogar_pc import config

    monkeypatch.setattr(config, "carpeta_datos", lambda: str(tmp_path))
    (tmp_path / "softether_update.json").write_text(json.dumps(
        {"pendiente": {"version": [4, 45, 9900], "desde": "4.44",
                       "staging": str(tmp_path)}}), encoding="utf-8")
    monkeypatch.setattr(vpn_win, "estado_softether",
                        lambda: {"conectado": True})

    def _prohibido(*_a, **_k):
        raise AssertionError("con túnel activo no se debe elevar ni tocar")

    monkeypatch.setattr(softether_update, "ejecutar_elevado", _prohibido)
    salida = softether_update.aplicar_pendiente(lambda t, d: None)
    assert salida["aplicada"] is False and salida.get("diferida") is True


# ---------------------------------------------------------------------------
# Diagnóstico VPN (refuerzo 3)
# ---------------------------------------------------------------------------

def test_sc_query_y_qc():
    assert vpn_win.interpretar_sc_query(
        "[SC] OpenService FAILED 1060:\nThe specified service does not "
        "exist.") == {"registrado": False, "corriendo": False}
    corriendo = vpn_win.interpretar_sc_query(
        "SERVICE_NAME: SEVPNCLIENT\nSTATE : 4 RUNNING")
    assert corriendo == {"registrado": True, "corriendo": True}
    assert vpn_win.interpretar_sc_qc(
        "START_TYPE : 2 AUTO_START")["inicio"] == "auto"
    assert vpn_win.interpretar_sc_qc(
        "START_TYPE : 3 DEMAND_START")["inicio"] == "manual"


def test_diagnostico_con_ruta_simulada_y_ausente(monkeypatch):
    falso = _VpncmdResync(con_cuenta=True)
    monkeypatch.setattr(vpn_win, "_ejecutar_vpncmd", falso)
    monkeypatch.setattr(vpn_win, "ruta_vpncmd",
                        lambda: r"C:\simulada\vpncmd.exe")
    monkeypatch.setattr(
        vpn_win, "estado_servicio_softether",
        lambda: {"registrado": True, "corriendo": True, "inicio": "auto"})
    diag = vpn_win.diagnostico_softether()
    assert diag["instalado"] is True and diag["nic"] is True
    assert "AntivirusHogarVPN" in diag["cuentas"]
    monkeypatch.setattr(vpn_win, "ruta_vpncmd", lambda: "")
    diag2 = vpn_win.diagnostico_softether()
    assert diag2["instalado"] is False and diag2["ruta_vpncmd"] == ""


class _VpncmdErrores:
    def __init__(self, escenario):
        self.escenario = escenario
        self.nic = True
        self.cuenta = True

    def __call__(self, argumentos, timeout=60):
        comando = argumentos[0]
        if self.escenario == "servicio_caido" and comando == "NicList":
            return 1, ("Error Code: 1\nConnection to the server "
                       "failed.\n")
        if comando == "NicList":
            return 0, "VPN|Enabled\n" + _OK
        if comando == "AccountList":
            return 0, "AntivirusHogarVPN|Disconnected\n" + _OK
        if comando == "AccountConnect":
            if self.escenario == "auth":
                return 2, ("Error: user authentication failed. "
                           "Password incorrect.\n")
            return 2, "Error Code: 2\nConnection to the server failed.\n"
        if comando in ("NicCreate", "AccountCreate", "AccountPasswordSet",
                       "AccountDelete", "AccountDisconnect"):
            return 0, _OK
        if comando == "AccountStatusGet":
            return 0, "Session Status|Not Connected\n" + _OK
        raise AssertionError(comando)


def test_errores_tipicos_de_vpncmd_en_espanol(monkeypatch):
    monkeypatch.setattr(vpn_win, "ruta_vpncmd", lambda: r"C:\x\vpncmd.exe")
    hostname = "vpn123.opengw.net"  # conectar_softether recibe el host

    monkeypatch.setattr(vpn_win, "_ejecutar_vpncmd",
                        _VpncmdErrores("servicio_caido"))
    r1 = vpn_win.conectar_softether(hostname)
    assert r1["ok"] is False and "servicio de SoftEther no responde" \
        in r1["mensaje"]

    monkeypatch.setattr(vpn_win, "_ejecutar_vpncmd", _VpncmdErrores("auth"))
    r2 = vpn_win.conectar_softether(hostname)
    assert r2["ok"] is False and "autenticación" in r2["mensaje"]

    monkeypatch.setattr(vpn_win, "_ejecutar_vpncmd",
                        _VpncmdErrores("sin_respuesta"))
    r3 = vpn_win.conectar_softether(hostname)
    assert r3["ok"] is False and "no respondió" in r3["mensaje"]


def test_cada_servidor_lleva_lo_que_vpncmd_necesita():
    from antivirus_hogar_pc import config
    from antivirus_hogar_pc.core import vpngate

    assert vpn_win.PUERTO_VPNGATE == 443
    assert vpn_win.HUB_VPNGATE == "VPNGATE"
    assert vpn_win.USUARIO_VPNGATE == "vpn"
    servidores, _fuente = vpngate.leer_semilla_vpngate(
        config.carpeta_activos())
    assert servidores, "la semilla de VPN Gate debe poblar la lista"
    for s in servidores:
        assert s.hostname  # sin host, vpncmd no puede crear la cuenta
