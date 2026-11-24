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


def animaciones_activas() -> bool:
    return _activas


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
        if animaciones_activas() and not self._temporizador.isActive():
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
