"""Iconos vectoriales (SVG de trazo) y widget de icono ANIMADO.

El usuario pidió un icono al frente de cada fila de estado, animado si es
posible: escudo de Defender que pulsa, llama del Firewall que titila,
flechas de Actualizaciones que giran y LED del Disco que parpadea.
"""
from PySide6.QtCore import QByteArray, QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from . import theme

# Trazo 24x24, stroke con el color indicado, sin relleno (salvo el LED).
_SVG = {
    "escudo": '<path d="M12 3l7 2.8v5.4c0 4.6-2.9 7.7-7 9.3-4.1-1.6-7-4.7-7-9.3V5.8L12 3z"/>'
              '<path d="M8.8 11.6l2.2 2.2 4.2-4.6"/>',
    "llama": '<path d="M12 3.5c.9 3.2-2.3 4.6-2.3 7.2a2.4 2.4 0 0 0 4.7 0c0-1-.6-1.8-1.1-2.7 '
             '2 1.2 3.2 3 3.2 5A6.5 6.5 0 0 1 12 20.5 6.5 6.5 0 0 1 5.5 14c0-4.2 3.4-6.4 6.5-10.5z"/>',
    "actualizar": '<path d="M20 12a8 8 0 1 1-2.5-5.8"/><path d="M20.5 3.5v4h-4"/>',
    "disco": '<rect x="3.5" y="7" width="17" height="10" rx="2"/>'
             '<circle cx="17" cy="12" r="1.4" fill="{color}" stroke="none"/>'
             '<path d="M6.5 10.2h6M6.5 13.8h4"/>',
    "inicio": '<path d="M4 11.2L12 4l8 7.2"/><path d="M6 9.8V20h12V9.8"/><path d="M10 20v-5h4v5"/>',
    "lupa": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.3 15.3L20.5 20.5"/>',
    "limpieza": '<path d="M5 19l7.5-1.2L20 5.5a2.1 2.1 0 0 0-3-3L4.8 10 5 19z"/>'
                '<path d="M13.5 6.5l4 4M4 21h9"/>',
    "red": '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.6 2.3 3.9 5.2 3.9 8.5'
           's-1.3 6.2-3.9 8.5c-2.6-2.3-3.9-5.2-3.9-8.5S9.4 5.8 12 3.5z"/>',
    "informe": '<path d="M6 3.5h8L19 8v12.5H6z"/><path d="M13.5 3.5V8H19"/>'
               '<path d="M9 12.5h6M9 16h6"/>',
    "chip": '<rect x="7" y="7" width="10" height="10" rx="1.6"/>'
            '<path d="M10 4v3M14 4v3M10 17v3M14 17v3M4 10h3M4 14h3M17 10h3M17 14h3"/>',
    "engranaje": '<circle cx="12" cy="12" r="3.2"/>'
                 '<path d="M12 3.8v3M12 17.2v3M3.8 12h3M17.2 12h3M6.2 6.2l2.1 2.1M15.7 15.7l2.1 2.1'
                 'M17.8 6.2l-2.1 2.1M8.3 15.7l-2.1 2.1"/>',
    "carpeta": '<path d="M3.5 6.5A1.5 1.5 0 0 1 5 5h4l2 2.5h8A1.5 1.5 0 0 1 20.5 9v9A1.5 1.5 0 0 1 19 19.5H5'
               'A1.5 1.5 0 0 1 3.5 18z"/>',
    "alerta": '<path d="M12 4L21 20H3z"/><path d="M12 10v4.2"/><circle cx="12" cy="17" r="0.6" fill="{color}"/>',
    "wifi": '<path d="M4 10.5a12 12 0 0 1 16 0M6.8 13.8a8 8 0 0 1 10.4 0M9.6 17a4 4 0 0 1 4.8 0"/>'
            '<circle cx="12" cy="19.4" r="1" fill="{color}" stroke="none"/>',
    "boton": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
}


def svg_texto(nombre: str, color: str) -> str:
    cuerpo = _SVG[nombre].replace("{color}", color)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" '
        f'stroke-linejoin="round">{cuerpo}</svg>'
    )


def pixmap_icono(nombre: str, color: str, tamano: int = 28) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg_texto(nombre, color).encode("utf-8")))
    pix = QPixmap(tamano, tamano)
    pix.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(pix)
    renderer.render(pintor)
    pintor.end()
    return pix


class IconoAnimado(QWidget):
    """Icono SVG con animación según `modo`:
    - "pulso": escala suave (escudo Defender)
    - "giro": rotación continua (flechas de actualizaciones)
    - "llama": titileo (firewall)
    - "parpadeo": LED que se enciende y apaga (disco)
    - "estatico": sin animación
    """

    def __init__(self, nombre: str, color: str = theme.CIAN, tamano: int = 30,
                 modo: str = "estatico", parent=None):
        super().__init__(parent)
        self._renderer = QSvgRenderer(QByteArray(svg_texto(nombre, color).encode("utf-8")))
        self._modo = modo
        self._fase = 0.0
        self.setFixedSize(tamano, tamano)
        self._temporizador = QTimer(self)
        self._temporizador.timeout.connect(self._avanzar)
        if modo != "estatico":
            self._temporizador.start(50)

    def _avanzar(self) -> None:
        self._fase += 0.16
        self.update()

    def detener(self) -> None:
        self._temporizador.stop()

    def paintEvent(self, _evento) -> None:  # noqa: N802 (API de Qt)
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        lado = min(self.width(), self.height())
        pintor.translate(self.width() / 2, self.height() / 2)
        import math

        if self._modo == "pulso":
            escala = 1.0 + 0.09 * math.sin(self._fase)
            pintor.scale(escala, escala)
        elif self._modo == "giro":
            pintor.rotate(self._fase * 22 % 360)
        elif self._modo == "llama":
            pintor.scale(1.0 + 0.03 * math.sin(self._fase * 2.3),
                         1.0 + 0.07 * math.sin(self._fase * 3.1))
        elif self._modo == "parpadeo":
            if math.sin(self._fase * 1.6) < -0.2:
                pintor.setOpacity(0.25)
        destino = QRectF(-lado / 2, -lado / 2, lado, lado)
        self._renderer.render(pintor, destino)
        pintor.end()
