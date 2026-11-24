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
    servicios = ServiciosApp()
    if servicios.ajustes.letra_grande:
        fuente = app.font()
        fuente.setPointSizeF(fuente.pointSizeF() * 1.125)
        app.setFont(fuente)
    # Arranque con Windows (v1.0.5): si el interruptor está activado,
    # la entrada del registro se asegura en cada apertura (se
    # autorrepara si algo la borró); si está apagado no se toca.
    if servicios.ajustes.arranque_windows:
        try:
            from ..winapi import arranque as arranque_win

            arranque_win.fijar_arranque_windows(True)
        except Exception:
            pass  # best-effort: la app abre igual
    ventana = VentanaPrincipal(servicios)
    if "--inicio-automatico" in argv:
        # Arranque de Windows: minimizada, en segundo plano, y con la
        # rutina automática si su interruptor está activado.
        ventana.showMinimized()
        if servicios.ajustes.rutina_automatica:
            from .rutina_auto import lanzar_rutina_en_fondo

            QTimer.singleShot(
                2500,
                lambda: lanzar_rutina_en_fondo(
                    servicios,
                    al_terminar=lambda _r: ventana.refrescar_rutina()))
    else:
        ventana.show()
    return app.exec()
