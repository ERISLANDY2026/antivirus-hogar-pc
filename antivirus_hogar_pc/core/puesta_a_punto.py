"""«Puesta a punto» de un clic (v1.0.16, frente 1): la rutina
orquestada que encadena el mantenimiento que la app ya sabía
hacer por separado, en este orden:

    escaneo rápido → limpieza → optimizar volúmenes → drivers

con UNA sola barra de progreso global (la etapa actual va
nombrada), botón de cancelar que deja lo hecho hecho (y lo
dice) y UN veredicto final: qué se hizo, qué se encontró y
qué quedó pendiente.

Candados de la casa, heredados de las piezas:
- La revisión de drivers SOLO revisa y cuenta: instalar sigue
  siendo paso a paso con la confirmación del usuario en su
  pantalla (la rutina jamás instala un driver).
- Optimizar usa la vía de la 1.0.15 (defrag.exe con veredicto
  cierto; TRIM en SSD, nunca defrag clásico sobre SSD).
- Nada de registro de Windows; la limpieza es la segura de
  siempre (temporales, cachés y papelera).
- Ante una amenaza el escaneo NO actúa: anota los hallazgos
  y decide el usuario.

Lógica pura (sin Qt): los pasos se inyectan como funciones
(progreso_etapa, cancelado) -> {"ok", "resumen", …}; la UI
construye los de verdad (ui/puesta_a_punto.py) y la suite
prueba la orquestación con pasos falsos.
"""
import time
from typing import Callable

# (clave, título) en el orden de ejecución.
ETAPAS = (
    ("escaneo", "Escaneo rápido"),
    ("limpieza", "Limpieza segura"),
    ("optimizar", "Optimizar volúmenes"),
    ("drivers", "Revisión de drivers"),
)


def componer_veredicto(resultados: dict, cancelada: bool) -> str:
    """El veredicto ÚNICO de la rutina, desde los resultados."""
    hechos = [c for c, _ in ETAPAS
              if resultados.get(c, {}).get("ok")]
    fallos = [titulo for c, titulo in ETAPAS
              if c in resultados and not resultados[c].get("ok")
              and not resultados[c].get("omitida")]
    omitidas = [titulo for c, titulo in ETAPAS
                if resultados.get(c, {}).get("omitida")]
    if cancelada:
        texto = ("Puesta a punto CANCELADA: "
                 f"{len(hechos)} de {len(ETAPAS)} etapas completadas. "
                 "Lo ya hecho queda hecho.")
        if omitidas:
            texto += f" Quedó pendiente: {', '.join(omitidas)}."
        return texto
    if fallos:
        return ("Puesta a punto terminada CON AVISOS: "
                f"no se pudo completar: {', '.join(fallos)}. "
                "El detalle de cada etapa está arriba y en el "
                "registro de actividad.")
    return ("Puesta a punto terminada: escaneo, limpieza, "
            "optimización y revisión de drivers completados. "
            "El detalle de cada etapa está arriba y en el "
            "registro de actividad.")


def ejecutar_puesta_a_punto(
        pasos: list[tuple[str, str, Callable]],
        al_progreso: Callable[[float, str, str], None] | None = None,
        cancelado: Callable[[], bool] | None = None,
        registrar: Callable[[str, str], None] | None = None,
        ahora: Callable[[], float] = time.time) -> dict:
    """Corre los pasos EN ORDEN con progreso global y cancelación.

    al_progreso(fraccion_global 0..1, etapa_actual, texto).
    Devuelve {"cuando", "resultados", "cancelada", "veredicto"}.
    Un paso que falla no detiene a los demás; la cancelación sí:
    lo hecho queda hecho y el resto se marca «omitida».
    """
    cancelado = cancelado or (lambda: False)
    total = max(1, len(pasos))
    resultados: dict[str, dict] = {}
    cancelada = False

    def _emitir(frac: float, etapa: str, texto: str) -> None:
        if al_progreso is not None:
            try:
                al_progreso(max(0.0, min(1.0, frac)), etapa, texto)
            except Exception:
                pass  # el progreso nunca rompe la rutina

    for i, (clave, titulo, funcion) in enumerate(pasos):
        if cancelado():
            cancelada = True
            for clave2, titulo2, _f in pasos[i:]:
                resultados[clave2] = {
                    "ok": False, "omitida": True,
                    "resumen": f"{titulo2}: omitida por cancelación."}
            break
        _emitir(i / total, titulo, titulo)

        def _progreso_etapa(frac: float, texto: str = "",
                            _i=i, _titulo=titulo) -> None:
            _emitir((_i + max(0.0, min(1.0, frac))) / total,
                    _titulo, texto or _titulo)

        try:
            res = funcion(_progreso_etapa, cancelado) or {}
            resultado = {
                "ok": bool(res.get("ok")),
                "resumen": str(res.get("resumen") or ""),
            }
            if res.get("cancelada"):
                resultado["cancelada"] = True
        except Exception as exc:
            resultado = {"ok": False,
                         "resumen": f"No se pudo completar: {exc}"}
        resultados[clave] = resultado
        if registrar is not None:
            try:
                registrar("puesta-a-punto",
                          f"{titulo}: {resultado['resumen']}")
            except Exception:
                pass
        _emitir((i + 1) / total, titulo, resultado["resumen"])
        if resultado.get("cancelada") or cancelado():
            cancelada = True
            for clave2, titulo2, _f in pasos[i + 1:]:
                if clave2 not in resultados:
                    resultados[clave2] = {
                        "ok": False, "omitida": True,
                        "resumen": f"{titulo2}: omitida por cancelación."}
            break

    veredicto = componer_veredicto(resultados, cancelada)
    if not cancelada:
        _emitir(1.0, "", veredicto)
    return {"cuando": float(ahora()), "resultados": resultados,
            "cancelada": cancelada, "veredicto": veredicto}
