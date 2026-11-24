"""Página de Ajustes (integrador): canal de actualización y preferencias.

No es un módulo de carril: vive en la carcasa porque toca el contexto
compartido. La lógica de actualización es core.updater.
"""
from PySide6.QtWidgets import QCheckBox, QLineEdit

from .. import config
from ..contracts import ContextoModulo
from .paginas_base import boton_principal, etiqueta, pagina_base, tarjeta


def crear_pagina_ajustes(ctx: ContextoModulo):
    servicios = ctx.servicios
    ajustes = servicios.ajustes if servicios else None
    pagina, layout = pagina_base("Ajustes", "La aplicación y su canal de actualización.")

    tarjeta_app, lay = tarjeta("Aplicación")
    lay.addWidget(etiqueta(f"Antivirus Hogar PC · versión {config.VERSION}"))
    lay.addWidget(etiqueta(
        "Compañero de Microsoft Defender: la protección en tiempo real la hace "
        "Defender; esta app escanea, limpia e informa. Sin firma comercial: "
        "Windows mostrará el aviso de SmartScreen al instalar.", suave=True))
    layout.addWidget(tarjeta_app)

    # --- Arranque con Windows + rutina automática (v1.0.5) -------------------
    tarjeta_arranque, lay_ar = tarjeta("Arranque y rutina automática")
    check_arranque = QCheckBox(
        "Arrancar con Windows (la app abre minimizada, en segundo plano)")
    check_rutina = QCheckBox(
        "Al arrancar, ejecutar la rutina automática: escaneo rápido, "
        "revisión de drivers, limpieza segura y revisión de inicio")
    if ajustes is not None:
        check_arranque.setChecked(bool(ajustes.arranque_windows))
        check_rutina.setChecked(bool(ajustes.rutina_automatica))

        def _arranque(marcado: bool) -> None:
            ajustes.arranque_windows = bool(marcado)
            ajustes.guardar()
            # Aplicar ya: escribir o retirar la entrada del registro.
            from ..winapi import arranque as arranque_win
            from .services import seguro

            seguro(arranque_win.fijar_arranque_windows, bool(marcado))

        def _rutina(marcado: bool) -> None:
            ajustes.rutina_automatica = bool(marcado)
            ajustes.guardar()

        check_arranque.toggled.connect(_arranque)
        check_rutina.toggled.connect(_rutina)
    lay_ar.addWidget(check_arranque)
    lay_ar.addWidget(check_rutina)
    lay_ar.addWidget(etiqueta(
        "La rutina solo revisa y limpia lo seguro (temporales, cachés "
        "y papelera): ante una amenaza NO actúa sola — deja el "
        "resultado en Inicio y en el registro de actividad para que "
        "decidas tú.", suave=True))
    layout.addWidget(tarjeta_arranque)

    tarjeta_canal, lay_c = tarjeta("Canal de actualización (Google Drive)")
    campo_url = QLineEdit(ajustes.url_actualizacion if ajustes else "")
    campo_url.setPlaceholderText("URL del version-pc.json del canal")
    lay_c.addWidget(campo_url)
    lay_c.addWidget(etiqueta(
        "Al buscar actualizaciones se compara la versión y, si hay una nueva, "
        "se enseña «Qué trae esta actualización» antes de descargar nada. "
        "El instalador se verifica por su huella SHA-256.", suave=True))
    boton_guardar = boton_principal("Guardar canal", "primario")
    if ajustes is not None:
        def _guardar() -> None:
            ajustes.url_actualizacion = campo_url.text().strip()
            ajustes.guardar()

        boton_guardar.clicked.connect(_guardar)
    lay_c.addWidget(boton_guardar)
    layout.addWidget(tarjeta_canal)

    tarjeta_vista, lay_v = tarjeta("Vista")
    check_letra = QCheckBox("Letra grande (para leer más cómodo)")
    if ajustes is not None:
        check_letra.setChecked(bool(ajustes.letra_grande))

        def _letra(marcado: bool) -> None:
            ajustes.letra_grande = bool(marcado)
            ajustes.guardar()

        check_letra.toggled.connect(_letra)
    lay_v.addWidget(check_letra)
    check_radar = QCheckBox(
        "Animaciones de la interfaz (iconos, bordes con movimiento "
        "y fondo del Panel)")
    if ajustes is not None:
        check_radar.setChecked(bool(getattr(ajustes, "fondo_animado", True)))

        def _radar(marcado: bool) -> None:
            ajustes.fondo_animado = bool(marcado)
            ajustes.guardar()
            # v1.0.6: la puerta global se actualiza AL MOMENTO (el
            # reloj compartido se para o se reanuda sin reiniciar).
            from .animacion import fijar_animaciones_activas

            fijar_animaciones_activas(bool(marcado))

        check_radar.toggled.connect(_radar)
    lay_v.addWidget(check_radar)
    lay_v.addWidget(etiqueta(
        "Los iconos del panel se mueven suave, los bordes de las "
        "tarjetas tienen un recorrido de color y el radar de Inicio "
        "se anima; todo cuelga de un solo temporizador compartido y "
        "gasta muy poco. Si Windows tiene activado «reducir "
        "animaciones», la app lo respeta aunque esto esté marcado. "
        "Apagarlo deja toda la interfaz quieta al momento.", suave=True))
    layout.addWidget(tarjeta_vista)
    layout.addStretch(1)
    return pagina
