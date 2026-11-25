"""Icono en el área de notificación de Windows (v1.0.7, punto 5).

Al arrancar —también con --inicio-automatico— la app vive junto al
reloj: doble clic abre la ventana, el menú contextual trae «Abrir»,
«Escaneo rápido» y «Salir», y los avisos importantes (rutina de
arranque terminada, escaneo con hallazgos, actualización de
OpenVPN) llegan por globito SIN actuar nunca sola ante amenazas:
el globito avisa; decidir es del usuario.

Al cerrar la ventana, la app se queda en la bandeja en vez de
morir; salir de verdad es la opción «Salir» del menú.

Sin dependencias nuevas: QSystemTrayIcon es de Qt. La clase recibe
las acciones por callback para poder probarla con Qt simulado sin
levantar la ventana principal.
"""
from __future__ import annotations

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class Bandeja:
    """El icono de la bandeja y su menú (Abrir / Escaneo rápido / Salir)."""

    def __init__(self, icono: QIcon, al_abrir, al_escaneo_rapido,
                 al_salir, padre=None) -> None:
        self._al_abrir = al_abrir
        self._al_escaneo_rapido = al_escaneo_rapido
        self._al_salir = al_salir
        self.tray = QSystemTrayIcon(icono, padre)
        self.tray.setToolTip("Antivirus Hogar PC")

        self.menu = QMenu()
        self.accion_abrir = QAction("Abrir", self.menu)
        self.accion_abrir.triggered.connect(lambda _=False: self._al_abrir())
        self.accion_escaneo = QAction("Escaneo rápido", self.menu)
        self.accion_escaneo.triggered.connect(
            lambda _=False: self._al_escaneo_rapido())
        self.accion_salir = QAction("Salir", self.menu)
        self.accion_salir.triggered.connect(lambda _=False: self._al_salir())
        self.menu.addAction(self.accion_abrir)
        self.menu.addAction(self.accion_escaneo)
        self.menu.addSeparator()
        self.menu.addAction(self.accion_salir)
        self.tray.setContextMenu(self.menu)

        self.tray.activated.connect(self._activado)
        self.disponible = QSystemTrayIcon.isSystemTrayAvailable()
        if self.disponible:
            self.tray.show()

    def _activado(self, motivo) -> None:
        """Doble clic en el icono: abrir/restaurar la ventana."""
        if motivo == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._al_abrir()

    def avisar(self, titulo: str, mensaje: str) -> None:
        """Globito de la bandeja (best-effort: si no hay bandeja, nada)."""
        if self.disponible:
            self.tray.showMessage(titulo, mensaje,
                                  QSystemTrayIcon.MessageIcon.Information,
                                  6000)

    def ocultar(self) -> None:
        self.tray.hide()
