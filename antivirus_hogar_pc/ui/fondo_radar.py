"""Fondo futurista animado del Panel (v1.0.2, aprobado por el usuario).

Elemento principal: BARRIDO DE RADAR DIGITAL girando suave. Apoyo:
rejilla oscura en movimiento lento, partículas cian subiendo y un
resplandor cian/azul/morado que «respira». Todo se pinta con QPainter
en UNA pasada y el temporizador va con paso grueso (120 ms): es un
adorno, no debe cargar la CPU de una Toughbook.

El anillo de salud se coloca ENCIMA (hijo centrado o en el layout del
padre); este widget solo pinta el fondo. La animación se detiene sola
cuando el widget no está visible, y la página la apaga si el usuario
desactiva el movimiento en Ajustes o Windows pide reducir animaciones.
"""
import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from . import theme

_PASO_MS = 120          # paso grueso a propósito: animación ligera
_N_PARTICULAS = 26


class FondoRadar(QWidget):
    """Banda de fondo con radar; altura recomendada ~230-260 px."""

    def __init__(self, parent=None, animado: bool = True):
        super().__init__(parent)
        self._animado = False
        self._angulo = 0.0            # barrido del radar (grados)
        self._fase_rejilla = 0.0      # desplazamiento lento de la rejilla
        self._fase_respiro = 0.0      # resplandor que respira
        self._rng = random.Random(20261124)
        # partículas: [x_rel, y_rel, velocidad, tamaño]
        self._particulas = [
            [self._rng.random(), self._rng.random(),
             0.002 + self._rng.random() * 0.004, 1.5 + self._rng.random() * 2.0]
            for _ in range(_N_PARTICULAS)
        ]
        self._temporizador = QTimer(self)
        self._temporizador.timeout.connect(self._avanzar)
        self.setMinimumHeight(230)
        if animado:
            self.activar_animacion(True)

    # -- control ---------------------------------------------------------------
    def activar_animacion(self, activa: bool) -> None:
        self._animado = bool(activa)
        if self._animado and self.isVisible():
            self._temporizador.start(_PASO_MS)
        else:
            self._temporizador.stop()
        self.update()

    def showEvent(self, evento):  # noqa: N802
        super().showEvent(evento)
        if self._animado:
            self._temporizador.start(_PASO_MS)

    def hideEvent(self, evento):  # noqa: N802
        self._temporizador.stop()
        super().hideEvent(evento)

    def _avanzar(self) -> None:
        self._angulo = (self._angulo + 3.0) % 360.0
        self._fase_rejilla = (self._fase_rejilla + 0.6) % 28.0
        self._fase_respiro += 0.08
        for p in self._particulas:
            p[1] -= p[2]
            if p[1] < -0.02:
                p[1] = 1.02
                p[0] = self._rng.random()
        self.update()

    # -- pintura -----------------------------------------------------------------
    def paintEvent(self, _evento) -> None:  # noqa: N802
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        ancho, alto = self.width(), self.height()
        centro = QPointF(ancho / 2, alto / 2)
        radio = min(ancho, alto) * 0.46

        # Fondo: degradado oscuro propio (bajo las tarjetas cristal)
        grad = QLinearGradient(0, 0, 0, alto)
        grad.setColorAt(0.0, QColor("#0A101E"))
        grad.setColorAt(1.0, QColor(theme.FONDO))
        pintor.fillRect(self.rect(), grad)

        # Resplandor que respira (cian → azul → morado, muy suave)
        intensidad = 26 + int(10 * (1 + math.sin(self._fase_respiro)) / 2)
        resplandor = QRadialGradient(centro, radio * 1.9)
        resplandor.setColorAt(0.0, QColor(34, 211, 238, intensidad))
        resplandor.setColorAt(0.55, QColor(59, 130, 246, intensidad // 2))
        resplandor.setColorAt(1.0, QColor(147, 51, 234, 0))
        pintor.fillRect(self.rect(), resplandor)

        # Rejilla oscura en movimiento lento
        pintor.setPen(QPen(QColor(56, 78, 122, 60), 1))
        paso = 28.0
        x = -self._fase_rejilla
        while x < ancho:
            pintor.drawLine(QPointF(x, 0), QPointF(x, alto))
            x += paso
        y = -self._fase_rejilla
        while y < alto:
            pintor.drawLine(QPointF(0, y), QPointF(ancho, y))
            y += paso

        # Radar: anillos + barrido cónico girando
        for fraccion in (1.0, 0.66, 0.33):
            pintor.setPen(QPen(QColor(34, 211, 238, 70), 1))
            pintor.setBrush(Qt.BrushStyle.NoBrush)
            r = radio * fraccion
            pintor.drawEllipse(QRectF(centro.x() - r, centro.y() - r, 2 * r, 2 * r))
        pintor.setPen(QPen(QColor(34, 211, 238, 45), 1))
        pintor.drawLine(QPointF(centro.x() - radio, centro.y()),
                        QPointF(centro.x() + radio, centro.y()))
        pintor.drawLine(QPointF(centro.x(), centro.y() - radio),
                        QPointF(centro.x(), centro.y() + radio))
        # Cuña del barrido: abanico de líneas con alpha decreciente
        for i in range(18):
            ang = math.radians(self._angulo - i * 2.2)
            alpha = max(0, 110 - i * 7)
            pintor.setPen(QPen(QColor(34, 211, 238, alpha), 2))
            pintor.drawLine(centro, QPointF(
                centro.x() + radio * math.cos(ang),
                centro.y() + radio * math.sin(ang)))
        ang = math.radians(self._angulo)
        pintor.setPen(QPen(QColor(125, 239, 252, 220), 2))
        pintor.drawLine(centro, QPointF(
            centro.x() + radio * math.cos(ang),
            centro.y() + radio * math.sin(ang)))

        # Partículas cian subiendo
        pintor.setPen(Qt.PenStyle.NoPen)
        for x_rel, y_rel, _vel, tam in self._particulas:
            pintor.setBrush(QColor(103, 232, 249, 130))
            pintor.drawEllipse(QPointF(x_rel * ancho, y_rel * alto), tam, tam)
        pintor.end()
