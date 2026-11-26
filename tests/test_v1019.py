"""v1.0.19 — Las SIETE notas del usuario tras probar la 1.0.18.

- Nota 1: botones del panel izquierdo recortados → la columna
  de navegación va en un área con desplazamiento (ningún botón
  se comprime) y el botón nuevo lleva su etiqueta en dos
  líneas.
- Nota 2: el espartano del radar se veía con baja calidad de
  imagen → activo re-derivado con desmezcla de color (sin halo
  magenta) y q92; la guarda mide el halo en los bordes.
- Nota 3: fuera el anillo de salud del centro del radar → el
  anillo vive en la tarjeta «Estado de la protección» y la
  banda ya no lo contiene. El radar sigue intacto.
- Nota 4: el botón «Puesta a punto» no ejecutaba nada (nunca
  estuvo conectado) → guarda de fuente: el clic está cableado
  y el trabajador se instancia en la página.
- Nota 5 (RAÍZ): «Optimizar con Windows» no confirmaba en la
  Toughbook real: el testigo de eventos se filtraba por un
  proveedor inexistente ('Defrag' en vez de
  'Microsoft-Windows-Defrag') y el evento 258 de éxito estaba
  en el registro mientras la app sentenciaba el fracaso. El
  testigo se filtra en código, el canal Operational solo se
  consulta si existe, el testigo se sondea DURANTE la espera
  y un archivo de resultado vacío no vale como veredicto.
- Nota 6: barrita dedicada de la verificación de servidores
  con el servidor en curso y detección de trabado (decisión
  pura probada aquí).
- Nota 7: «Diagnosticar integridad de la aplicación»: motor
  puro en core/diagnostico.py (corre entero aquí, sin Qt) y
  página con copiar/exportar.
"""
import hashlib
import os
import time

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _leer(ruta_rel: str) -> str:
    with open(os.path.join(RAIZ, ruta_rel), encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# NOTA 5 — el testigo del registro de eventos (evidencia Toughbook)
# ---------------------------------------------------------------------------

def test_nota5_el_filtro_no_usa_el_proveedor_inexistente():
    fuente = _leer("antivirus_hogar_pc/winapi/disks.py")
    # La causa raíz exacta: FilterHashtable con 'Defrag' a secas
    # lanzaba «The parameter is incorrect» SIEMPRE y el testigo
    # jamás hablaba en la Toughbook real. La guarda vigila las
    # líneas de COMANDO (el docstring sí nombra la causa raíz).
    for linea in fuente.splitlines():
        if "-FilterHashtable" in linea:
            assert "ProviderName" not in linea
    assert "Microsoft-Windows-Defrag" in fuente
    # El canal Operational no existe en esa máquina: solo se
    # consulta si Get-WinEvent -ListLog dice que está.
    assert "Get-WinEvent -ListLog" in fuente


def test_nota5_evento_real_258_de_la_toughbook_cierra_exito():
    from antivirus_hogar_pc.winapi.disks import (
        interpretar_eventos_optimizacion)
    # La forma EXACTA del evento que la Toughbook guardó el
    # 26/11/2026 09:43:44 (leído por SSH de su registro):
    # proveedor Microsoft-Windows-Defrag, Id 258, mensaje EN.
    ahora = time.time()
    eventos = [{
        "Id": 258, "TimeCreated": ahora - 5,
        "Message": "The storage optimizer successfully "
                   "completed retrim on (C:)"}]
    veredicto = interpretar_eventos_optimizacion(eventos, "C")
    assert veredicto is not None and veredicto["ok"] is True


def test_nota5_evento_de_fallo_es_error_y_sin_eventos_no_hay_veredicto():
    from antivirus_hogar_pc.winapi.disks import (
        interpretar_eventos_optimizacion)
    ahora = time.time()
    eventos = [{
        "Id": 261, "TimeCreated": ahora - 5,
        "Message": "The storage optimizer was unable to "
                   "complete retrim on (C:) because of a "
                   "hardware error."}]
    veredicto = interpretar_eventos_optimizacion(eventos, "C")
    assert veredicto is not None and veredicto["ok"] is False
    assert interpretar_eventos_optimizacion([], "C") is None


def test_nota5_el_testigo_se_sondea_durante_la_espera():
    fuente = _leer("antivirus_hogar_pc/winapi/disks.py")
    inicio = fuente.index("def optimizar_volumen")
    cuerpo = fuente[inicio:]
    # El sondeo del testigo vive DENTRO del bucle de espera de
    # optimizar_volumen (no solo tras el fracaso, como antes).
    assert "consultar_eventos_optimizacion" in cuerpo
    # Y el resultado del ayudante solo vale CON CONTENIDO: un
    # archivo vacío ya no cierra la espera como «sin veredicto».
    assert "_leer_texto_tolerante(ruta_resultado).strip()" in cuerpo


# ---------------------------------------------------------------------------
# NOTA 4 — el botón «Puesta a punto» conectado de verdad
# ---------------------------------------------------------------------------

def test_nota4_boton_puesta_a_punto_cableado():
    fuente = _leer("antivirus_hogar_pc/modules/panel/page.py")
    assert "boton_puesta.clicked.connect(" in fuente
    assert "boton_cancelar_puesta.clicked.connect(" in fuente
    # El trabajador se instancia en la página (antes: jamás).
    assert "trabajador = _TrabajadorPuestaAPunto(" in fuente


# ---------------------------------------------------------------------------
# NOTA 1 — panel sin recortes + NOTA 7 — botón y página de diagnóstico
# ---------------------------------------------------------------------------

def test_nota1_columna_de_navegacion_con_desplazamiento():
    fuente = _leer("antivirus_hogar_pc/ui/main_window.py")
    assert "QScrollArea" in fuente
    assert "lay_nav.addWidget(boton)" in fuente
    assert "lay_barra.addWidget(area_nav, 1)" in fuente


def test_nota7_boton_y_pagina_de_diagnostico():
    fuente = _leer("antivirus_hogar_pc/ui/main_window.py")
    assert 'self.ir_a("diagnostico")' in fuente
    assert '"diagnostico"' in fuente
    assert "crear_pagina_diagnostico" in fuente
    pagina = _leer("antivirus_hogar_pc/ui/diagnostico_page.py")
    assert "diagnostico.diagnosticar()" in pagina
    assert "clipboard().setText" in pagina      # copiar
    assert "getSaveFileName" in pagina          # exportar


def test_nota7_el_motor_diagnostica_sin_caerse():
    from antivirus_hogar_pc.core import diagnostico

    resultados = diagnostico.diagnosticar()
    assert len(resultados) >= 10
    for r in resultados:
        assert r["estado"] in ("ok", "aviso", "error")
        assert r["nombre"] and r["detalle"]
    informe = diagnostico.construir_informe(resultados)
    assert "Diagnóstico de integridad" in informe
    assert "Resumen:" in informe


def test_nota7_una_comprobacion_rota_sale_como_error(monkeypatch):
    from antivirus_hogar_pc.core import diagnostico

    def rota():
        raise RuntimeError("falla sembrada")

    monkeypatch.setattr(
        diagnostico, "COMPROBACIONES",
        [rota, diagnostico._chk_version])
    resultados = diagnostico.diagnosticar()
    assert resultados[0]["estado"] == "error"
    assert "falla sembrada" in resultados[0]["detalle"]
    assert resultados[1]["estado"] == "ok"


# ---------------------------------------------------------------------------
# NOTA 3 — el anillo fuera del radar (y el radar intacto)
# ---------------------------------------------------------------------------

def test_nota3_la_banda_ya_no_contiene_el_anillo():
    fuente = _leer("antivirus_hogar_pc/modules/panel/page.py")
    assert "QGridLayout(banda_radar)" not in fuente
    assert "lay_banda" not in fuente
    # El anillo vive en la tarjeta de estado, con su cifra.
    assert "columna_anillo.addWidget(" in fuente


def test_nota3_radar_intocable_sigue_intacto():
    ruta = os.path.join(
        RAIZ, "antivirus_hogar_pc", "ui", "fondo_radar.py")
    with open(ruta, "rb") as f:
        huella = hashlib.sha256(
            f.read().replace(b"\r\n", b"\n")).hexdigest()
    assert huella == (
        "ec21a7b8044b90f6cdb4915aa8ec2affa98d7f74059bb4e742dbfe110"
        "9629bea")


# ---------------------------------------------------------------------------
# NOTA 2 — el activo nuevo: sin halo magenta y con sus 240 cuadros
# ---------------------------------------------------------------------------

def _fraccion_halo_magenta(qimage) -> float:
    """Fracción de píxeles semitransparentes (el borde de la
    silueta) cuyo color RGB aún tira a magenta: el defecto que
    el usuario veía como «baja calidad». QImage en formato
    RGBA8888, sin dependencias fuera de Qt."""
    imagen = qimage.convertToFormat(
        qimage.Format.Format_RGBA8888)
    ancho, alto = imagen.width(), imagen.height()
    datos = imagen.constBits()
    paso = imagen.bytesPerLine()
    borde = teñidos = 0
    for y in range(alto):
        fila = y * paso
        for x in range(ancho):
            i = fila + x * 4
            a = datos[i + 3]
            if 10 < a < 250:
                borde += 1
                if min(datos[i], datos[i + 2]) - datos[i + 1] > 40:
                    teñidos += 1
    return teñidos / borde if borde else 0.0


def test_nota2_activo_sin_halo_y_completo():
    pytest.importorskip("PySide6.QtGui")
    from PySide6.QtGui import QImageReader

    ruta = os.path.join(
        RAIZ, "antivirus_hogar_pc", "assets",
        "espartano_animado.webp")
    lector = QImageReader(ruta)
    assert lector.size().width() == 640
    assert lector.size().height() == 960
    assert lector.imageCount() == 240
    halo_nuevo = _fraccion_halo_magenta(lector.read())
    # Medido al derivar (cuadro 0): el activo de la 1.0.18
    # (chromakey sin desmezcla) deja el 1,41 % de los píxeles
    # de borde teñidos de magenta; el nuevo, con la desmezcla,
    # mide 0,01 %. La guarda deja margen ×20 y el activo
    # viejo NO la pasaría.
    assert halo_nuevo < 0.002


# ---------------------------------------------------------------------------
# NOTA 6 — barrita de verificación y detección de trabado
# ---------------------------------------------------------------------------

def test_nota6_decision_de_trabado():
    from antivirus_hogar_pc.modules.net.servicios_red import (
        UMBRAL_TRABADA_S, verificacion_trabada)

    ahora = 10_000.0
    # Avanzando: no trabada.
    assert not verificacion_trabada(True, ahora - 5, ahora, 3, 40)
    # Silencio largo con trabajo pendiente: trabada.
    assert verificacion_trabada(
        True, ahora - UMBRAL_TRABADA_S - 1, ahora, 3, 40)
    # Barrido terminado o inactivo: nunca «trabada».
    assert not verificacion_trabada(
        True, ahora - 9999, ahora, 40, 40)
    assert not verificacion_trabada(
        False, ahora - 9999, ahora, 3, 40)


def test_nota6_barra_dedicada_y_vigia_en_la_pagina():
    fuente = _leer("antivirus_hogar_pc/modules/net/page.py")
    assert "self._barra_verificacion = BarraProgreso()" in fuente
    assert "_vigilar_verificacion" in fuente
    assert "ahora: {host}" in fuente


# ---------------------------------------------------------------------------
# Versión 1.0.19
# ---------------------------------------------------------------------------

def test_version_1019_en_config_notas_e_instalador():
    from antivirus_hogar_pc import config
    from antivirus_hogar_pc.core.notas_version import NOTAS_VERSION

    assert config.VERSION == "1.0.19"
    assert NOTAS_VERSION[0]["version"] == "1.0.19"
    assert len(NOTAS_VERSION[0]["novedades"]) >= 7
    with open(os.path.join(RAIZ, "packaging", "instalador.iss"),
              encoding="utf-8") as f:
        assert '#define AppVersion "1.0.19"' in f.read()
