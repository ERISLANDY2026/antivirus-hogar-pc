"""Estado de mantenimiento persistente (v1.0.16, frente 3).

La tarjeta «Pendientes» de Inicio solo puede enseñar datos
REALES, y dos de los suyos no vivían en ningún sitio entre
arranques: cuándo se revisaron los drivers por última vez (y
cuántos quedaron desactualizados) y cuándo se optimizó un
volumen por última vez. Este módulo es su casa: dos archivos
pequeños en la carpeta de datos, escritos por los servicios al
terminar su trabajo y leídos por el Panel.

Sin Qt y sin Windows: las rutas se inyectan (la suite lo prueba
en Linux) y leer algo corrupto devuelve None — «sin dato», que
la tarjeta interpreta como «este pendiente no se enseña».
"""
import json
import os
import time

ARCHIVO_DRIVERS = "revision_drivers.json"
ARCHIVO_OPTIMIZACION = "ultima_optimizacion.json"


def _ruta(archivo: str) -> str:
    from .. import config

    return os.path.join(config.carpeta_datos(), archivo)


def _leer(ruta: str) -> dict | None:
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else None
    except (OSError, ValueError):
        return None


def _guardar(ruta: str, datos: dict) -> None:
    try:
        os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=1)
    except OSError:
        pass  # anotar el mantenimiento nunca rompe la operación


def guardar_revision_drivers(desactualizados: int, total: int,
                             confirmado: bool = True,
                             ruta: str | None = None,
                             ahora: float | None = None) -> None:
    """Anota el resultado de una revisión de drivers COMPLETA
    (con la comparación hecha). `confirmado` es False cuando la
    consulta a Windows Update falló: entonces el conteo no es un
    dato real y la tarjeta no debe enseñar «al día» con él."""
    _guardar(ruta or _ruta(ARCHIVO_DRIVERS), {
        "cuando": float(ahora if ahora is not None else time.time()),
        "desactualizados": int(desactualizados),
        "total": int(total),
        "confirmado": bool(confirmado),
    })


def leer_revision_drivers(ruta: str | None = None) -> dict | None:
    return _leer(ruta or _ruta(ARCHIVO_DRIVERS))


def guardar_optimizacion(letra: str, ok: bool,
                         ruta: str | None = None,
                         ahora: float | None = None) -> None:
    """Anota una optimización de volumen TERMINADA (la que manda
    para «hace X días» es la última que salió bien)."""
    _guardar(ruta or _ruta(ARCHIVO_OPTIMIZACION), {
        "cuando": float(ahora if ahora is not None else time.time()),
        "letra": str(letra or ""),
        "ok": bool(ok),
    })


def leer_ultima_optimizacion(ruta: str | None = None) -> dict | None:
    return _leer(ruta or _ruta(ARCHIVO_OPTIMIZACION))
