"""Puerta y reloj GLOBALES de animación de la interfaz (v1.0.6).

Notas 6 y 7 del usuario (su PC real, 1.0.5): los iconos «no tienen
animación» y el acabado moderno debe llegar a TODAS las secciones,
con el interruptor de Ajustes como dueño del movimiento y sin que
su Toughbook se ponga lenta.

Diseño:
- UNA puerta global (`animaciones_activas`): la fija la ventana
  desde el ajuste guardado (`fondo_animado`, el interruptor de
  Ajustes, que ahora gobierna iconos, bordes animados y fondo) y la
  página de Ajustes al cambiarla. Todo widget animado la consulta
  antes de moverse; apagada = todo estático, sin temporizadores.
- UN reloj compartido (`RELOJ`): un solo QTimer de 50 ms para toda
  la app en vez de un temporizador por widget. Los widgets se
  suscriben al mostrarse y se desuscriben al ocultarse; sin
  suscriptores visibles el reloj se para (cero CPU en segundo
  plano o con la ventana en otra sección).
"""
from PySide6.QtCore import QObject, QTimer, Signal

_activas = True


def fijar_animaciones_activas(valor: bool) -> None:
    """Fija la puerta global (desde Ajustes) y para el reloj si se
    apaga: ningún widget sigue moviéndose."""
    global _activas
    _activas = bool(valor)
    if not _activas:
        RELOJ.detener()
    elif not _pausado and not _ahorro_bateria:
        RELOJ.reanudar()


def animaciones_activas() -> bool:
    # v1.0.16 (frente 6): el ahorro por batería también cierra
    # la puerta — los widgets consultan ESTA función y el reloj
    # compartido se para, así todo queda quieto sin tocar el
    # interruptor del usuario.
    return _activas and not _ahorro_bateria


# --- Ahorro por batería (v1.0.16, frente 6) --------------------------------
# La Toughbook vive mucho sin cargador: si el equipo va con
# batería, las animaciones se PAUSAN solas (iconos, radar,
# globo, bordes) y vuelven al enchufar. El interruptor manual
# de Ajustes MANDA sobre esto: si el usuario las apagó, el
# ahorro no las enciende jamás; si las dejó encendidas, el
# ahorro solo las pausa mientras dure la batería.
_ahorro_bateria = False


def fijar_ahorro_bateria(activo: bool) -> None:
    global _ahorro_bateria
    _ahorro_bateria = bool(activo)
    if _ahorro_bateria:
        RELOJ.detener()
    elif _activas and not _pausado:
        RELOJ.reanudar()


def ahorro_bateria_activo() -> bool:
    return _ahorro_bateria


_pausado = False


def fijar_pausa(pausado: bool) -> None:
    """Pausa global del reloj (v1.0.14): la ventana la activa al
    ocultarse/minimizarse y la quita al mostrarse — con la app
    en la bandeja o minimizada, NINGUNA animación consume CPU.
    No toca la puerta de Ajustes: al volver, todo sigue como
    estaba."""
    global _pausado
    _pausado = bool(pausado)
    if _pausado:
        RELOJ.detener()
    else:
        RELOJ.reanudar()


def en_pausa() -> bool:
    return _pausado


class _RelojAnimacion(QObject):
    """Reloj único de animación: emite `tic(segundos)` a 20 fps."""

    tic = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self._t = 0.0
        self._suscriptores = 0
        self._temporizador = QTimer(self)
        self._temporizador.setInterval(50)
        self._temporizador.timeout.connect(self._avanzar)

    def _avanzar(self) -> None:
        self._t += 0.05
        self.tic.emit(self._t)

    def suscribir(self) -> None:
        self._suscriptores += 1
        if animaciones_activas() and not _pausado \
                and not self._temporizador.isActive():
            self._temporizador.start()

    def reanudar(self) -> None:
        """Relanza el temporizador si hay suscriptores y la
        puerta de Ajustes está abierta."""
        if self._suscriptores > 0 and animaciones_activas() \
                and not self._temporizador.isActive():
            self._temporizador.start()

    def desuscribir(self) -> None:
        self._suscriptores = max(0, self._suscriptores - 1)
        if self._suscriptores == 0:
            self._temporizador.stop()

    def detener(self) -> None:
        self._temporizador.stop()

    def fase(self) -> float:
        return self._t

    def en_marcha(self) -> bool:
        return self._temporizador.isActive()


RELOJ = _RelojAnimacion()
