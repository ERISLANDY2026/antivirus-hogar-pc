"""Punto de entrada de la interfaz.

Uso:
  AntivirusHogarPC.exe                  → abre la ventana
  AntivirusHogarPC.exe --escaneo-programado
      → escaneo silencioso del Programador de tareas: escanea las carpetas
        de riesgo, guarda el informe y SOLO notifica si hay hallazgos.
"""
import json
import os
import sys
import time


def _escaneo_programado() -> int:
    from .. import config
    from ..core.scancache import CacheEscaneo
    from ..core.scanner import escanear
    from ..core.signatures import BaseFirmas
    from .services import ServiciosApp

    base = BaseFirmas()
    base.cargar_semilla(config.carpeta_activos())
    base.cargar_archivo(os.path.join(config.carpeta_datos(), "firmas_extra.txt"))
    cache = CacheEscaneo(config.ruta_bd_cache())
    raices = ServiciosApp.carpetas_riesgo()
    descargas = ServiciosApp.carpeta_descargas()
    resultado = escanear(
        raices, base, cache=cache, solo_ejecutables=True,
        forzar_rehash_en=[descargas] if descargas else [],
    )
    cache.cerrar()
    informe = {
        "fecha": time.time(),
        "revisados": resultado.archivos_revisados,
        "desde_cache": resultado.archivos_desde_cache,
        "errores": resultado.errores,
        "hallazgos": [
            {"ruta": h.ruta, "etiqueta": h.etiqueta, "sha256": h.sha256}
            for h in resultado.hallazgos
        ],
    }
    ruta_informe = os.path.join(
        config.ruta_informes(), time.strftime("escaneo-programado-%Y%m%d-%H%M%S.json"))
    with open(ruta_informe, "w", encoding="utf-8") as f:
        json.dump(informe, f, ensure_ascii=False, indent=1)
    if resultado.hallazgos:
        from ..winapi.tasks import notificar_windows

        notificar_windows(
            "Antivirus Hogar PC — escaneo semanal",
            f"Se encontraron {len(resultado.hallazgos)} archivo(s) sospechoso(s). "
            "Abre la app para decidir qué hacer.",
        )
    return 0


def _tareas_programadas_reales() -> dict:
    """Las tareas que el Programador de tareas puede lanzar con
    --tarea-programada <id> (v1.0.5): corren sin ventana, en segundo
    plano, y dejan su resultado en programadas/<id>.json y en el
    registro de actividad."""
    from .. import config
    from ..core import threats_update, updater
    from ..core.scanner import escanear
    from .rutina_auto import tareas_reales
    from .services import ServiciosApp

    servicios = ServiciosApp()
    base = tareas_reales(servicios)

    def escaneo_completo() -> str:
        import string

        raices = [f"{letra}:\\" for letra in string.ascii_uppercase
                  if os.path.isdir(f"{letra}:\\")]
        resultado = escanear(raices, servicios.base_firmas,
                             cache=servicios.cache, solo_ejecutables=True)
        servicios.registrar_escaneo(resultado)
        texto = (f"Escaneo completo: {resultado.archivos_revisados} "
                 f"archivos revisados, {len(resultado.hallazgos)} "
                 "hallazgo(s) — sin tocar nada: decide tú.")
        if resultado.hallazgos:
            from ..winapi.tasks import notificar_windows

            notificar_windows(
                "Antivirus Hogar PC — escaneo programado",
                f"El escaneo completo encontró "
                f"{len(resultado.hallazgos)} archivo(s) sospechoso(s). "
                "Abre la app para decidir qué hacer.")
        return texto

    def firmas() -> str:
        resultado = threats_update.actualizar_firmas_multifuente(
            servicios.ajustes.auth_key_abusech)
        if not resultado.ok:
            raise RuntimeError(
                "Ninguna fuente pudo aportar firmas nuevas. "
                + resultado.resumen())
        n_hashes = n_dominios = 0
        if resultado.hashes:
            from ..core.threats_update import escribir_archivo_firmas

            ruta_extra = os.path.join(
                config.carpeta_datos(), "firmas_extra.txt")
            n_hashes = escribir_archivo_firmas(ruta_extra, resultado.hashes)
        if resultado.dominios:
            ruta_dom = os.path.join(
                config.carpeta_datos(), "dominios_extra.txt")
            n_dominios = threats_update.escribir_archivo_dominios(
                ruta_dom, resultado.dominios)
        return (f"Firmas actualizadas: {n_hashes} huellas y "
                f"{n_dominios} dominios nuevos. {resultado.resumen()}")

    def actualizacion_app() -> str:
        info = updater.comprobar_actualizacion(
            servicios.ajustes.url_actualizacion, config.VERSION)
        if info is None:
            return "La app ya está en la última versión."
        carpeta = os.path.join(config.carpeta_datos(), "actualizaciones")
        os.makedirs(carpeta, exist_ok=True)
        destino = os.path.join(carpeta, updater.nombre_instalador(
            info.url_descarga))
        updater.descargar_archivo(info.url_descarga, destino)
        if not updater.verificar_sha256(destino, info.sha256):
            raise RuntimeError(
                "La descarga no coincide con el SHA-256 del canal; "
                "no se deja nada instalado.")
        return (f"Versión {info.version} descargada y verificada "
                "(SHA-256 correcto). Ábre la app para instalarla "
                "cuando quieras.")

    return {
        "escaneo-rapido": base["escaneo"],
        "escaneo-completo": escaneo_completo,
        "drivers": base["drivers"],
        "limpieza": base["limpieza"],
        "firmas": firmas,
        "actualizacion-app": actualizacion_app,
    }


def _tarea_programada(id_: str) -> int:
    """Ejecuta UNA tarea programada (sin ventana) y guarda su resultado."""
    from .. import config
    from ..core.actividad import RegistroActividad
    from ..core.programaciones import ejecutar_tarea_programada

    registro = RegistroActividad(config.ruta_actividad())

    def escribir(id2: str, resultado: dict) -> None:
        carpeta = os.path.join(config.carpeta_datos(), "programadas")
        os.makedirs(carpeta, exist_ok=True)
        with open(os.path.join(carpeta, f"{id2}.json"), "w",
                  encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=1)

    resultado = ejecutar_tarea_programada(
        id_, _tareas_programadas_reales(), registro.registrar, escribir)
    return 0 if resultado.get("ok") else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "--escaneo-programado" in argv:
        return _escaneo_programado()
    if "--tarea-programada" in argv:
        indice = argv.index("--tarea-programada")
        if indice + 1 < len(argv):
            return _tarea_programada(argv[indice + 1])
        return 2

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from . import theme
    from .main_window import VentanaPrincipal
    from .services import ServiciosApp

    app = QApplication(argv)
    app.setApplicationName("Antivirus Hogar PC")
    app.setStyleSheet(theme.QSS)
    # Icono de la VENTANA y de la barra de tareas (v1.0.6, nota del
    # usuario): se fija en tiempo de ejecución desde el .ico del
    # espartano incluido en la app. Sin esto, Windows enseña el
    # icono que tenga en su caché para la ruta del ejecutable o el
    # del acceso directo viejo — en su PC seguía saliendo el icono
    # anterior aunque el .exe ya llevaba el espartano incrustado.
    try:
        from PySide6.QtGui import QIcon

        from .. import config as _config

        _ruta_icono = os.path.join(_config.carpeta_activos(), "icono_app.ico")
        if os.path.isfile(_ruta_icono):
            app.setWindowIcon(QIcon(_ruta_icono))
    except Exception:
        pass  # el icono nunca debe impedir abrir la app
    servicios = ServiciosApp()
    # Idioma guardado (v1.0.14): se fija antes de crear la
    # ventana para que todo nazca en el idioma elegido.
    from ..core import i18n as _i18n

    _i18n.fijar_idioma(getattr(servicios.ajustes, "idioma", "es"))
    # Escala de la interfaz (v1.0.16, frente 7): «Grande»
    # (×1.22) o el «letra grande» de siempre (×1.125); el
    # factor efectivo lo decide ui.escala (el mayor, no la suma).
    from .escala import aplicar_escala

    aplicar_escala(app, servicios.ajustes)
    # Arranque con Windows (v1.0.5): si el interruptor está activado,
    # la entrada del registro se asegura en cada apertura (se
    # autorrepara si algo la borró); si está apagado no se toca.
    if servicios.ajustes.arranque_windows:
        try:
            from ..winapi import arranque as arranque_win

            arranque_win.fijar_arranque_windows(True)
        except Exception:
            pass  # best-effort: la app abre igual
    # Autorreparación del hosts (v1.0.6): si el bloque de Protección
    # quedó dañado o una retirada programada para el reinicio sigue
    # pendiente, se deja limpio al abrir y queda anotado en el
    # registro de actividad. Best-effort: nunca impide abrir la app.
    try:
        from ..core import seguridad as _seguridad

        _seguridad.autorreparar_al_inicio(servicios.registrar_actividad)
    except Exception:
        pass
    # Protección anti-falso-positivo (v1.0.7, punto 4): al abrir, la
    # app comprueba que la exclusión de Defender pedida por el
    # instalador quedó aplicada y que sus propios archivos siguen
    # íntegros; todo queda en el registro de actividad y, si la
    # exclusión no se pudo poner, se avisa con el paso manual.
    _aviso_defender = None
    try:
        from ..winapi import defender as _defender

        _salud = _defender.comprobar_al_arranque(
            servicios.registrar_actividad)
        _aviso_defender = _salud.get("aviso")
    except Exception:
        pass
    ventana = VentanaPrincipal(servicios)
    # Bandeja del sistema (v1.0.7, punto 5): la app vive junto al
    # reloj también con --inicio-automatico; cerrar la ventana la
    # oculta a la bandeja y salir es «Salir» de su menú.
    bandeja = None
    try:
        from PySide6.QtGui import QIcon

        from .bandeja import Bandeja

        def _abrir_ventana():
            ventana.showNormal()
            ventana.raise_()
            ventana.activateWindow()

        def _escaneo_desde_bandeja():
            _abrir_ventana()
            ventana.ir_a("escaner")
            pagina = ventana._paginas.get("escaner")
            rapido = getattr(pagina, "escaneo_rapido", None)
            if callable(rapido):
                rapido()

        def _salir_de_verdad():
            if bandeja is not None:
                bandeja.ocultar()
            ventana.salir()

        bandeja = Bandeja(QIcon(_ruta_icono), _abrir_ventana,
                          _escaneo_desde_bandeja, _salir_de_verdad,
                          padre=ventana)
        ventana.fijar_bandeja(bandeja)
        # v1.0.14: al cambiar el idioma en el panel, el menú de
        # la bandeja se retraduce en el acto.
        ventana.al_cambiar_idioma = bandeja.retraducir

        def _aviso_escaneo(info):
            if info.get("hallazgos", 0) > 0:
                from ..core.i18n import t as _t

                bandeja.avisar(
                    "Antivirus Hogar PC",
                    _t("Un escaneo terminó con {n} "
                       "hallazgo(s). Abre la app y decide qué hacer: "
                       "la app nunca actúa sola.",
                       n=info['hallazgos']))

        servicios.al_registrar_escaneo = _aviso_escaneo
    except Exception:
        bandeja = None  # sin bandeja la app funciona igual que antes
    # Vigilante de reconexión de la VPN (v1.0.16, frente 2): si
    # un túnel establecido se cae solo, reconecta (mismo
    # servidor, luego el failover) y avisa por la bandeja; la
    # desconexión manual no se reconecta jamás. El interruptor
    # vive en Ajustes y se lee en cada ciclo.
    try:
        from ..modules.net import servicios_red as _servicios_red

        def _avisar_vigilante(evento, objetivo):
            if bandeja is None:
                return
            from ..core.i18n import t

            host = str((objetivo or {}).get("hostname") or "")
            if evento == "caida":
                bandeja.avisar(
                    "Antivirus Hogar PC",
                    t("La conexión VPN se cayó. "
                      "Reconectando automáticamente…"))
            elif evento == "reconectada":
                bandeja.avisar(
                    "Antivirus Hogar PC",
                    t("La VPN volvió a conectar sola a {host}.",
                      host=host))
            elif evento == "agotado":
                bandeja.avisar(
                    "Antivirus Hogar PC",
                    t("No se pudo reconectar la VPN tras varios "
                      "intentos. Abre Red y VPN para conectar "
                      "a mano."))

        _servicios_red.iniciar_vigilante_vpn(
            obtener_ajustes=lambda: servicios.ajustes,
            avisar=_avisar_vigilante)
    except Exception:
        pass  # sin vigilante la app funciona igual que antes
    # Ahorro por batería (v1.0.16, frente 6): sondeo ligero
    # cada 30 s de GetSystemPowerStatus; sin cargador, las
    # animaciones se pausan solas (ui.animacion) y vuelven al
    # enchufar. En un sobremesa (sin batería) no se toca nada.
    def _vigilar_bateria():
        try:
            from ..winapi import system_info as _sistema_info
            from .animacion import fijar_ahorro_bateria

            energia = _sistema_info.estado_bateria()
            if energia.get("sin_bateria"):
                fijar_ahorro_bateria(False)
            elif energia.get("con_cargador") is False:
                fijar_ahorro_bateria(True)
            elif energia.get("con_cargador") is True:
                fijar_ahorro_bateria(False)
        except Exception:
            pass  # sin lectura de energía, las animaciones siguen

    temporizador_bateria = QTimer(ventana)
    temporizador_bateria.timeout.connect(_vigilar_bateria)
    temporizador_bateria.start(30000)
    _vigilar_bateria()
    if _aviso_defender:
        def _mostrar_aviso_defender():
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(ventana, "Antivirus Hogar PC",
                                _aviso_defender)

        QTimer.singleShot(1500, _mostrar_aviso_defender)
    # Auto-actualizador de OpenVPN (v1.0.10): chequeo en segundo
    # plano si toca (cada 3 días) y aplicación SEGURA de lo
    # pendiente si no hay túnel (verificada antes y después, con
    # reversión si algo queda mal); nunca bloquea la interfaz.
    def _chequeo_openvpn():
        import threading

        def _trabajo():
            from ..winapi import openvpn_update

            openvpn_update.chequear_y_aplicar(
                servicios.registrar_actividad,
                avisar=bandeja.avisar if bandeja is not None else None)

        threading.Thread(target=_trabajo, daemon=True).start()

    QTimer.singleShot(6000, _chequeo_openvpn)
    # Refresco de fuentes VPN + autoanálisis (v1.0.14): gemelo
    # del chequeo de OpenVPN — al abrir la app (el autoarranque
    # en bandeja al iniciar Windows es el mismo camino), en un
    # hilo de fondo que nunca bloquea el arranque: si toca por
    # cadencia (~30 min) refresca la lista unificada (VPN Gate +
    # VPNBook) y guarda la caché buena; después sondea de verdad
    # unos pocos candidatos con su presupuesto. Las sondas se
    # difieren solas si hay un túnel o un intento en curso.
    def _refresco_fuentes_vpn():
        import threading

        def _trabajo():
            from ..modules.net import servicios_red

            servicios_red.refresco_y_sondas_en_fondo(
                servicios.registrar_actividad)

        threading.Thread(target=_trabajo, daemon=True).start()

    QTimer.singleShot(10000, _refresco_fuentes_vpn)
    if "--inicio-automatico" in argv:
        # Arranque de Windows: minimizada, en segundo plano, y con la
        # rutina automática si su interruptor está activado.
        ventana.showMinimized()
        if servicios.ajustes.rutina_automatica:
            from .rutina_auto import lanzar_rutina_en_fondo

            def _rutina_terminada(_r):
                ventana.refrescar_rutina()
                if bandeja is not None:
                    from ..core.i18n import t as _t

                    bandeja.avisar(
                        "Antivirus Hogar PC",
                        _t("La rutina automática de arranque terminó. "
                           "La app sigue en la bandeja."))

            QTimer.singleShot(
                2500,
                lambda: lanzar_rutina_en_fondo(
                    servicios, al_terminar=_rutina_terminada))
    else:
        ventana.show()
    return app.exec()
