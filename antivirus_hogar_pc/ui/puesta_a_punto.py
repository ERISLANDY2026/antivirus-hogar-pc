"""Los pasos REALES de la «Puesta a punto» (v1.0.16, frente 1).

Construye, sobre los servicios que la app ya tiene, los cuatro
pasos que orquesta core.puesta_a_punto: escaneo rápido,
limpieza segura, optimizar volúmenes y revisión de drivers
(solo revisar y contar: instalar sigue siendo paso a paso con
la confirmación del usuario en la pantalla de Drivers).

Sin Qt: la página de Inicio los lanza en su hilo y enseña el
progreso global que la orquestación emite.
"""
from ..core.puesta_a_punto import ETAPAS
from ..core.scanner import escanear
from ..modules.system import servicios_sistema as svc_sys
from ..winapi import disks as discos_win


def pasos_reales(servicios) -> list[tuple[str, str, object]]:
    """[(clave, título, funcion(progreso, cancelado)->dict)]."""

    def escaneo(progreso, cancelado):
        descargas = servicios.carpeta_descargas()

        def _prog(_ruta, revisados, total):
            if total:
                progreso(revisados / total,
                         f"Escaneo rápido: {revisados} de {total} archivos")

        resultado = escanear(
            servicios.carpetas_riesgo(), servicios.base_firmas,
            cache=servicios.cache, solo_ejecutables=True,
            forzar_rehash_en=[descargas] if descargas else [],
            progreso=_prog, debe_cancelar=cancelado)
        servicios.registrar_escaneo(resultado)
        texto = (f"Escaneo rápido: {resultado.archivos_revisados} "
                 f"archivos revisados, {len(resultado.hallazgos)} "
                 "hallazgo(s)")
        if resultado.hallazgos:
            texto += " — sin tocar nada: decide tú qué hacer"
        if getattr(resultado, "cancelado", False):
            return {"ok": False, "cancelada": True,
                    "resumen": texto + " (cancelado a mitad)"}
        return {"ok": True, "resumen": texto}

    def limpieza(progreso, cancelado):
        def _prog(hechas, total):
            if total:
                progreso(hechas / total,
                         f"Limpieza segura: partida {hechas} de {total}")

        res = svc_sys.limpiar_con_progreso(_prog)
        if not res.ok:
            return {"ok": False, "resumen": res.mensaje}
        partes = [res.mensaje]
        if cancelado():
            return {"ok": True, "resumen": " · ".join(partes)}
        papelera = svc_sys.vaciar_papelera()
        if papelera.ok:
            partes.append(papelera.mensaje)
        return {"ok": True, "resumen": " · ".join(partes)}

    def optimizar(progreso, cancelado):
        fisicos = discos_win.discos_fisicos()
        volumenes = [v for v in discos_win.volumenes() if v.get("letra")]
        if not volumenes:
            return {"ok": False,
                    "resumen": "No se encontró ningún volumen que optimizar."}
        mensajes: list[str] = []
        todo_ok = True
        for i, volumen in enumerate(volumenes):
            if cancelado():
                return {"ok": todo_ok and bool(mensajes),
                        "cancelada": True,
                        "resumen": " · ".join(mensajes)
                        or "Optimización cancelada antes de empezar."}
            letra = str(volumen["letra"])
            es_ssd = svc_sys.tipo_de_volumen(fisicos, volumen) == "SSD"

            def _prog(fase, pct, _i=i, _n=len(volumenes), _letra=letra):
                base = _i / _n
                frac = base if pct is None else base + (pct / 100.0) / _n
                progreso(frac, f"Optimizando {_letra}: — {fase}")

            res = svc_sys.optimizar_volumen(letra, es_ssd,
                                             al_progreso=_prog)
            mensajes.append(f"{letra}: {res.mensaje}")
            todo_ok = todo_ok and bool(res.ok)
        return {"ok": todo_ok, "resumen": " · ".join(mensajes)}

    def drivers(progreso, cancelado):
        paso1 = svc_sys.escanear_drivers_paso1()
        if not paso1.ok or not isinstance(paso1.datos, dict):
            return {"ok": False,
                    "resumen": paso1.mensaje or "Sin datos de drivers."}
        instalados = paso1.datos["instalados"]
        progreso(0.2, "Revisión de drivers: consultando Windows Update")
        paso2 = svc_sys.escanear_drivers_paso2_buscar(instalados)
        final = svc_sys.escanear_drivers_paso3_comparar(
            instalados,
            (paso2.datos or {}).get("ofrecidas", []),
            bool((paso2.datos or {}).get("wu_consultado")),
            paso1.datos.get("fabricante_pc", ""),
            str((paso2.datos or {}).get("wu_causa", "")),
            estados_previos=(paso2.datos or {}).get("estados"))
        estados = (final.datos or {}).get("estados", [])
        # La revisión queda guardada para la tarjeta
        # «Pendientes» en el propio paso 3 (servicios_sistema).
        return {"ok": bool(final.ok), "resumen": final.mensaje}

    funciones = {"escaneo": escaneo, "limpieza": limpieza,
                 "optimizar": optimizar, "drivers": drivers}
    return [(clave, titulo, funciones[clave]) for clave, titulo in ETAPAS]
