"""Fondo animado de radar MILITAR — visión nocturna (Inicio, v1.0.5).

Hasta la v1.0.4 el radar era azul/cian con «partículas». El usuario
pidió un radar de apariencia militar realista: fondo VERDE ELÉCTRICO
estilo visión nocturna, el haz barriendo, y las bolitas convertidas en
AMENAZAS pequeñas que el radar caza: virus, bichitos tipo alien y
archivos rotos — dibujados con QPainter (sin archivos externos),
derivando despacio por el fondo y ENCENDIÉNDOSE cuando el haz los
toca, como un contacto en una pantalla de radar de verdad.

La zona del escáner es un poco más grande que antes (280 px de alto
mínimo frente a 230). Todo sigue gobernado por el mismo interruptor:
si Ajustes desactiva el fondo animado, la animación se detiene y queda
un cuadro estático (sin gasto de CPU). El AnilloSalud se pinta encima,
sin cambios. Temporizador de 50 ms y 14 contactos: adorno ligero.
"""
import math
import random

from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

# Paleta visión nocturna
_FONDO_A = QColor(2, 18, 10)      # verde casi negro
_FONDO_B = QColor(5, 30, 16)
_VERDE = QColor(57, 255, 142)     # verde eléctrico
_CLARO = QColor(190, 255, 214)    # borde líder del haz / contacto vivo
_OSCURO_OJO = QColor(3, 20, 10)

_TIPOS_AMENAZA = ("virus", "bicho", "archivo")


class _Amenaza:
    """Un contacto del radar: deriva despacio y guarda su último
    «toque» del haz para encenderse y apagarse poco a poco."""

    __slots__ = ("x", "y", "vx", "vy", "tipo", "tam", "brillo")

    def __init__(self, aleatorio: random.Random):
        self.x = aleatorio.uniform(0.06, 0.94)
        self.y = aleatorio.uniform(0.10, 0.90)
        angulo = aleatorio.uniform(0, math.tau)
        velocidad = aleatorio.uniform(0.05, 0.13)
        self.vx = math.cos(angulo) * velocidad
        self.vy = math.sin(angulo) * velocidad * 0.6
        self.tipo = aleatorio.choice(_TIPOS_AMENAZA)
        self.tam = aleatorio.uniform(13.0, 19.0)
        self.brillo = 0.0


def _dibujar_virus(p: QPainter, x: float, y: float, r: float,
                   color: QColor) -> None:
    """Virus: círculo con púas rematadas en bolita y puntos interiores."""
    p.setPen(QPen(color, 1.6))
    p.setBrush(color)
    for k in range(8):
        a = k * math.tau / 8
        p.drawLine(QPointF(x + math.cos(a) * r * 0.7,
                           y + math.sin(a) * r * 0.7),
                   QPointF(x + math.cos(a) * r * 1.15,
                           y + math.sin(a) * r * 1.15))
        p.drawEllipse(QPointF(x + math.cos(a) * r * 1.22,
                              y + math.sin(a) * r * 1.22), 1.7, 1.7)
    p.drawEllipse(QPointF(x, y), r * 0.72, r * 0.72)
    p.setBrush(_OSCURO_OJO)
    p.setPen(Qt.PenStyle.NoPen)
    for dx, dy in ((-0.28, -0.18), (0.25, 0.05), (-0.02, 0.3)):
        p.drawEllipse(QPointF(x + dx * r, y + dy * r), r * 0.13, r * 0.13)


def _dibujar_bicho(p: QPainter, x: float, y: float, r: float,
                   color: QColor) -> None:
    """Bichito tipo alien: cabeza ovalada, ojos grandes y antenas."""
    p.setPen(QPen(color, 1.6))
    p.setBrush(color)
    for s in (-1, 1):
        p.drawLine(QPointF(x + s * r * 0.35, y - r * 0.55),
                   QPointF(x + s * r * 0.62, y - r * 0.95))
        p.drawEllipse(QPointF(x + s * r * 0.66, y - r * 1.0), 2.0, 2.0)
    p.drawEllipse(QPointF(x, y), r * 0.78, r * 0.62)
    p.setBrush(_OSCURO_OJO)
    p.setPen(Qt.PenStyle.NoPen)
    for s in (-1, 1):
        p.drawEllipse(QPointF(x + s * r * 0.32, y - r * 0.08),
                      r * 0.17, r * 0.26)


def _dibujar_archivo_roto(p: QPainter, x: float, y: float, r: float,
                          color: QColor) -> None:
    """Archivo roto: hoja con la esquina doblada y una grieta en zigzag."""
    w, h = r * 1.05, r * 1.35
    p.setPen(QPen(color, 1.6))
    relleno = QColor(color)
    relleno.setAlpha(60)
    p.setBrush(relleno)
    ruta = QPainterPath()
    ruta.moveTo(x - w / 2, y - h / 2)
    ruta.lineTo(x + w * 0.18, y - h / 2)
    ruta.lineTo(x + w / 2, y - h * 0.14)
    ruta.lineTo(x + w / 2, y + h / 2)
    ruta.lineTo(x - w / 2, y + h / 2)
    ruta.closeSubpath()
    p.drawPath(ruta)
    grieta = QPainterPath()
    grieta.moveTo(x - r * 0.05, y - h * 0.32)
    grieta.lineTo(x + r * 0.18, y - h * 0.05)
    grieta.lineTo(x - r * 0.12, y + h * 0.18)
    grieta.lineTo(x + r * 0.1, y + h * 0.42)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(color, 1.8))
    p.drawPath(grieta)


_DIBUJOS = {"virus": _dibujar_virus, "bicho": _dibujar_bicho,
            "archivo": _dibujar_archivo_roto}


class FondoRadar(QWidget):
    """Radar verde de visión nocturna con amenazas que caza el haz."""

    def __init__(self, parent=None, animado: bool = True):
        super().__init__(parent)
        self.setMinimumHeight(280)  # zona del escáner un poco mayor
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._angulo = 0.0
        self._aleatorio = random.Random(20261124)
        self._amenazas = [_Amenaza(self._aleatorio) for _ in range(14)]
        self._temporizador = QTimer(self)
        self._temporizador.setInterval(50)
        self._temporizador.timeout.connect(self._avanzar)
        self._deseado = bool(animado)

    # -- control externo (interruptor de Ajustes) -------------------------------
    def activar_animacion(self, activa: bool) -> None:
        self._deseado = bool(activa)
        if activa and self.isVisible():
            self._temporizador.start()
        elif not activa:
            self._temporizador.stop()
        self.update()

    def showEvent(self, evento):  # noqa: N802 - nombre de Qt
        super().showEvent(evento)
        if self._deseado:
            self._temporizador.start()

    def hideEvent(self, evento):  # noqa: N802 - nombre de Qt
        self._temporizador.stop()
        super().hideEvent(evento)

    def animando(self) -> bool:
        return self._temporizador.isActive()

    # -- animación ----------------------------------------------------------------
    def _avanzar(self) -> None:
        self._angulo = (self._angulo + 3.4) % 360.0
        for am in self._amenazas:
            am.x += am.vx * 0.05
            am.y += am.vy * 0.05
            if not 0.03 < am.x < 0.97:
                am.vx = -am.vx
                am.x = min(max(am.x, 0.03), 0.97)
            if not 0.06 < am.y < 0.94:
                am.vy = -am.vy
                am.y = min(max(am.y, 0.06), 0.94)
            # ¿El haz la está tocando? diferencia angular con el barrido
            ang = math.degrees(math.atan2(-(am.y - 0.52), am.x - 0.5)) % 360.0
            if (self._angulo - ang) % 360.0 < 14.0:
                am.brillo = 1.0
            else:
                am.brillo = max(0.0, am.brillo - 0.012)
        self.update()

    # -- pintura --------------------------------------------------------------------
    def paintEvent(self, evento):  # noqa: N802 - nombre de Qt
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = float(self.width()), float(self.height())
        # Fondo: viñeta verde visión nocturna
        grad = QRadialGradient(w / 2, h / 2, max(w, h) * 0.75)
        grad.setColorAt(0.0, _FONDO_B)
        grad.setColorAt(1.0, _FONDO_A)
        p.fillRect(self.rect(), grad)
        cx, cy = w / 2, h * 0.52
        radio = min(w, h) * 0.46
        # Anillos y cruz del radar
        p.setBrush(Qt.BrushStyle.NoBrush)
        for frac, alfa in ((1.0, 120), (0.66, 80), (0.33, 60)):
            c = QColor(_VERDE)
            c.setAlpha(alfa)
            p.setPen(QPen(c, 1.2))
            p.drawEllipse(QPointF(cx, cy), radio * frac, radio * frac)
        c = QColor(_VERDE)
        c.setAlpha(50)
        p.setPen(QPen(c, 1.0))
        p.drawLine(QPointF(cx - radio, cy), QPointF(cx + radio, cy))
        p.drawLine(QPointF(cx, cy - radio), QPointF(cx, cy + radio))
        # Haz del barrido: sector con estela + borde líder brillante
        p.setPen(Qt.PenStyle.NoPen)
        for pasos, alfa in ((10, 10), (6, 18), (3, 30), (0, 52)):
            c = QColor(_VERDE)
            c.setAlpha(alfa)
            p.setBrush(c)
            sector = QPainterPath()
            sector.moveTo(cx, cy)
            sector.arcTo(QRectF(cx - radio, cy - radio, radio * 2, radio * 2),
                         self._angulo - pasos * 2.2, 2.2 * pasos + 0.1)
            sector.closeSubpath()
            p.drawPath(sector)
        a = math.radians(self._angulo)
        p.setPen(QPen(_CLARO, 2.0))
        p.drawLine(QPointF(cx, cy),
                   QPointF(cx + math.cos(a) * radio, cy - math.sin(a) * radio))
        # Amenazas: tenues en reposo; se ENCIENDEN al tocarlas el haz
        for am in self._amenazas:
            x, y = am.x * w, am.y * h
            if am.brillo > 0.25:  # halo de contacto detectado
                halo = QColor(_VERDE)
                halo.setAlpha(int(60 * am.brillo))
                p.setBrush(halo)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(x, y), am.tam * 1.15, am.tam * 1.15)
            color = QColor(_VERDE if am.brillo < 0.55 else _CLARO)
            color.setAlpha(int(70 + 185 * am.brillo))
            _DIBUJOS[am.tipo](p, x, y, am.tam * 0.62, color)
        p.end()
