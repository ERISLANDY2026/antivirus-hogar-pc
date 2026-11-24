"""Anillo de salud animado (QPainter + QPropertyAnimation).

Muestra la puntuación 0–100 con el color semántico que corresponda y un
punto orbital girando mientras hay un escaneo en curso.
"""
import math

from PySide6.QtCore import Property, QPropertyAnimation, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from . import theme


class AnilloSalud(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._valor = 0.0
        self._objetivo = 0
        self._sin_datos = False
        self._girando = False
        self._angulo_orbita = 0.0
        self.setMinimumSize(190, 190)
        self._animacion = QPropertyAnimation(self, b"valor", self)
        self._animacion.setDuration(900)
        self._temporizador = QTimer(self)
        self._temporizador.timeout.connect(self._avanzar_orbita)
        self._temporizador.start(40)

    # -- propiedad animable ---------------------------------------------------
    def _get_valor(self) -> float:
        return self._valor

    def _set_valor(self, v: float) -> None:
        self._valor = float(v)
        self.update()

    valor = Property(float, _get_valor, _set_valor)

    # -- API --------------------------------------------------------------------
    def fijar_puntuacion(self, puntuacion: int, animado: bool = True) -> None:
        self._sin_datos = False
        self._objetivo = max(0, min(100, int(puntuacion)))
        if animado:
            self._animacion.stop()
            self._animacion.setStartValue(self._valor)
            self._animacion.setEndValue(float(self._objetivo))
            self._animacion.start()
        else:
            self._valor = float(self._objetivo)
            self.update()

    def fijar_sin_datos(self) -> None:
        """Sin datos comprobables (p. ej. equipo de pruebas sin Windows):
        se enseña «—» en gris, nunca un 0 en rojo que parezca un desastre."""
        self._animacion.stop()
        self._sin_datos = True
        self._objetivo = 0
        self._valor = 0.0
        self.update()

    def fijar_girando(self, girando: bool) -> None:
        self._girando = girando
        self.update()

    def _avanzar_orbita(self) -> None:
        if self._girando:
            self._angulo_orbita = (self._angulo_orbita + 4) % 360
            self.update()

    # -- pintura ------------------------------------------------------------------
    def _color(self) -> QColor:
        if self._sin_datos:
            return QColor(theme.TEXTO_SUAVE)
        if self._objetivo >= 80:
            return QColor(theme.VERDE)
        if self._objetivo >= 50:
            return QColor(theme.AMBAR)
        return QColor(theme.ROJO)

    def paintEvent(self, _evento) -> None:  # noqa: N802
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        lado = min(self.width(), self.height()) - 16
        rect = QRectF((self.width() - lado) / 2, (self.height() - lado) / 2, lado, lado)
        grosor = 13

        # Fondo del anillo
        pintor.setPen(QPen(QColor(theme.BORDE), grosor, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        pintor.drawArc(rect, 0, 360 * 16)

        # Arco de progreso (desde arriba, en sentido horario)
        color = self._color()
        pintor.setPen(QPen(color, grosor, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        pintor.drawArc(rect, 90 * 16, int(-self._valor / 100 * 360 * 16))

        # Punto orbital mientras se escanea
        if self._girando:
            cx, cy = self.width() / 2, self.height() / 2
            radio = lado / 2
            ang = math.radians(self._angulo_orbita - 90)
            x, y = cx + radio * math.cos(ang), cy + radio * math.sin(ang)
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.setBrush(QColor(theme.CIAN))
            pintor.drawEllipse(QRectF(x - 5, y - 5, 10, 10))

        # Cifra central
        pintor.setPen(QColor(theme.TEXTO))
        fuente = QFont("Segoe UI Variable", 40)
        fuente.setBold(True)
        pintor.setFont(fuente)
        cifra = "—" if self._sin_datos else f"{round(self._valor)}"
        pintor.drawText(QRectF(0, self.height() / 2 - 46, self.width(), 56),
                        Qt.AlignmentFlag.AlignCenter, cifra)
        pintor.setPen(QColor(theme.TEXTO_SUAVE))
        pintor.setFont(QFont("Segoe UI Variable", 11))
        leyenda = "Sin datos de Windows" if self._sin_datos else "Salud del equipo"
        pintor.drawText(QRectF(0, self.height() / 2 + 12, self.width(), 24),
                        Qt.AlignmentFlag.AlignCenter, leyenda)
        pintor.end()
