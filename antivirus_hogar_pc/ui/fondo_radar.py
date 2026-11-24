"""Fondo de radar/sonar FUTURISTA premium (Inicio, v1.0.6 — nota 9).

Diseño definido por el usuario tras probar la 1.0.5 («el verde se
ve un poco falso»): pantalla PPI de ciencia ficción, «algo caro»:

- Barrido VERDE ELÉCTRICO AMPLIO Y COMPLETO: la cuña cubre la
  imagen entera hasta las esquinas (el radio del haz es la
  distancia a la esquina, no el círculo inscrito) y su estela se
  apaga con PERSISTENCIA DE FÓSFORO real: decenas de sectores
  finos con caída exponencial de brillo, nada de franjas duras.
- ONDAS DE ESCANEO: anillos que nacen en el centro y se expanden
  hasta el borde desvaneciéndose, como un sonar futurista.
- TRIDIMENSIONAL holográfico: cúpula de cristal sobre el disco
  (luz cenital suave), bisel luminoso en el borde, sombra interior
  y resplandor eléctrico tenue alrededor, con líneas de barrido
  de pantalla (scanlines) muy sutiles.
- Las AMENAZAS de siempre (virus, bichitos alien, archivos
  rotos) derivan por el fondo y MUEREN al paso del haz (destello
  y desvanecimiento con anillo de choque), RENACIENDO poco
  después en otro punto, en un ciclo continuo: la escena nunca
  queda vacía y el barrido siempre está «cazando» algo.
- Interruptor de Ajustes: sin animación queda un cuadro estático
  (y la puerta global de ui.animacion también lo detiene).

Temporizador propio de 50 ms y 14 contactos: adorno ligero. El
AnilloSalud se pinta encima, sin cambios.
"""
import math
import random

from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

# Paleta visión nocturna eléctrica
_FONDO_A = QColor(1, 12, 7)       # verde casi negro (bordes)
_FONDO_B = QColor(4, 26, 14)      # verde profundo (centro)
_VERDE = QColor(57, 255, 142)     # verde eléctrico
_CLARO = QColor(196, 255, 218)    # borde líder del haz / contacto vivo
_OSCURO_OJO = QColor(3, 20, 10)

_TIPOS_AMENAZA = ("virus", "bicho", "archivo")

# Estela del haz: sectores finos con caída exponencial (fósforo).
_PASOS_ESTELA = 64
_ALCANCE_ESTELA = 105.0  # grados de estela tras el borde líder


class _Amenaza:
    """Un contacto del radar: deriva despacio; el haz lo MATA al
    tocarlo (estado «muriendo»: destello y desvanecimiento) y poco
    después RENACE en otro punto (estado «renaciendo»: aparece
    creciendo), en ciclo continuo."""

    __slots__ = ("x", "y", "vx", "vy", "tipo", "tam", "brillo",
                 "estado", "t_estado")

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
        self.estado = "viva"
        self.t_estado = 0.0


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
    """Radar/sonar futurista verde eléctrico con amenazas que caza
    el haz y ondas de escaneo que se expanden."""

    def __init__(self, parent=None, animado: bool = True):
        super().__init__(parent)
        self.setMinimumHeight(280)  # zona del escáner
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._angulo = 0.0
        self._t = 0.0  # reloj interno (ondas y centelleo eléctrico)
        self._aleatorio = random.Random(20261124)
        self._amenazas = [_Amenaza(self._aleatorio) for _ in range(14)]
        self._temporizador = QTimer(self)
        self._temporizador.setInterval(50)
        self._temporizador.timeout.connect(self._avanzar)
        self._deseado = bool(animado)

    # -- control externo (interruptor de Ajustes) -------------------------------
    def activar_animacion(self, activa: bool) -> None:
        self._deseado = bool(activa)
        if activa and self.isVisible() and self._puerta_abierta():
            self._temporizador.start()
        elif not activa:
            self._temporizador.stop()
        self.update()

    def _puerta_abierta(self) -> bool:
        from .animacion import animaciones_activas

        return animaciones_activas()

    def showEvent(self, evento):  # noqa: N802 - nombre de Qt
        super().showEvent(evento)
        if self._deseado and self._puerta_abierta():
            self._temporizador.start()

    def hideEvent(self, evento):  # noqa: N802 - nombre de Qt
        self._temporizador.stop()
        super().hideEvent(evento)

    def animando(self) -> bool:
        return self._temporizador.isActive()

    # -- animación ----------------------------------------------------------------
    def _avanzar(self) -> None:
        self._angulo = (self._angulo + 3.4) % 360.0
        self._t += 0.05
        w = max(1.0, float(self.width()))
        h = max(1.0, float(self.height()))
        cx, cy = w / 2, h / 2
        for am in self._amenazas:
            am.x += am.vx * 0.05
            am.y += am.vy * 0.05
            if not 0.03 < am.x < 0.97:
                am.vx = -am.vx
                am.x = min(max(am.x, 0.03), 0.97)
            if not 0.06 < am.y < 0.94:
                am.vy = -am.vy
                am.y = min(max(am.y, 0.06), 0.94)
            # Ciclo de vida: viva → (el haz la toca) muriendo →
            # renaciendo en otro punto → viva.
            ang = math.degrees(
                math.atan2(-(am.y * h - cy), am.x * w - cx)) % 360.0
            am.t_estado += 0.05
            if am.estado == "viva":
                if (self._angulo - ang) % 360.0 < 14.0:
                    am.estado = "muriendo"
                    am.t_estado = 0.0
                    am.brillo = 1.0  # destello de muerte
                else:
                    am.brillo = max(0.0, am.brillo - 0.008)
            elif am.estado == "muriendo":
                am.brillo = max(0.0, 1.0 - am.t_estado / 0.45)
                if am.t_estado >= 0.45:
                    am.x = self._aleatorio.uniform(0.06, 0.94)
                    am.y = self._aleatorio.uniform(0.10, 0.90)
                    am.estado = "renaciendo"
                    am.t_estado = 0.0
            elif am.estado == "renaciendo":
                if am.t_estado >= 0.8:
                    am.estado = "viva"
                    am.brillo = 0.45
        self.update()

    # -- pintura --------------------------------------------------------------------
    def paintEvent(self, evento):  # noqa: N802 - nombre de Qt
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = float(self.width()), float(self.height())
        cx, cy = w / 2, h / 2
        radio_corto = min(w, h) * 0.46
        # El haz llega hasta las ESQUINAS: radio = distancia a la esquina.
        radio_total = math.hypot(w / 2, h / 2) * 1.02

        # Fondo: viñeta verde profunda
        grad = QRadialGradient(cx, cy, max(w, h) * 0.75)
        grad.setColorAt(0.0, _FONDO_B)
        grad.setColorAt(1.0, _FONDO_A)
        p.fillRect(self.rect(), grad)

        # Resplandor eléctrico ambiental alrededor del disco
        halo = QRadialGradient(cx, cy, radio_total)
        halo.setColorAt(0.72, QColor(57, 255, 142, 0))
        halo.setColorAt(0.92, QColor(57, 255, 142, 16))
        halo.setColorAt(1.0, QColor(57, 255, 142, 0))
        p.fillRect(self.rect(), halo)

        recto_total = QRectF(cx - radio_total, cy - radio_total,
                             radio_total * 2, radio_total * 2)

        # ESTELA DE FÓSFORO: sectores finos con caída exponencial
        # tras el borde líder (suave, sin franjas duras).
        p.setPen(Qt.PenStyle.NoPen)
        paso = _ALCANCE_ESTELA / _PASOS_ESTELA
        for i in range(_PASOS_ESTELA):
            retraso = i * paso
            alfa = int(64 * math.exp(-3.2 * i / _PASOS_ESTELA))
            if alfa < 2:
                continue
            c = QColor(_VERDE)
            c.setAlpha(alfa)
            p.setBrush(c)
            sector = QPainterPath()
            sector.moveTo(cx, cy)
            sector.arcTo(recto_total, self._angulo - retraso - paso,
                         paso + 0.35)
            sector.closeSubpath()
            p.drawPath(sector)
        # Núcleo brillante pegado al borde líder
        for ancho, alfa in ((26.0, 26), (12.0, 40)):
            c = QColor(_VERDE)
            c.setAlpha(alfa)
            p.setBrush(c)
            sector = QPainterPath()
            sector.moveTo(cx, cy)
            sector.arcTo(recto_total, self._angulo - ancho, ancho + 0.1)
            sector.closeSubpath()
            p.drawPath(sector)
        # Borde líder: línea con resplandor (tres pasadas)
        a = math.radians(self._angulo)
        fin = QPointF(cx + math.cos(a) * radio_total,
                      cy - math.sin(a) * radio_total)
        for grosor, alfa in ((7.0, 40), (3.5, 90), (1.8, 235)):
            c = QColor(_CLARO)
            c.setAlpha(alfa)
            p.setPen(QPen(c, grosor))
            p.drawLine(QPointF(cx, cy), fin)

        # Anillos de alcance y marcas de rumbo (hasta el borde)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for frac, alfa in ((0.33, 55), (0.66, 75), (1.0, 110)):
            c = QColor(_VERDE)
            c.setAlpha(alfa)
            p.setPen(QPen(c, 1.2))
            p.drawEllipse(QPointF(cx, cy), radio_corto * frac,
                          radio_corto * frac)
        for frac, alfa in ((1.35, 42), (1.7, 26)):
            c = QColor(_VERDE)
            c.setAlpha(alfa)
            p.setPen(QPen(c, 1.0))
            p.drawEllipse(QPointF(cx, cy), radio_corto * frac,
                          radio_corto * frac)
        c = QColor(_VERDE)
        c.setAlpha(46)
        p.setPen(QPen(c, 1.0))
        p.drawLine(QPointF(cx - radio_total, cy), QPointF(cx + radio_total, cy))
        p.drawLine(QPointF(cx, cy - radio_total), QPointF(cx, cy + radio_total))
        for k in range(12):  # marcas de rumbo cada 30°
            ang = math.radians(k * 30)
            r1 = radio_corto * 0.94
            r2 = radio_corto * (1.0 if k % 3 == 0 else 0.97)
            c = QColor(_VERDE)
            c.setAlpha(120 if k % 3 == 0 else 70)
            p.setPen(QPen(c, 1.4))
            p.drawLine(QPointF(cx + math.cos(ang) * r1,
                               cy + math.sin(ang) * r1),
                       QPointF(cx + math.cos(ang) * r2,
                               cy + math.sin(ang) * r2))

        # ONDAS DE ESCANEO: nacen en el centro y se expanden
        # desvaneciéndose (periodo 2,7 s, dos ondas desfasadas).
        for desfase in (0.0, 0.5):
            fase = ((self._t / 2.7) + desfase) % 1.0
            r_onda = radio_total * fase
            alfa = int(120 * (1.0 - fase) ** 2)
            if alfa > 3 and r_onda > 4:
                c = QColor(_VERDE)
                c.setAlpha(alfa)
                p.setPen(QPen(c, 2.2 * (1.0 - fase) + 0.6))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(cx, cy), r_onda, r_onda)

        # Centelleo eléctrico sutil en el bisel (determinista por t)
        rng = random.Random(int(self._t * 7))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for _ in range(5):
            ang = rng.uniform(0, math.tau)
            r_b = radio_corto * rng.uniform(0.97, 1.03)
            c = QColor(_CLARO)
            c.setAlpha(rng.randint(18, 46))
            p.setPen(QPen(c, 1.1))
            p.drawLine(QPointF(cx + math.cos(ang) * r_b,
                               cy + math.sin(ang) * r_b),
                       QPointF(cx + math.cos(ang + 0.05) * r_b * 1.02,
                               cy + math.sin(ang + 0.05) * r_b * 1.02))

        # Amenazas según su estado del ciclo de vida
        for am in self._amenazas:
            x, y = am.x * w, am.y * h
            if am.estado == "muriendo":
                f = min(1.0, am.t_estado / 0.45)
                # Anillo de choque de la muerte, expandiéndose
                c = QColor(_CLARO)
                c.setAlpha(int(175 * (1.0 - f)))
                p.setPen(QPen(c, 2.0))
                p.setBrush(Qt.BrushStyle.NoBrush)
                r_choque = am.tam * (1.0 + 2.4 * f)
                p.drawEllipse(QPointF(x, y), r_choque, r_choque)
                # La figura se encoge y se desvanece en blanco
                color = QColor(_CLARO)
                color.setAlpha(int(255 * (1.0 - f)))
                _DIBUJOS[am.tipo](p, x, y,
                                  am.tam * 0.62 * (1.0 - 0.8 * f), color)
            elif am.estado == "renaciendo":
                f = min(1.0, am.t_estado / 0.8)
                halo_am = QColor(_VERDE)
                halo_am.setAlpha(int(55 * f))
                p.setBrush(halo_am)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(x, y), am.tam * 1.1, am.tam * 1.1)
                color = QColor(_VERDE)
                color.setAlpha(int(50 + 170 * f))
                _DIBUJOS[am.tipo](p, x, y,
                                  am.tam * 0.62 * (0.25 + 0.75 * f), color)
            else:  # viva: tenue en reposo, halo si aún guarda brillo
                if am.brillo > 0.2:
                    halo_am = QColor(_VERDE)
                    halo_am.setAlpha(int(70 * am.brillo))
                    p.setBrush(halo_am)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(QPointF(x, y), am.tam * 1.2, am.tam * 1.2)
                color = QColor(_VERDE if am.brillo < 0.55 else _CLARO)
                color.setAlpha(int(70 + 185 * am.brillo))
                _DIBUJOS[am.tipo](p, x, y, am.tam * 0.62, color)

        # CÚPULA DE CRISTAL (3D holográfico): luz cenital sobre el
        # disco + sombra interior en el borde inferior.
        p.save()
        disco = QPainterPath()
        disco.addEllipse(QPointF(cx, cy), radio_corto, radio_corto)
        p.setClipPath(disco)
        luz = QRadialGradient(cx - radio_corto * 0.35,
                              cy - radio_corto * 0.55, radio_corto * 1.25)
        luz.setColorAt(0.0, QColor(210, 255, 226, 34))
        luz.setColorAt(0.55, QColor(210, 255, 226, 8))
        luz.setColorAt(1.0, QColor(210, 255, 226, 0))
        p.fillRect(QRectF(cx - radio_corto, cy - radio_corto,
                          radio_corto * 2, radio_corto * 2), luz)
        p.restore()
        # Bisel luminoso del disco (borde «caro»)
        c = QColor(_VERDE)
        c.setAlpha(150)
        p.setPen(QPen(c, 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), radio_corto, radio_corto)
        c = QColor(_CLARO)
        c.setAlpha(50)
        p.setPen(QPen(c, 3.2))
        p.drawEllipse(QPointF(cx, cy), radio_corto + 2.5, radio_corto + 2.5)

        # Scanlines de pantalla holográfica (muy sutiles)
        p.setPen(QPen(QColor(0, 0, 0, 26), 1))
        y = 2.0
        while y < h:
            p.drawLine(QPointF(0, y), QPointF(w, y))
            y += 4.0
        p.end()
