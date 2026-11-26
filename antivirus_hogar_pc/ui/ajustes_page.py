"""Página de Ajustes (integrador): canal de actualización y preferencias.

No es un módulo de carril: vive en la carcasa porque toca el contexto
compartido. La lógica de actualización es core.updater.
"""
from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit

from .. import config
from ..contracts import ContextoModulo
from ..core.i18n import t
from .paginas_base import boton_principal, etiqueta, pagina_base, tarjeta


def crear_pagina_ajustes(ctx: ContextoModulo):
    servicios = ctx.servicios
    ajustes = servicios.ajustes if servicios else None
    pagina, layout = pagina_base(t("Ajustes"), t("La aplicación y su canal de actualización."))

    tarjeta_app, lay = tarjeta(t("Aplicación"))
    lay.addWidget(etiqueta(t("Antivirus Hogar PC · versión {version}", version=config.VERSION)))
    lay.addWidget(etiqueta(t(
        "Compañero de Microsoft Defender: la protección en tiempo real la hace "
        "Defender; esta app escanea, limpia e informa. Sin firma comercial: "
        "Windows mostrará el aviso de SmartScreen al instalar."), suave=True))
    layout.addWidget(tarjeta_app)

    # --- Arranque con Windows + rutina automática (v1.0.5) -------------------
    tarjeta_arranque, lay_ar = tarjeta(t("Arranque y rutina automática"))
    check_arranque = QCheckBox(t(
        "Arrancar con Windows (la app abre minimizada, en segundo plano)"))
    check_rutina = QCheckBox(t(
        "Al arrancar, ejecutar la rutina automática: escaneo rápido, "
        "revisión de drivers, limpieza segura y revisión de inicio"))
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
    lay_ar.addWidget(etiqueta(t(
        "La rutina solo revisa y limpia lo seguro (temporales, cachés "
        "y papelera): ante una amenaza NO actúa sola — deja el "
        "resultado en Inicio y en el registro de actividad para que "
        "decidas tú."), suave=True))
    layout.addWidget(tarjeta_arranque)

    # --- Reconexión automática de la VPN (v1.0.16, frente 2) ------------------
    tarjeta_vpn, lay_vpn = tarjeta(t("Red y VPN"))
    check_reconectar = QCheckBox(t(
        "Reconectar la VPN automáticamente si la conexión se cae"))
    if ajustes is not None:
        check_reconectar.setChecked(
            bool(getattr(ajustes, "vpn_reconectar_auto", True)))

        def _reconectar(marcado: bool) -> None:
            ajustes.vpn_reconectar_auto = bool(marcado)
            ajustes.guardar()

        check_reconectar.toggled.connect(_reconectar)
    lay_vpn.addWidget(check_reconectar)
    lay_vpn.addWidget(etiqueta(t(
        "Si un túnel establecido se cae solo, la app reconecta: "
        "primero al mismo servidor y luego al siguiente "
        "recomendado, con avisos en la bandeja. Si desconectas "
        "a mano, no reconecta nunca."), suave=True))
    layout.addWidget(tarjeta_vpn)

    tarjeta_canal, lay_c = tarjeta(t("Canal de actualización (Google Drive)"))
    campo_url = QLineEdit(ajustes.url_actualizacion if ajustes else "")
    campo_url.setPlaceholderText(t("URL del version-pc.json del canal"))
    lay_c.addWidget(campo_url)
    lay_c.addWidget(etiqueta(t(
        "Al buscar actualizaciones se compara la versión y, si hay una nueva, "
        "se enseña «Qué trae esta actualización» antes de descargar nada. "
        "El instalador se verifica por su huella SHA-256."), suave=True))
    boton_guardar = boton_principal(t("Guardar canal"), "primario")
    if ajustes is not None:
        def _guardar() -> None:
            ajustes.url_actualizacion = campo_url.text().strip()
            ajustes.guardar()

        boton_guardar.clicked.connect(_guardar)
    lay_c.addWidget(boton_guardar)
    layout.addWidget(tarjeta_canal)

    tarjeta_vista, lay_v = tarjeta(t("Vista"))
    check_letra = QCheckBox(t("Letra grande (para leer más cómodo)"))
    if ajustes is not None:
        check_letra.setChecked(bool(ajustes.letra_grande))

        def _letra(marcado: bool) -> None:
            ajustes.letra_grande = bool(marcado)
            ajustes.guardar()

        check_letra.toggled.connect(_letra)
    lay_v.addWidget(check_letra)
    check_radar = QCheckBox(t(
        "Animaciones de la interfaz (iconos, bordes con movimiento "
        "y fondo del Panel)"))
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
    lay_v.addWidget(etiqueta(t(
        "Los iconos del panel se mueven suave, los bordes de las "
        "tarjetas tienen un recorrido de color y el radar de Inicio "
        "se anima; todo cuelga de un solo temporizador compartido y "
        "gasta muy poco. Si Windows tiene activado «reducir "
        "animaciones», la app lo respeta aunque esto esté marcado. "
        "Apagarlo deja toda la interfaz quieta al momento."), suave=True))
    # Ahorro por batería (v1.0.16, frente 6): indicador del
    # estado EN ESTE MOMENTO y la explicación de la regla.
    from .animacion import ahorro_bateria_activo

    if ahorro_bateria_activo():
        lay_v.addWidget(etiqueta(t(
            "Ahorro por batería: ACTIVO ahora — las animaciones "
            "están en pausa hasta enchufar el cargador.")))
    lay_v.addWidget(etiqueta(t(
        "Ahorro por batería: si el equipo va sin cargador, las "
        "animaciones se pausan solas y vuelven al enchufarlo. "
        "Tu interruptor de animaciones manda sobre esto."),
        suave=True))
    # Escala de la interfaz (v1.0.16, frente 7).
    lay_v.addWidget(etiqueta(t("Tamaño de la interfaz")))
    combo_escala = QComboBox()
    combo_escala.addItem(t("Normal"), "normal")
    combo_escala.addItem(t("Grande"), "grande")
    if ajustes is not None:
        indice = combo_escala.findData(
            getattr(ajustes, "escala_interfaz", "normal"))
        combo_escala.setCurrentIndex(indice if indice >= 0 else 0)

        def _escala(_i: int) -> None:
            ajustes.escala_interfaz = combo_escala.currentData()
            ajustes.guardar()
            from PySide6.QtWidgets import QApplication

            from .escala import aplicar_escala

            app = QApplication.instance()
            if app is not None:
                aplicar_escala(app, ajustes)

        combo_escala.currentIndexChanged.connect(_escala)
    lay_v.addWidget(combo_escala)
    lay_v.addWidget(etiqueta(t(
        "La letra se aplica al momento; el resto de tamaños (la "
        "barra lateral y las páginas ya abiertas) termina de "
        "ajustarse al reabrir la ventana."), suave=True))
    layout.addWidget(tarjeta_vista)

    # --- Protección avanzada (v1.0.21) ---------------------------------------
    tarjeta_av, lay_av = tarjeta(t("Protección avanzada"))
    lay_av.addWidget(etiqueta(t(
        "Clave de VirusTotal (opcional): con TU clave, el análisis de un "
        "archivo puede consultar su huella en VirusTotal. Solo viaja la "
        "huella (SHA-256): la app jamás sube archivos. Sin clave, la "
        "consulta queda sin configurar y no se usa."), suave=True))
    campo_vt = QLineEdit(ajustes.clave_virustotal if ajustes else "")
    campo_vt.setEchoMode(QLineEdit.EchoMode.Password)
    lay_av.addWidget(campo_vt)
    boton_vt = boton_principal(t("Guardar clave de VirusTotal"), "primario")

    def _guardar_vt() -> None:
        if ajustes is not None:
            ajustes.clave_virustotal = campo_vt.text().strip()
            ajustes.guardar()

    boton_vt.clicked.connect(_guardar_vt)
    lay_av.addWidget(boton_vt)
    lay_av.addWidget(etiqueta(t(
        "Anti-ransomware propio: siembra archivos señuelo en las carpetas "
        "protegidas y vigila ráfagas de cambios con pinta de cifrado. "
        "Detecta y avisa; no promete interceptarlo todo, y contener un "
        "proceso solo ocurre si TÚ lo ordenas en el aviso."), suave=True))
    combo_ransom = QComboBox()
    combo_ransom.addItem(t("Solo avisar (recomendado)"), "avisar")
    combo_ransom.addItem(t("Apagado"), "apagado")
    if ajustes is not None:
        indice = combo_ransom.findData(ajustes.antiransomware_modo)
        combo_ransom.setCurrentIndex(max(0, indice))

    def _ransom() -> None:
        if ajustes is not None:
            ajustes.antiransomware_modo = combo_ransom.currentData()
            ajustes.guardar()

    combo_ransom.currentIndexChanged.connect(_ransom)
    lay_av.addWidget(combo_ransom)
    layout.addWidget(tarjeta_av)
    layout.addStretch(1)
    return pagina
