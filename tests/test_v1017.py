"""v1.0.17 — El espartano animado de Inicio (orden del usuario).

Lo que se prueba aquí:
- El activo animado va en el paquete, decodifica con sus 240
  cuadros (v1.0.18, nota 8: 640×960 a 24 fps, re-derivado del
  video fuente; en la 1.0.17 eran 120 cuadros de 440×660),
  con transparencia real, y la foto fija de respaldo también.
- La geometría pura: de pie en la zona izquierda de la banda,
  anclado abajo, y JAMÁS sobre el disco del radar (el anillo va
  encima del disco: si no toca el disco, no toca el anillo).
- La puerta de animación (tabla de verdad pura).
- La versión es la 1.0.18 en config, notas y el .iss.
- El radar sigue INTOCABLE: su huella es la de la v1.0.6.
- Qt (con importorskip, como el resto de la suite): QMovie abre
  el WebP con sus 240 cuadros (el plugin qwebp va en el paquete),
  el widget obedece las puertas (interruptor / pausa de ventana /
  batería → foto fija) y la página de Inicio lo lleva colocado
  sin tapar el anillo.
"""
import hashlib
import os

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(RAIZ, "antivirus_hogar_pc", "assets")
RUTA_ANIMADO = os.path.join(ASSETS, "espartano_animado.webp")
RUTA_FIJO = os.path.join(ASSETS, "espartano_radar.png")

# Huella del radar aprobado por el usuario en la v1.0.6: su
# diseño no se toca (regla suya, reafirmada en la 1.0.16).
SHA_RADAR_V106 = (
    "ec21a7b8044b90f6cdb4915aa8ec2affa98d7f74059bb4e742dbfe1109629bea")


# --- Activos (con Qt, como los de la 1.0.15: la CI no instala PIL) -------------

def test_activo_animado_en_el_paquete_y_decodifica(app_qt):
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QImageReader

    assert os.path.isfile(RUTA_ANIMADO)
    assert os.path.getsize(RUTA_ANIMADO) > 100_000
    lector = QImageReader(RUTA_ANIMADO)
    assert lector.size() == QSize(640, 960)
    assert lector.imageCount() == 240
    cuadro = lector.read()
    assert not cuadro.isNull() and cuadro.hasAlphaChannel()
    assert cuadro.pixelColor(2, 2).alpha() == 0      # transparencia real
    centro = cuadro.pixelColor(320, 480)
    assert centro.alpha() > 0                        # y cuerpo presente


def test_activo_fijo_de_respaldo_en_el_paquete(app_qt):
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QImage

    assert os.path.isfile(RUTA_FIJO)
    imagen = QImage(RUTA_FIJO)
    assert not imagen.isNull()
    assert imagen.size() == QSize(1274, 1866)
    assert imagen.hasAlphaChannel()


# --- Geometría pura -------------------------------------------------------------

def _modulo_espartano():
    # El módulo importa QtGui/QtWidgets (es un widget): donde Qt
    # no sea importable, estos tests se saltan como los demás
    # tests Qt de la suite; en la CI corren enteros.
    pytest.importorskip("PySide6.QtGui")
    from antivirus_hogar_pc.ui import espartano_radar

    return espartano_radar


def _geometria(ancho, alto):
    modulo = _modulo_espartano()
    return modulo.geometria_espartano(ancho, alto), (
        modulo.MARGEN_IZQUIERDO, modulo.MARGEN_INFERIOR,
        modulo.MARGEN_ANILLO)


@pytest.mark.parametrize("ancho_banda,alto_banda", [
    (1030, 280),   # la Toughbook: ventana ancha, banda mínima
    (1200, 320),
    (900, 280),
    (760, 280),    # ventana estrecha: debe encoger, no invadir
    (640, 280),
    (1030, 420),   # banda alta
])
def test_geometria_de_pie_a_la_izquierda_y_sin_tapar_el_disco(
        ancho_banda, alto_banda):
    (x, y, ancho, alto), (m_izq, m_inf, m_anillo) = _geometria(
        ancho_banda, alto_banda)
    assert x == m_izq
    assert ancho > 0 and alto > 0
    # De pie: los pies quedan a MARGEN_INFERIOR del borde inferior.
    assert y + alto == alto_banda - m_inf
    # El disco del radar (fondo_radar.py): centrado, radio
    # min(ancho, alto) * 0.46. El espartano queda a su izquierda
    # con MARGEN_ANILLO de respeto (1 px de tolerancia por el
    # redondeo a enteros).
    radio = min(ancho_banda, alto_banda) * 0.46
    borde_disco = ancho_banda / 2 - radio
    assert x + ancho <= borde_disco - m_anillo + 1
    # La proporción del activo se conserva (640×960).
    assert abs(ancho / alto - 640 / 960) < 0.02


def test_geometria_tamanos_degenerados():
    modulo = _modulo_espartano()

    assert modulo.geometria_espartano(0, 280) == (0, 0, 0, 0)
    assert modulo.geometria_espartano(1030, 0) == (0, 0, 0, 0)
    assert modulo.geometria_espartano(-5, -5) == (0, 0, 0, 0)


def test_puerta_de_animacion_tabla():
    modulo = _modulo_espartano()

    assert modulo.debe_animar(True, False) is True
    assert modulo.debe_animar(True, True) is False    # ventana en pausa
    assert modulo.debe_animar(False, False) is False  # interruptor/batería
    assert modulo.debe_animar(False, True) is False


# --- Versión y radar intocable ---------------------------------------------------

def test_version_1017_en_config_notas_e_instalador():
    from antivirus_hogar_pc import config
    from antivirus_hogar_pc.core.notas_version import NOTAS_VERSION

    assert config.VERSION == "1.0.19"
    assert NOTAS_VERSION[0]["version"] == "1.0.19"
    with open(os.path.join(RAIZ, "packaging", "instalador.iss"),
              encoding="utf-8") as f:
        assert '#define AppVersion "1.0.19"' in f.read()


def test_radar_intocable_desde_la_v106():
    ruta = os.path.join(
        RAIZ, "antivirus_hogar_pc", "ui", "fondo_radar.py")
    with open(ruta, "rb") as f:
        # La huella se calcula con los finales de línea en LF:
        # el checkout de Windows los pasa a CRLF y el contenido
        # (que es lo que la regla protege) es el mismo.
        huella = hashlib.sha256(
            f.read().replace(b"\r\n", b"\n")).hexdigest()
    assert huella == SHA_RADAR_V106


def test_ninguna_llamada_a_t_pasa_el_marcador_texto():
    """Guarda de la clase del bug CFA: el primer parámetro de
    i18n.t se llama «texto», así que pasar texto= como marcador
    es un TypeError seguro al ejecutarse. Ninguna llamada del
    paquete puede hacerlo (por AST, sin importar Qt)."""
    import ast

    paquete = os.path.join(RAIZ, "antivirus_hogar_pc")
    ofensores = []
    for base, _dirs, archivos in os.walk(paquete):
        for nombre in archivos:
            if not nombre.endswith(".py"):
                continue
            ruta = os.path.join(base, nombre)
            with open(ruta, encoding="utf-8") as f:
                arbol = ast.parse(f.read())
            for nodo in ast.walk(arbol):
                if not isinstance(nodo, ast.Call):
                    continue
                funcion = nodo.func
                es_t = (isinstance(funcion, ast.Name)
                        and funcion.id == "t") or (
                            isinstance(funcion, ast.Attribute)
                            and funcion.attr == "t")
                if es_t and any(kw.arg == "texto"
                                for kw in nodo.keywords):
                    ofensores.append(f"{ruta}:{nodo.lineno}")
    assert not ofensores, ofensores


# --- Qt (solo con PySide6 importable, patrón de la suite) ------------------------

@pytest.fixture()
def app_qt():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        pytest.skip("QtWidgets no importable en este entorno")

    app = QApplication.instance() or QApplication([])
    yield app


def _destruir(widget, app):
    import gc

    from PySide6.QtCore import QCoreApplication, QEvent

    widget.deleteLater()
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    gc.collect()


def test_qmovie_abre_el_webp_con_sus_240_cuadros(app_qt):
    from PySide6.QtGui import QMovie

    pelicula = QMovie(RUTA_ANIMADO)
    assert pelicula.isValid()          # el plugin qwebp responde
    assert pelicula.frameCount() == 240
    # v1.0.18: el widget decodifica al vuelo (CacheNone), no
    # precarga ~590 MB de cuadros en RAM.
    from antivirus_hogar_pc.ui.espartano_radar import EspartanoRadar
    from PySide6.QtWidgets import QWidget

    banda = QWidget()
    banda.resize(1030, 280)
    espartano = EspartanoRadar(banda)
    assert espartano._pelicula is not None
    assert espartano._pelicula.cacheMode() == QMovie.CacheMode.CacheNone


def test_espartano_obedece_las_puertas(app_qt):
    from PySide6.QtGui import QMovie
    from PySide6.QtWidgets import QWidget

    from antivirus_hogar_pc.ui import animacion
    from antivirus_hogar_pc.ui.espartano_radar import EspartanoRadar

    animacion.fijar_animaciones_activas(True)
    animacion.fijar_ahorro_bateria(False)
    animacion.fijar_pausa(False)
    banda = QWidget()
    banda.resize(1030, 280)
    espartano = EspartanoRadar(banda)
    banda.show()
    app_qt.processEvents()
    try:
        # Puertas abiertas y visible: la película corre.
        espartano._sincronizar()
        assert espartano.movie() is not None
        assert espartano._pelicula.state() == QMovie.MovieState.Running
        # Su rectángulo: de pie a la izquierda, sin llegar al disco.
        geo = espartano.geometry()
        assert geo.x() == 14
        assert geo.y() + geo.height() == 280 - 4
        assert geo.right() < 1030 / 2 - 280 * 0.46 - 16 + 1
        # Interruptor de Ajustes apagado → foto fija.
        animacion.fijar_animaciones_activas(False)
        espartano._sincronizar()
        assert espartano.movie() is None
        assert not espartano.pixmap().isNull()
        # Vuelve el interruptor → vuelve la película.
        animacion.fijar_animaciones_activas(True)
        espartano._sincronizar()
        assert espartano.movie() is not None
        # Pausa de ventana (oculta/minimizada) → foto fija.
        animacion.fijar_pausa(True)
        espartano._sincronizar()
        assert espartano.movie() is None
        assert not espartano.pixmap().isNull()
        # Ahorro por batería → foto fija (va dentro de la puerta).
        animacion.fijar_pausa(False)
        animacion.fijar_ahorro_bateria(True)
        espartano._sincronizar()
        assert espartano.movie() is None
        assert not espartano.pixmap().isNull()
    finally:
        animacion.fijar_ahorro_bateria(False)
        animacion.fijar_pausa(False)
        animacion.fijar_animaciones_activas(True)
        _destruir(banda, app_qt)


def test_pagina_inicio_lleva_el_espartano_sin_tapar_el_anillo(
        app_qt, monkeypatch):
    from PySide6.QtWidgets import QWidget

    from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo
    from antivirus_hogar_pc.modules.panel import page as pagina_panel
    from antivirus_hogar_pc.modules.panel.fake import informe_fake
    from antivirus_hogar_pc.ui.fondo_radar import FondoRadar

    def informe_rapido(servicios=None):
        return ResultadoModulo(
            True, "Estado de prueba", datos=informe_fake())

    monkeypatch.setattr(pagina_panel, "recoger_informe", informe_rapido)
    pagina = pagina_panel.crear_pagina(ContextoModulo(servicios=None))
    pagina.resize(1100, 900)
    pagina.show()
    # El informe fake llega por el hilo: se espera a que
    # aplicar() lo pinte (la fila del disco es la señal).
    from PySide6.QtWidgets import QLabel

    def _textos():
        return [lbl.text() for lbl in pagina.findChildren(QLabel)]

    import time as _time
    limite = _time.time() + 10
    while _time.time() < limite:
        app_qt.processEvents()
        if any("Disco principal" in txt for txt in _textos()):
            break
        _time.sleep(0.05)
    app_qt.processEvents()
    try:
        espartano = pagina.espartano_radar
        banda = pagina.findChild(FondoRadar)
        assert banda is not None
        assert espartano.parent() is banda
        # v1.0.19 (nota 3): el anillo de salud YA NO vive en la
        # banda del radar — el usuario ordenó quitarlo de ahí —;
        # vive en la tarjeta «Estado de la protección» de la
        # misma página. El espartano sigue de pie a la izquierda
        # del barrido, apoyado en el borde inferior de la banda.
        anillos_banda = [w for w in banda.findChildren(QWidget)
                         if w.__class__.__name__ == "AnilloSalud"]
        assert anillos_banda == []
        anillos = [w for w in pagina.findChildren(QWidget)
                   if w.__class__.__name__ == "AnilloSalud"]
        assert len(anillos) == 1
        geo_esp = espartano.geometry()
        assert geo_esp.width() > 0
        assert geo_esp.x() < banda.width() // 2
        assert geo_esp.y() + geo_esp.height() == banda.height() - 4
        # Regresión (bug latente desde la v1, destapado por esta
        # suite): aplicar() debe COMPLETAR con un informe real
        # —incluida la fila del disco, que va tras la de CFA— y
        # los Pendientes deben salir de «Leyendo…».
        textos = _textos()
        assert any("Disco principal" in txt for txt in textos)
        visibles = [lbl for lbl in pagina.findChildren(QLabel)
                    if lbl.isVisible()]
        assert any("Todo al día" in lbl.text()
                   or "Todavía no has hecho ningún escaneo" in lbl.text()
                   or "Último escaneo" in lbl.text()
                   for lbl in visibles)
    finally:
        # El trabajador del informe (ya resuelto con el fake)
        # debe terminar antes de destruir la página.
        from PySide6.QtCore import QThread
        for hilo in pagina.findChildren(QThread):
            hilo.wait(5000)
        _destruir(pagina, app_qt)
