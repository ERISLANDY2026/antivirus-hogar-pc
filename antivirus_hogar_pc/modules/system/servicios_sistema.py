"""Orquestación del Carril C (sin Qt): drivers, discos y limpieza.

Cada función devuelve contracts.ResultadoModulo y NUNCA lanza: los fallos
(incluido «esto solo funciona en Windows») viajan en el sobre con su frase
en español, como manda el contrato.

Cadena de drivers (orden del usuario, solo fuentes oficiales):
  1. Windows Update / Microsoft Update Catalog
  2. Fabricantes de chips (NVIDIA / AMD / Intel)
  3. Página oficial de la marca de la PC
Antes de instalar: punto de restauración automático. Solo drivers firmados
(Windows Update solo sirve drivers firmados por Microsoft).
"""
import os

from antivirus_hogar_pc import config
from antivirus_hogar_pc.contracts import (InformeTuneUp, PartidaLimpieza,
                                          ResultadoModulo, SmartInfo)
from antivirus_hogar_pc.core import drivers_logic, v102
from antivirus_hogar_pc.core.hashing import tamano_legible
from antivirus_hogar_pc.winapi import WindowsNoDisponible
from antivirus_hogar_pc.winapi import drivers_win, system_info, tuneup_win
from antivirus_hogar_pc.winapi import disks as discos_win

from .smart_logic import (fusionar_smart, smart_desde_physicaldisk,
                          smart_desde_pysmart, tipo_para_volumen)


def _fallo(exc: Exception, contexto: str) -> ResultadoModulo:
    if isinstance(exc, WindowsNoDisponible):
        return ResultadoModulo(ok=False, mensaje="Disponible solo en Windows.",
                               detalle_tecnico=str(exc))
    return ResultadoModulo(ok=False, mensaje=f"No se pudo completar {contexto}: {exc}",
                           detalle_tecnico=repr(exc))


# === DRIVERS ====================================================================
def escanear_drivers_paso1() -> ResultadoModulo:
    """Paso 1 del escaneo: enumerar los drivers instalados y leer la marca
    de la PC. datos = {"instalados": [...], "fabricante_pc": str}."""
    try:
        instalados = drivers_win.enumerar_drivers()
    except Exception as exc:
        return _fallo(exc, "la enumeración de drivers")
    if not instalados:
        return ResultadoModulo(ok=False, mensaje="No se encontró ningún driver "
                                                 "en esta PC.")
    fabricante_pc = ""
    try:
        fabricante_pc = system_info.fabricante_y_modelo_pc().get("fabricante", "")
    except Exception:
        pass  # el enlace OEM es un respaldo; sin él la cadena sigue
    return ResultadoModulo(
        ok=True,
        mensaje=f"Se leyeron {len(instalados)} drivers instalados.",
        datos={"instalados": instalados, "fabricante_pc": fabricante_pc})


def escanear_drivers_paso2(instalados, fabricante_pc: str = "") -> ResultadoModulo:
    """Paso 2 del escaneo: contrastar los instalados con Windows Update.
    Devuelve el resultado completo de siempre (estados, fabricante_pc,
    wu_consultado, ofrecidas_wu)."""
    try:
        ofrecidas = drivers_win.buscar_drivers_windows_update()
        wu_consultado = True
    except Exception:
        ofrecidas = []
        wu_consultado = False

    if wu_consultado:
        estados = drivers_logic.contrastar_con_windows_update(instalados, ofrecidas)
    else:
        estados = [
            drivers_logic.EstadoDriver(
                driver=d, estado="sin_datos",
                detalle="No se pudo consultar Windows Update en este intento; "
                        "el estado de este driver queda sin confirmar.")
            for d in instalados
        ]
    nuevos = sum(1 for e in estados if e.estado == "hay_uno_mas_nuevo")
    if not wu_consultado:
        mensaje = (f"Se leyeron {len(instalados)} drivers, pero Windows Update "
                   "no respondió: ningún estado está confirmado.")
    elif nuevos:
        mensaje = (f"{len(instalados)} drivers revisados contra Windows Update: "
                   f"{nuevos} con una versión más nueva disponible.")
    else:
        mensaje = (f"{len(instalados)} drivers revisados contra Windows Update: "
                   "todos al día según la fuente oficial.")
    return ResultadoModulo(ok=True, mensaje=mensaje, datos={
        "estados": estados,
        "fabricante_pc": fabricante_pc,
        "wu_consultado": wu_consultado,
        "ofrecidas_wu": len(ofrecidas),
    })


def escanear_drivers() -> ResultadoModulo:
    """Envoltorio compatible: paso 1 (enumerar) + paso 2 (Windows Update)."""
    paso1 = escanear_drivers_paso1()
    if not paso1.ok or not isinstance(paso1.datos, dict):
        return paso1
    return escanear_drivers_paso2(paso1.datos["instalados"],
                                  paso1.datos.get("fabricante_pc", ""))


def enlaces_oficiales_driver(estado: drivers_logic.EstadoDriver,
                             fabricante_pc: str = "") -> list[tuple[str, str]]:
    """La cadena de respaldo (Catálogo → chip → OEM) para un driver."""
    return drivers_logic.enlaces_para_driver(estado, fabricante_pc)


def crear_punto_para_drivers() -> ResultadoModulo:
    """Paso 1 de la actualización: crear el punto de restauración. Si este
    paso falla, la actualización NO debe seguir a la instalación."""
    try:
        creado = drivers_win.crear_punto_restauracion(
            "Antivirus Hogar PC — antes de actualizar drivers")
    except Exception as exc:
        return _fallo(exc, "la creación del punto de restauración")
    if not creado:
        return ResultadoModulo(
            ok=False,
            mensaje="No se pudo crear el punto de restauración, así que no se "
                    "instaló nada. Revisa que la protección del sistema esté "
                    "activada en la unidad C: e inténtalo de nuevo.")
    return ResultadoModulo(ok=True, mensaje="Punto de restauración creado.")


def instalar_drivers_wu() -> ResultadoModulo:
    """Paso 2 de la actualización: Windows Update descarga e instala los
    drivers que ofrece (todos firmados por Microsoft). Windows Update no
    expone un porcentaje real de esta instalación."""
    try:
        instalado = drivers_win.instalar_drivers_windows_update()
    except Exception as exc:
        return _fallo(exc, "la instalación de drivers")
    if instalado:
        return ResultadoModulo(
            ok=True,
            mensaje="Windows Update instaló los drivers nuevos. Vuelve a "
                    "escanear para confirmar el estado; puede hacer falta "
                    "reiniciar la PC.")
    return ResultadoModulo(
        ok=False,
        mensaje="La instalación no se completó (puede haberse cancelado el "
                "aviso de administrador). No pasa nada: inténtalo de nuevo "
                "cuando quieras.")


def actualizar_drivers() -> ResultadoModulo:
    """Envoltorio compatible con la misma lógica de seguridad de siempre:
    punto de restauración primero; si no se puede crear, NO se instala."""
    punto = crear_punto_para_drivers()
    if not punto.ok:
        return punto
    instalacion = instalar_drivers_wu()
    if instalacion.ok:
        return ResultadoModulo(
            ok=True,
            mensaje="Punto de restauración creado y Windows Update instaló los "
                    "drivers nuevos. Vuelve a escanear para confirmar el estado; "
                    "puede hacer falta reiniciar la PC.")
    return ResultadoModulo(
        ok=False,
        mensaje="El punto de restauración se creó, pero la instalación no se "
                "completó (puede haberse cancelado el aviso de administrador). "
                "No pasa nada: inténtalo de nuevo cuando quieras.")


# === DISCOS =====================================================================
def _atributo_smart(dev, id_o_nombre) -> int | None:
    """Lee un atributo SMART de un Device de pySMART sin romperse: pySMART
    expone `attributes` como lista indexada por ID (con huecos) o como
    colección de objetos con .name/.raw según la versión."""
    try:
        atributos = getattr(dev, "attributes", None)
        if atributos is None:
            return None
        candidato = None
        if isinstance(id_o_nombre, int):
            if isinstance(atributos, dict):
                candidato = atributos.get(id_o_nombre)
            elif isinstance(atributos, (list, tuple)) and len(atributos) > id_o_nombre:
                candidato = atributos[id_o_nombre]
        else:
            iterable = atributos.values() if isinstance(atributos, dict) else atributos
            for atributo in iterable or []:
                if atributo is not None and id_o_nombre.lower() in str(
                        getattr(atributo, "name", "")).lower():
                    candidato = atributo
                    break
        if candidato is None:
            return None
        return int(getattr(candidato, "raw", 0))
    except Exception:
        return None


def _leer_pysmart() -> list[SmartInfo]:
    """Datos vía pySMART/smartctl. Si pySMART no está o smartctl no
    responde, devuelve [] y manda el respaldo de Windows."""
    try:
        from pySMART import DeviceList
    except Exception:
        return []
    try:
        dispositivos = DeviceList().devices or []
    except Exception:
        return []
    infos: list[SmartInfo] = []
    for dev in dispositivos:
        modelo = str(getattr(dev, "model", "") or getattr(dev, "name", "") or "Disco")
        interfaz = str(getattr(dev, "interface", "") or "").upper()
        if "NVME" in interfaz or "nvme" in modelo.lower():
            tipo = "NVMe"
        elif "ssd" in modelo.lower():
            tipo = "SSD"
        else:
            tipo = ""
        horas = getattr(dev, "power_on_hours", None)
        if horas is None:
            horas = _atributo_smart(dev, 9)  # Power-On Hours
        desgaste = None
        porcentaje_usado = _atributo_smart(dev, "Percentage Used")  # NVMe
        if porcentaje_usado is not None:
            desgaste = porcentaje_usado
        else:
            vida_restante = _atributo_smart(dev, 231)  # SSD Life Left (SATA)
            if vida_restante is not None:
                desgaste = max(0, 100 - vida_restante)
        errores = None
        suma = 0
        encontrado = False
        for id_error in (5, 187, 197, 198):  # reasignados / no corregibles / pendientes
            valor = _atributo_smart(dev, id_error)
            if valor is not None:
                suma += valor
                encontrado = True
        if encontrado:
            errores = suma
        temperatura = getattr(dev, "temperature", None)
        infos.append(smart_desde_pysmart({
            "modelo": modelo, "tipo": tipo,
            "evaluacion": str(getattr(dev, "assessment", "") or ""),
            "temperatura_c": int(temperatura) if temperatura is not None else None,
            "horas_encendido": int(horas) if horas is not None else None,
            "desgaste_pct": int(desgaste) if desgaste is not None else None,
            "errores": errores,
        }))
    return infos


def salud_discos() -> ResultadoModulo:
    """Salud SMART fusionando pySMART/smartctl y Get-PhysicalDisk."""
    de_pysmart = _leer_pysmart()
    fisicos: list[dict] = []
    de_windows: list[SmartInfo] = []
    error_windows: Exception | None = None
    try:
        fisicos = discos_win.discos_fisicos()
        de_windows = [smart_desde_physicaldisk(d) for d in fisicos]
    except Exception as exc:
        error_windows = exc
    if not de_pysmart and not de_windows:
        if error_windows is not None:
            return _fallo(error_windows, "la lectura de los discos")
        return ResultadoModulo(ok=False, mensaje="No se pudo leer ningún disco "
                                                 "en esta PC.")
    volumenes: list[dict] = []
    try:
        volumenes = discos_win.volumenes()
    except Exception:
        pass
    discos = fusionar_smart(de_pysmart, de_windows) if de_windows else de_pysmart
    con_datos = sum(1 for d in discos if not d.sin_datos)
    mensaje = (f"{len(discos)} disco(s) revisados: {con_datos} con salud "
               f"legible y {len(discos) - con_datos} sin datos (no se pueden leer).")
    return ResultadoModulo(ok=True, mensaje=mensaje, datos={
        "discos": discos, "volumenes": volumenes, "fisicos": fisicos,
    })


def tipo_de_volumen(fisicos: list[dict], volumen: dict) -> str:
    return tipo_para_volumen(fisicos, int(volumen.get("tamano") or 0))


def optimizar_volumen(letra: str, es_ssd: bool) -> ResultadoModulo:
    """Optimize-Volume de Windows: TRIM en SSD, desfragmentación en HDD."""
    try:
        hecho = discos_win.optimizar_volumen(letra, es_ssd)
    except Exception as exc:
        return _fallo(exc, "la optimización del volumen")
    if hecho:
        return ResultadoModulo(
            ok=True, mensaje=f"Windows optimizó la unidad {letra}: "
                             f"({'TRIM' if es_ssd else 'desfragmentación'}).")
    return ResultadoModulo(
        ok=False, mensaje=f"La optimización de la unidad {letra}: no se "
                          "completó (puede haberse cancelado el aviso de "
                          "administrador).")


def _tamano_carpeta(ruta: str) -> int:
    """Bytes totales de una carpeta por recorrido os.walk; los errores de
    lectura (permisos, archivos que desaparecen) se ignoran."""
    total = 0
    if not ruta or not os.path.isdir(ruta):
        return 0
    for dirpath, _dirs, archivos in os.walk(ruta):
        for nombre in archivos:
            try:
                total += os.path.getsize(os.path.join(dirpath, nombre))
            except OSError:
                continue
    return total


_CARPETAS_MAPA = (
    ("Descargas", ("Descargas", "Downloads")),
    ("Documentos", ("Documentos", "Documents")),
    ("Escritorio", ("Escritorio", "Desktop")),
    ("Imágenes", ("Imágenes", "Pictures")),
    ("Vídeos", ("Vídeos", "Videos")),
    ("Música", ("Música", "Music")),
)


def mapa_disco(progreso=None) -> ResultadoModulo:
    """Mapa de uso: tamaño de las carpetas del usuario del perfil más la
    temporal. datos = core.v102.mapa_desde_tamanos(...) -> [{nombre, bytes,
    pct}] con pct sobre el TOTAL MEDIDO de esas carpetas (no del disco).
    progreso(i, n_carpetas) se llama tras medir cada carpeta."""
    try:
        hogar = os.path.expanduser("~")
        candidatas: list[tuple[str, str]] = []
        for nombre, variantes in _CARPETAS_MAPA:
            for variante in variantes:
                ruta = os.path.join(hogar, variante)
                if os.path.isdir(ruta):
                    candidatas.append((nombre, ruta))
                    break
        temporal = os.environ.get("TEMP", "")
        if temporal and os.path.isdir(temporal):
            candidatas.append(("Temporales", temporal))
        tamanos: dict[str, int] = {}
        total_carpetas = len(candidatas)
        for i, (nombre, ruta) in enumerate(candidatas, start=1):
            tamanos[nombre] = _tamano_carpeta(ruta)
            if progreso is not None:
                try:
                    progreso(i, total_carpetas)
                except Exception:
                    pass  # un fallo del indicador no detiene la medición
        mapa = v102.mapa_desde_tamanos(tamanos)
        total_med = sum(int(fila["bytes"]) for fila in mapa)
        return ResultadoModulo(
            ok=True,
            mensaje=(f"Mapa calculado: {tamano_legible(total_med)} medidos en "
                     f"{total_carpetas} carpeta(s). Los porcentajes son sobre "
                     "ese total medido, no sobre todo el disco."),
            datos=mapa)
    except Exception as exc:
        return _fallo(exc, "el cálculo del mapa de disco")


# === LIMPIEZA (tune-up) ===========================================================
def analizar_limpieza() -> ResultadoModulo:
    """Informe ANTES de borrar: qué carpetas temporales y cuánto ocupan,
    más la papelera. No borra nada."""
    try:
        analisis = tuneup_win.analizar_temporales()
        papelera = tuneup_win.tamano_papelera()
    except Exception as exc:
        return _fallo(exc, "el análisis de limpieza")
    partidas = [PartidaLimpieza(nombre=a["nombre"], ruta=a["ruta"],
                                tamano=int(a["tamano"]))
                for a in analisis if int(a["tamano"]) > 0]
    informe = InformeTuneUp(partidas=partidas, papelera_bytes=int(papelera))
    return ResultadoModulo(
        ok=True,
        mensaje=f"Se pueden liberar {len(partidas)} partida(s) de temporales "
                "más la papelera. Nada se ha borrado todavía.",
        datos=informe)


def limpiar_temporales() -> ResultadoModulo:
    """Borra el contenido de las carpetas temporales; lo que esté en uso se
    salta solo (Windows lo bloquea), nunca se fuerza."""
    try:
        resultado = tuneup_win.limpiar_temporales()
    except Exception as exc:
        return _fallo(exc, "la limpieza de temporales")
    mensaje = f"Temporales limpiados: {resultado['borrados']} archivo(s) borrados."
    if resultado["errores"]:
        mensaje += (f" {resultado['errores']} no se pudieron borrar porque "
                    "están en uso; es normal y no pasa nada.")
    return ResultadoModulo(ok=True, mensaje=mensaje, datos=resultado)


def limpiar_con_progreso(progreso) -> ResultadoModulo:
    """Como limpiar_temporales(), pero con progreso REAL por partidas:
    progreso(borradas, total_partidas) se llama tras procesar cada partida
    del análisis (borradas = partidas ya procesadas), para que la barra
    enseñe partidas x de y de verdad.

    tuneup_win.limpiar_temporales() borra todas las carpetas de golpe y no
    sirve por partidas, así que el borrado por partida vive aquí: se
    reutiliza tuneup_win.analizar_temporales() para las partidas y se
    respeta su misma regla de las miniaturas (solo archivos thumbcache).
    Lo que esté en uso se salta solo, nunca se fuerza."""
    try:
        partidas = tuneup_win.analizar_temporales()
    except Exception as exc:
        return _fallo(exc, "el análisis de limpieza")
    total_partidas = len(partidas)
    borrados = 0
    errores = 0
    bytes_liberados = 0
    for indice, partida in enumerate(partidas, start=1):
        ruta = partida.get("ruta", "")
        patron = "thumbcache" if "Miniaturas" in partida.get("nombre", "") else ""
        if ruta and os.path.isdir(ruta):
            for dirpath, _dirs, archivos in os.walk(ruta):
                for nombre in archivos:
                    if patron and patron not in nombre.lower():
                        continue
                    ruta_archivo = os.path.join(dirpath, nombre)
                    try:
                        tamano = os.path.getsize(ruta_archivo)
                        os.remove(ruta_archivo)
                        bytes_liberados += tamano
                        borrados += 1
                    except OSError:
                        errores += 1
        if progreso is not None:
            try:
                progreso(indice, total_partidas)
            except Exception:
                pass  # un fallo del indicador no detiene la limpieza
    mensaje = (f"Temporales limpiados: {borrados} archivo(s) borrados "
               f"({tamano_legible(bytes_liberados)} liberados).")
    if errores:
        mensaje += (f" {errores} no se pudieron borrar porque están en uso; "
                    "es normal y no pasa nada.")
    return ResultadoModulo(ok=True, mensaje=mensaje, datos={
        "borrados": borrados, "errores": errores,
        "bytes_liberados": bytes_liberados, "partidas": total_partidas,
    })


def vaciar_papelera() -> ResultadoModulo:
    try:
        hecho = tuneup_win.vaciar_papelera()
    except Exception as exc:
        return _fallo(exc, "el vaciado de la papelera")
    if hecho:
        return ResultadoModulo(ok=True, mensaje="Papelera vaciada.")
    return ResultadoModulo(ok=False, mensaje="No se pudo vaciar la papelera.")


# === Arranque reversible ==========================================================
def _carpeta_inicio() -> str:
    return os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows",
                        "Start Menu", "Programs", "Startup")


def elementos_arranque() -> ResultadoModulo:
    """Programas que arrancan con Windows (Win32_StartupCommand). Solo los
    de la carpeta de inicio se pueden desactivar de forma reversible con
    esta app; el resto se enseña con su origen."""
    try:
        elementos = system_info.elementos_arranque()
    except Exception as exc:
        return _fallo(exc, "la lectura del arranque")
    archivos_inicio: dict[str, str] = {}
    carpeta = _carpeta_inicio()
    if os.path.isdir(carpeta):
        for nombre in os.listdir(carpeta):
            archivos_inicio[os.path.splitext(nombre)[0].lower()] = nombre
    salida = []
    for elemento in elementos:
        nombre = elemento.get("nombre", "")
        archivo = archivos_inicio.get(nombre.lower(), "")
        impacto, impacto_motivo = v102.clasificar_impacto_arranque(
            nombre, elemento.get("comando", ""))
        salida.append({
            **elemento,
            "reversible": bool(archivo),
            "archivo_inicio": archivo,
            "impacto": impacto,
            "impacto_motivo": impacto_motivo,
        })
    return ResultadoModulo(
        ok=True,
        mensaje=f"{len(salida)} programa(s) arrancan con Windows.",
        datos=salida)


def desactivar_arranque(nombre_archivo: str) -> ResultadoModulo:
    """Mueve el acceso de la carpeta de inicio a respaldos (reversible)."""
    try:
        hecho = tuneup_win.desactivar_arranque_inicio(
            nombre_archivo, config.ruta_respaldos())
    except Exception as exc:
        return _fallo(exc, "la desactivación del arranque")
    if hecho:
        return ResultadoModulo(
            ok=True, mensaje="Arranque desactivado. No se ha borrado nada: "
                             "puedes restaurarlo cuando quieras desde aquí.")
    return ResultadoModulo(ok=False, mensaje="No se encontró ese acceso en la "
                                             "carpeta de inicio.")


def restaurar_arranque() -> ResultadoModulo:
    try:
        cuantos = tuneup_win.restaurar_arranque(config.ruta_respaldos())
    except Exception as exc:
        return _fallo(exc, "la restauración del arranque")
    if cuantos:
        return ResultadoModulo(ok=True, mensaje=f"{cuantos} arranque(s) "
                                                "restaurados.")
    return ResultadoModulo(ok=True, mensaje="No había arranques desactivados "
                                            "por esta app para restaurar.")


# === Respaldo antes de cambios ====================================================
def crear_punto_restauracion() -> ResultadoModulo:
    try:
        creado = drivers_win.crear_punto_restauracion(
            "Antivirus Hogar PC — punto manual desde Limpieza")
    except Exception as exc:
        return _fallo(exc, "la creación del punto de restauración")
    if creado:
        return ResultadoModulo(ok=True, mensaje="Punto de restauración creado.")
    return ResultadoModulo(
        ok=False, mensaje="No se pudo crear el punto de restauración. Revisa "
                          "que la protección del sistema esté activada en C:.")


def respaldo_registro() -> ResultadoModulo:
    """La alternativa segura al «limpiador de registro»: copiar, no tocar."""
    try:
        creados = tuneup_win.respaldo_registro(config.ruta_respaldos())
    except Exception as exc:
        return _fallo(exc, "la copia del registro")
    if creados:
        nombres = ", ".join(os.path.basename(r) for r in creados)
        return ResultadoModulo(
            ok=True, datos=creados,
            mensaje=f"Copia del registro guardada en Respaldos: {nombres}. "
                    "El registro no se ha modificado.")
    return ResultadoModulo(ok=False, mensaje="No se pudo hacer la copia del "
                                             "registro.")
