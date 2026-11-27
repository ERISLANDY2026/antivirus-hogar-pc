"""La marca «WAR — Home Guardian» del encabezado (v1.0.22).

El nombre nuevo de la app, SOLO en inglés, aprobado por el
usuario «así tal cual» el 2026-11-27: va arriba, en el
encabezado sobre el panel izquierdo. «WAR» grande en degradado
cian eléctrico — el mismo cian del «GUERRA» del escudo del
espartano — con borde dorado fino y arcos de energía lentos
como los del escudo; «Home Guardian» debajo, en plateado, más
pequeño y tranquilo.

Animación (la aprobada): al abrir la app, las letras se
encienden con un barrido tipo radar, de izquierda a derecha;
después, un barrido de luz cruza las letras cada pocos
segundos y un resplandor cian respira suave detrás. Todo va
con el reloj compartido de ui.animacion: la puerta global de
Ajustes manda (apagada = marca estática, ya encendida), la
pausa con la ventana oculta/minimizada lo detiene todo, y sin
suscriptores visibles el reloj se para — cero CPU en la
bandeja, como el resto de la casa.
"""
import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from . import theme

TEXTO_WAR = "WAR"
TEXTO_SUB = "Home Guardian"
_DORADO = QColor("#E3B341")
_PLATA = QColor("#C7CDD6")
_APAGADO = QColor(38, 54, 74)  # letra aún sin encender (encendido inicial)

_CICLO_BARRIDO_S = 6.0     # un barrido de luz cada ~6 s
_DURACION_BARRIDO_S = 1.1  # lo que tarda en cruzar
_DURACION_ENCENDIDO_S = 1.4


class MarcaWAR(QWidget):
    """El nombre de la app pintado a mano en el encabezado."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._suscrito = False
        self._t = 0.0
        self._encendido_en: float | None = None  # t del primer tic visible
        fuente_war = QFont()
        fuente_war.setPointSize(27)
        fuente_war.setWeight(QFont.Weight.Black)
        fuente_war.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)
        self._fuente_war = fuente_war
        fuente_sub = QFont()
        fuente_sub.setPointSize(11)
        fuente_sub.setWeight(QFont.Weight.DemiBold)
        fuente_sub.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3.2)
        self._fuente_sub = fuente_sub
        from PySide6.QtGui import QFontMetricsF

        m_war = QFontMetricsF(fuente_war)
        m_sub = QFontMetricsF(fuente_sub)
        ancho = max(m_war.horizontalAdvance(TEXTO_WAR),
                    m_sub.horizontalAdvance(TEXTO_SUB)) + 14
        alto = m_war.height() + m_sub.height() + 8
        self.setFixedSize(int(ancho) + 4, int(alto))

    # -- geometría del texto ------------------------------------------------
    def _rutas(self) -> tuple[QPainterPath, QPainterPath, QRectF]:
        from PySide6.QtGui import QFontMetricsF

        m_war = QFontMetricsF(self._fuente_war)
        base_war = m_war.ascent() + 2
        ruta_war = QPainterPath()
        ruta_war.addText(2.0, base_war, self._fuente_war, TEXTO_WAR)
        m_sub = QFontMetricsF(self._fuente_sub)
        base_sub = base_war + m_war.descent() + m_sub.ascent() + 3
        ruta_sub = QPainterPath()
        ruta_sub.addText(3.0, base_sub, self._fuente_sub, TEXTO_SUB)
        return ruta_war, ruta_sub, ruta_war.boundingRect()

    # -- suscripción al reloj compartido (patrón de la casa) ------------------
    def showEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        super().showEvent(evento)
        from .animacion import RELOJ, animaciones_activas

        if animaciones_activas() and not self._suscrito:
            RELOJ.tic.connect(self._al_tic)
            RELOJ.suscribir()
            self._suscrito = True
        self.update()

    def hideEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        super().hideEvent(evento)
        if self._suscrito:
            from .animacion import RELOJ

            try:
                RELOJ.tic.disconnect(self._al_tic)
            except (RuntimeError, TypeError):
                pass
            RELOJ.desuscribir()
            self._suscrito = False

    def _al_tic(self, t: float) -> None:
        self._t = t
        if self._encendido_en is None:
            self._encendido_en = t
        self.update()

    # -- pintura ---------------------------------------------------------------
    def paintEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        from .animacion import animaciones_activas

        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        ruta_war, ruta_sub, caja = self._rutas()
        animado = animaciones_activas() and self._suscrito
        t = self._t if animado else 999.0

        # Progreso del encendido inicial (barrido tipo radar al
        # abrir): sin animación, la marca nace ya encendida.
        if not animado or self._encendido_en is None:
            encendido = 1.0
        else:
            encendido = min(1.0, max(0.0, (t - self._encendido_en)
                                     / _DURACION_ENCENDIDO_S))

        # 1) Resplandor cian que respira (detrás de las letras).
        respiro = 0.5 + 0.5 * math.sin(t * 1.1)
        alfa_glow = int(46 + 40 * respiro) if animado else 60
        pen_glow = QPen(QColor(34, 211, 238, alfa_glow))
        pen_glow.setWidth(7)
        pintor.setPen(pen_glow)
        pintor.setBrush(Qt.BrushStyle.NoBrush)
        pintor.drawPath(ruta_war)

        # 2) Letras aún apagadas (solo se ven durante el encendido).
        if encendido < 1.0:
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.setBrush(_APAGADO)
            pintor.drawPath(ruta_war)

        # 3) El degradado cian eléctrico, recortado por el
        #    encendido (izquierda→derecha) y, en su ventana del
        #    ciclo, cruzado por el barrido de luz.
        degradado = QLinearGradient(0, caja.top(), 0, caja.bottom())
        degradado.setColorAt(0.0, QColor("#8DF3FF"))
        degradado.setColorAt(0.5, QColor(theme.CIAN))
        degradado.setColorAt(1.0, QColor("#0E7E9B"))
        pintor.save()
        if encendido < 1.0:
            limite = caja.left() + caja.width() * encendido
            pintor.setClipRect(QRectF(0, 0, limite, self.height()))
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(degradado)
        pintor.drawPath(ruta_war)
        # Barrido de luz: una banda clara que cruza las letras.
        fase = (t % _CICLO_BARRIDO_S) if animado else 99.0
        if encendido >= 1.0 and fase < _DURACION_BARRIDO_S:
            avance = fase / _DURACION_BARRIDO_S
            x = caja.left() - 18 + (caja.width() + 36) * avance
            banda = QLinearGradient(x - 16, 0, x + 16, 0)
            banda.setColorAt(0.0, QColor(255, 255, 255, 0))
            banda.setColorAt(0.5, QColor(255, 255, 255, 110))
            banda.setColorAt(1.0, QColor(255, 255, 255, 0))
            pintor.setBrush(banda)
            pintor.drawPath(ruta_war)
        pintor.restore()

        # 4) Borde dorado fino de las letras.
        pen_oro = QPen(_DORADO)
        pen_oro.setWidthF(0.9)
        pintor.setPen(pen_oro)
        pintor.setBrush(Qt.BrushStyle.NoBrush)
        if encendido < 1.0:
            pintor.save()
            limite = caja.left() + caja.width() * encendido
            pintor.setClipRect(QRectF(0, 0, limite, self.height()))
            pintor.drawPath(ruta_war)
            pintor.restore()
        else:
            pintor.drawPath(ruta_war)

        # 5) Arcos de energía lentos sobre las letras, como los
        #    del escudo del espartano: dos arcos que se desplazan
        #    despacio en sentidos opuestos por encima del nombre.
        if animado:
            for i, velocidad in enumerate((0.11, -0.07)):
                angulo0 = (t * 360.0 * velocidad + i * 170.0) % 360.0
                pen_arco = QPen(QColor(56, 224, 255, 120 - i * 35))
                pen_arco.setWidthF(1.4)
                pintor.setPen(pen_arco)
                margen = 3 + i * 4
                recto = QRectF(caja.left() - margen, caja.top() - margen,
                               caja.width() + 2 * margen,
                               caja.height() + 2 * margen)
                pintor.drawArc(recto, int(angulo0 * 16), int(52 * 16))

        # 6) «Home Guardian» en plateado, debajo (también se
        #    enciende con el barrido inicial).
        if encendido < 1.0:
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.setBrush(_APAGADO)
            pintor.drawPath(ruta_sub)
            pintor.save()
            limite = caja.left() + caja.width() * encendido
            pintor.setClipRect(QRectF(0, 0, limite, self.height()))
            pintor.setBrush(_PLATA)
            pintor.drawPath(ruta_sub)
            pintor.restore()
        else:
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.setBrush(_PLATA)
            pintor.drawPath(ruta_sub)
        pintor.end()
