"""Espartano animado de Inicio (v1.0.17, orden directa del usuario).

El espartano que el usuario eligió y aprobó tras verlo animado en
la página de elección («Esa es hermano, intégrala a la app»,
2026-11-26): cuerpo entero, escudo tipo shield con «GUERRA» fijo
en todos los cuadros, electricidad LENTA y ciclo natural de
guardia (alerta → vigilancia → en guardia → respiración), en un
WebP animado con transparencia en bucle.

v1.0.18 (nota 8): el activo se re-derivó de su video fuente
(768×1152, 24 fps) porque a 440×660 y 12 fps se veía «un poco
difuso, un poco ruidoso» en la Toughbook — la app lo escalaba
hacia arriba en la banda. Ahora: 640×960, 24 fps completos,
calidad 85 y llave de magenta afinada (chromakey 0.25/0.18 sin
despill: borde más limpio, sin comerse la cresta roja). Coste
medido de decodificación (libwebp, esta máquina): 16,3 ms por
cuadro frente a un presupuesto de 41,7 ms a 24 fps — fluido
junto al radar. Y la caché de QMovie pasa a CacheNone: con
CacheAll, 240 cuadros de 640×960 ocuparían ~590 MB de RAM; sin
caché se decodifica al vuelo, que es lo que el coste medido
permite.

COLOCACIÓN (palabras del usuario): su fondo es «la parte
izquierda del área de barrido del radar» — va DENTRO de la banda
del radar de Inicio, en su zona izquierda, de pie sobre ese
fondo. El radar (`ui/fondo_radar.py`) queda INTOCABLE en diseño
y comportamiento, y el espartano NUNCA tapa el anillo de salud:
`geometria_espartano` calcula su rectángulo con el borde del
disco del radar como límite duro.

REPRODUCCIÓN: QMovie en bucle (el plugin WebP de Qt va en el
paquete; verificado en el entorno y en el build congelado). Las
pausas son las puertas de siempre de `ui.animacion`, sondeadas
cada 250 ms como hace el propio radar con su temporizador:
- ventana oculta o minimizada (pausa global de la ventana),
- interruptor de animaciones de Ajustes apagado,
- ahorro por batería (v1.0.16, frente 6; va dentro de
  `animaciones_activas()`).
Al pausar o apagar se enseña su FOTO FIJA
(`assets/espartano_radar.png`, el mismo espartano quieto). Si el
animado faltara o no decodificara, se enseña la foto y la página
nunca se rompe por su culpa.
"""
import os

from PySide6.QtCore import QEvent, QSize, QTimer, Qt
from PySide6.QtGui import QImageReader, QMovie, QPixmap
from PySide6.QtWidgets import QLabel

# Aspecto (ancho/alto) del activo entregado: 640×960 (v1.0.18).
# Si el archivo real dice otra cosa, manda el archivo (se lee
# con QImageReader al construir el widget).
ASPECTO_DEFECTO = 640 / 960

MARGEN_IZQUIERDO = 14    # px desde el borde izquierdo de la banda
MARGEN_INFERIOR = 4      # px de aire bajo sus pies
MARGEN_ANILLO = 16       # px de respeto ante el borde del disco
FRACCION_ALTO = 0.94     # alto del espartano / alto de la banda
SONDEO_MS = 250          # sondeo de las puertas de animación


def _ruta_assets(nombre: str) -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", nombre)


def ruta_animado() -> str:
    return _ruta_assets("espartano_animado.webp")


def ruta_fijo() -> str:
    return _ruta_assets("espartano_radar.png")


def geometria_espartano(ancho_banda: float, alto_banda: float,
                        aspecto: float = ASPECTO_DEFECTO
                        ) -> tuple[int, int, int, int]:
    """(x, y, ancho, alto) del espartano dentro de la banda.

    De pie en la zona izquierda: pies a MARGEN_INFERIOR del borde
    inferior y alto FRACCION_ALTO de la banda, salvo que el ancho
    resultante invada el disco del radar (centrado, de radio
    min(ancho, alto) * 0.46, como lo dibuja fondo_radar.py): en
    ese caso se encoge hasta dejar MARGEN_ANILLO de respeto. Así
    el espartano jamás tapa el disco ni el anillo que va encima.
    Función pura, sin Qt: la ejerce la suite sin interfaz.
    """
    if ancho_banda <= 0 or alto_banda <= 0 or aspecto <= 0:
        return (0, 0, 0, 0)
    alto = FRACCION_ALTO * alto_banda
    ancho = alto * aspecto
    radio_disco = min(ancho_banda, alto_banda) * 0.46
    limite_derecho = ancho_banda / 2.0 - radio_disco - MARGEN_ANILLO
    if MARGEN_IZQUIERDO + ancho > limite_derecho:
        ancho = max(0.0, limite_derecho - MARGEN_IZQUIERDO)
        alto = ancho / aspecto
    x = MARGEN_IZQUIERDO
    y = alto_banda - MARGEN_INFERIOR - alto
    return (int(round(x)), int(round(y)),
            int(round(ancho)), int(round(alto)))


def debe_animar(activas: bool, en_pausa: bool) -> bool:
    """La puerta del espartano: animaciones activas (interruptor
    de Ajustes y ahorro por batería, que ya va dentro de
    `animaciones_activas()`) y ventana sin pausar. Pura."""
    return bool(activas) and not en_pausa


class EspartanoRadar(QLabel):
    """El espartano de pie en la zona izquierda de la banda del
    radar: hijo de la propia banda, se coloca solo ante sus
    cambios de tamaño y sondea las puertas de animación."""

    def __init__(self, banda) -> None:
        super().__init__(banda)
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("background: transparent;")
        self._banda = banda
        self._fijo = QPixmap(ruta_fijo())
        self._pelicula: QMovie | None = None
        self._aspecto = ASPECTO_DEFECTO
        ruta = ruta_animado()
        if os.path.isfile(ruta):
            lector = QImageReader(ruta)
            tam = lector.size()
            if tam.isValid() and tam.height() > 0:
                self._aspecto = tam.width() / tam.height()
            pelicula = QMovie(ruta)
            if pelicula.isValid():
                # v1.0.18: CacheNone — decodificación al vuelo.
                # Con CacheAll, los 240 cuadros de 640×960
                # ocuparían ~590 MB de RAM en caché; el coste
                # medido por cuadro (16,3 ms) deja margen de
                # sobra a 24 fps sin caché.
                pelicula.setCacheMode(QMovie.CacheMode.CacheNone)
                self._pelicula = pelicula
        self._temporizador = QTimer(self)
        self._temporizador.setInterval(SONDEO_MS)
        self._temporizador.timeout.connect(self._sincronizar)
        banda.installEventFilter(self)
        self._reposicionar()
        self._sincronizar()

    # -- geometría ------------------------------------------------------------
    def eventFilter(self, objeto, evento) -> bool:  # noqa: N802 (Qt)
        if objeto is self._banda and evento.type() == QEvent.Type.Resize:
            self._reposicionar()
        return super().eventFilter(objeto, evento)

    def _reposicionar(self) -> None:
        x, y, ancho, alto = geometria_espartano(
            self._banda.width(), self._banda.height(), self._aspecto)
        if ancho <= 0 or alto <= 0:
            return
        self.setGeometry(x, y, ancho, alto)
        if self._pelicula is not None:
            self._pelicula.setScaledSize(QSize(ancho, alto))
        if self.movie() is None:
            self._repintar_fijo()

    def _repintar_fijo(self) -> None:
        if not self._fijo.isNull() and self.width() > 0:
            self.setPixmap(self._fijo.scaled(
                self.width(), self.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

    # -- reproducción -----------------------------------------------------------
    def _sincronizar(self) -> None:
        from .animacion import animaciones_activas, en_pausa

        quiero = self.isVisible() and debe_animar(
            animaciones_activas(), en_pausa())
        if quiero and self._pelicula is not None:
            if self.movie() is not self._pelicula:
                self.setMovie(self._pelicula)
            if self._pelicula.state() != QMovie.MovieState.Running:
                self._pelicula.start()
            return
        if self._pelicula is not None and \
                self._pelicula.state() == QMovie.MovieState.Running:
            self._pelicula.stop()
        if self.movie() is not None:
            self.setMovie(None)
            self._repintar_fijo()

    def showEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        super().showEvent(evento)
        self._reposicionar()
        self._sincronizar()
        if not self._temporizador.isActive():
            self._temporizador.start()

    def hideEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        self._temporizador.stop()
        self._sincronizar()
        super().hideEvent(evento)
