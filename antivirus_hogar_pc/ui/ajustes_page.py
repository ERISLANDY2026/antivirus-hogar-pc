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
    check_radar = QCheckBox("Fondo animado del Panel (radar)")
    if ajustes is not None:
        check_radar.setChecked(bool(getattr(ajustes, "fondo_animado", True)))

        def _radar(marcado: bool) -> None:
            ajustes.fondo_animado = bool(marcado)
            ajustes.guardar()

        check_radar.toggled.connect(_radar)
    lay_v.addWidget(check_radar)
    lay_v.addWidget(etiqueta(
        "El radar de la pestaña Inicio se mueve suave y gasta muy poco. "
        "Si Windows tiene activado «reducir animaciones», la app lo "
        "respeta aunque esto esté marcado. El cambio se ve al volver a "
        "abrir la aplicación.", suave=True))
    layout.addWidget(tarjeta_vista)
    layout.addStretch(1)
    return pagina
