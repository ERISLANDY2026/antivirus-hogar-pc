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


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "--escaneo-programado" in argv:
        return _escaneo_programado()

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
    ventana = VentanaPrincipal(servicios)
    ventana.show()
    return app.exec()
