"""Rutina automática al arrancar con Windows (v1.0.5).

Cuando la app arranca con --inicio-automatico y el interruptor
«rutina automática» está activado, corre EN SEGUNDO PLANO (un hilo,
sin bloquear la ventana minimizada) el mantenimiento que no necesita
al usuario:

- Escaneo rápido de las carpetas de riesgo.
- Revisión de drivers (la cadena de confirmación de la v1.0.5).
- Limpieza SEGURA: temporales/cachés y papelera — solo lo que la app
  ya limpia a mano; nada más se borra.
- Revisión de los programas que arrancan con Windows.

Límites de siempre: ante una amenaza NO se actúa (quedan los
hallazgos anotados; decide el usuario). Cada tarea deja su resultado
en el registro de actividad y el resumen completo se guarda en
rutina_auto.json, que la pestaña Inicio enseña («qué se hizo al
arrancar y cuándo»).
"""
import json
import os
import threading
import time
from typing import Callable

from .. import config

ARCHIVO_RESUMEN = "rutina_auto.json"


def ruta_resumen() -> str:
    return os.path.join(config.carpeta_datos(), ARCHIVO_RESUMEN)


def tareas_reales(servicios) -> dict[str, Callable[[], str]]:
    """Las tareas de verdad, sobre los servicios de la app. Cada una
    devuelve su resumen en español; si falla, la excepción la recoge
    ejecutar_rutina y la rutina sigue con la siguiente."""
    from ..core.scanner import escanear
    from ..modules.system import servicios_sistema as svc_sys

    def escaneo() -> str:
        descargas = servicios.carpeta_descargas()
        resultado = escanear(
            servicios.carpetas_riesgo(), servicios.base_firmas,
            cache=servicios.cache, solo_ejecutables=True,
            forzar_rehash_en=[descargas] if descargas else [])
        servicios.registrar_escaneo(resultado)
        texto = (f"Escaneo rápido: {resultado.archivos_revisados} archivos "
                 f"revisados, {len(resultado.hallazgos)} hallazgo(s)")
        if resultado.hallazgos:
            texto += " — sin tocar nada: decide tú qué hacer"
            try:
                from ..winapi.tasks import notificar_windows

                notificar_windows(
                    "Antivirus Hogar PC — rutina de arranque",
                    f"El escaneo rápido encontró "
                    f"{len(resultado.hallazgos)} archivo(s) sospechoso(s). "
                    "Abre la app para decidir qué hacer.")
            except Exception:
                pass  # la notificación nunca rompe la rutina
        return texto

    def drivers() -> str:
        paso1 = svc_sys.escanear_drivers_paso1()
        if not paso1.ok or not isinstance(paso1.datos, dict):
            raise RuntimeError(paso1.mensaje or "sin datos de drivers")
        paso2 = svc_sys.escanear_drivers_paso2_buscar(
            paso1.datos["instalados"])
        return f"Drivers: {paso2.mensaje}"

    def limpieza() -> str:
        partes = []
        res = svc_sys.limpiar_con_progreso(None)
        partes.append(res.mensaje)
        papelera = svc_sys.vaciar_papelera()
        if papelera.ok:
            partes.append(papelera.mensaje)
        return "Limpieza segura: " + " · ".join(partes)

    def inicio() -> str:
        res = svc_sys.elementos_arranque()
        if not res.ok:
            raise RuntimeError(res.mensaje or "sin datos de arranque")
        return f"Revisión de inicio: {res.mensaje}"

    return {"escaneo": escaneo, "drivers": drivers,
            "limpieza": limpieza, "inicio": inicio}


def ejecutar_rutina(tareas: dict[str, Callable[[], str]],
                    registrar: Callable[[str, str], None],
                    escribir_resumen: Callable[[dict], None],
                    ahora: Callable[[], float] = time.time) -> dict:
    """Corre las tareas EN ORDEN, registra cada resultado y guarda el
    resumen. Una tarea que falla no detiene a las demás."""
    resultados: dict[str, dict] = {}
    for nombre, funcion in tareas.items():
        try:
            resumen = funcion()
            resultados[nombre] = {"ok": True, "resumen": str(resumen)}
        except Exception as exc:
            resultados[nombre] = {
                "ok": False,
                "resumen": f"No se pudo completar: {exc}"}
        try:
            registrar("rutina-automatica",
                      f"{nombre}: {resultados[nombre]['resumen']}")
        except Exception:
            pass  # el registro nunca detiene la rutina
    resumen_total = {"cuando": float(ahora()), "resultados": resultados}
    try:
        escribir_resumen(resumen_total)
    except Exception:
        pass
    return resumen_total


def _escribir_resumen_archivo(resumen: dict) -> None:
    with open(ruta_resumen(), "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=1)


def leer_resumen_rutina() -> dict | None:
    """El resumen guardado de la última rutina (o None si nunca corrió)."""
    try:
        with open(ruta_resumen(), "r", encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else None
    except (OSError, ValueError):
        return None


def lanzar_rutina_en_fondo(servicios,
                           al_terminar: Callable[[dict], None] | None = None
                           ) -> threading.Thread:
    """Lanza la rutina en un hilo daemon (la ventana no espera)."""
    def _correr() -> None:
        resumen = ejecutar_rutina(
            tareas_reales(servicios), servicios.registrar_actividad,
            _escribir_resumen_archivo)
        if al_terminar is not None:
            try:
                al_terminar(resumen)
            except Exception:
                pass

    hilo = threading.Thread(target=_correr, name="rutina-automatica",
                            daemon=True)
    hilo.start()
    return hilo
