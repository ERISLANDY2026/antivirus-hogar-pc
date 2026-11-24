"""Programaciones de escaneos y mantenimientos (v1.0.5).

Modelo de datos + cálculo de la próxima ejecución + disparador. El
mecanismo real es el Programador de tareas de Windows (winapi/tasks):
cada programación activa tiene su tarea «AntivirusHogarPC-<id>» que
lanza la app con --tarea-programada <id> a la hora fijada — corre
aunque la app esté cerrada. La app guarda las programaciones en
ajustes.json y sincroniza las tareas de Windows al guardar.

El disparador (ejecutar_tarea_programada) corre la tarea pedida, deja
su resultado en un JSON por tarea (programadas/<id>.json, que la
pantalla enseña como «última ejecución») y en el registro de
actividad. Las tareas son inyectables para la suite.
"""
import datetime as _dt
from dataclasses import asdict, dataclass

DIAS_SEMANA = ("lunes", "martes", "miércoles", "jueves", "viernes",
               "sábado", "domingo")
# Día en español → código de schtasks y weekday() de Python.
_CODIGOS_DIA = {"lunes": "MON", "martes": "TUE", "miércoles": "WED",
                "jueves": "THU", "viernes": "FRI", "sábado": "SAT",
                "domingo": "SUN"}

TIPOS_PROGRAMACION: dict[str, dict] = {
    "escaneo-rapido": {
        "titulo": "Escaneo rápido",
        "descripcion": "Escanea las carpetas de riesgo (Descargas, "
                       "Documentos, Escritorio…). Si encuentra algo, "
                       "lo anota y te avisa: nunca actúa solo."},
    "escaneo-completo": {
        "titulo": "Escaneo completo",
        "descripcion": "Escanea todas las unidades locales completas. "
                       "Tarda más; déjalo para cuando no uses la PC."},
    "drivers": {
        "titulo": "Revisión de drivers",
        "descripcion": "Confirma el estado de los drivers contra las "
                       "fuentes oficiales (Catálogo, Windows Update, "
                       "almacén). Solo revisa: no instala nada."},
    "limpieza": {
        "titulo": "Limpieza segura de discos",
        "descripcion": "Borra temporales y cachés y vacía la papelera "
                       "— solo las categorías seguras de siempre."},
    "firmas": {
        "titulo": "Actualización de firmas",
        "descripcion": "Descarga las firmas de malware y phishing "
                       "más recientes de las fuentes configuradas."},
    "actualizacion-app": {
        "titulo": "Buscar actualizaciones de la app",
        "descripcion": "Comprueba el canal y, si hay versión nueva, "
                       "la descarga y la deja lista; la instalación "
                       "la confirmas tú desde la app."},
}


@dataclass
class Programacion:
    id: str
    activa: bool = False
    frecuencia: str = "semanal"      # "diaria" | "semanal"
    dia: str = "domingo"             # para semanal: día en español
    hora: str = "10:00"              # "HH:MM"

    def a_dict(self) -> dict:
        return asdict(self)


def programaciones_por_defecto() -> list[Programacion]:
    """Las seis programaciones conocidas, con dos activas de fábrica
    (escaneo rápido semanal y firmas diarias, como ya hacía la app de
    Android); el resto las activa el usuario desde la pantalla."""
    return [
        Programacion("escaneo-rapido", activa=True, frecuencia="semanal",
                     dia="domingo", hora="10:00"),
        Programacion("escaneo-completo", activa=False, frecuencia="semanal",
                     dia="domingo", hora="12:00"),
        Programacion("drivers", activa=False, frecuencia="semanal",
                     dia="lunes", hora="09:00"),
        Programacion("limpieza", activa=False, frecuencia="semanal",
                     dia="domingo", hora="11:00"),
        Programacion("firmas", activa=True, frecuencia="diaria",
                     hora="09:00"),
        Programacion("actualizacion-app", activa=False, frecuencia="diaria",
                     hora="09:30"),
    ]


def desde_dicts(datos) -> list[Programacion]:
    """La lista guardada en ajustes → objetos. Lo que falte o sobre se
    reconcilia con las seis conocidas: siempre están las seis."""
    guardadas: dict[str, Programacion] = {}
    for d in datos or []:
        if not isinstance(d, dict) or d.get("id") not in TIPOS_PROGRAMACION:
            continue
        guardadas[d["id"]] = Programacion(
            id=d["id"], activa=bool(d.get("activa", False)),
            frecuencia=d.get("frecuencia") if d.get("frecuencia") in
            ("diaria", "semanal") else "semanal",
            dia=d.get("dia") if d.get("dia") in DIAS_SEMANA else "domingo",
            hora=str(d.get("hora") or "10:00"))
    return [guardadas.get(p.id, p) for p in programaciones_por_defecto()]


def a_dicts(programaciones: list[Programacion]) -> list[dict]:
    return [p.a_dict() for p in programaciones]


def buscar(programaciones: list[Programacion], id_: str) -> Programacion | None:
    for p in programaciones:
        if p.id == id_:
            return p
    return None


def proxima_ejecucion(prog: Programacion,
                      ahora: _dt.datetime | None = None) -> _dt.datetime | None:
    """La próxima vez que toca correr (None si está desactivada).

    Diaria: hoy a la hora si aún no pasó; si pasó, mañana.
    Semanal: el día fijado a la hora; si hoy es el día pero la hora
    pasó, la semana que viene."""
    if not prog.activa:
        return None
    ahora = ahora or _dt.datetime.now()
    try:
        hh, mm = (int(x) for x in prog.hora.split(":"))
    except (ValueError, AttributeError):
        hh, mm = 10, 0
    base = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if prog.frecuencia == "diaria":
        return base if base > ahora else base + _dt.timedelta(days=1)
    objetivo = DIAS_SEMANA.index(prog.dia) if prog.dia in DIAS_SEMANA else 6
    delta_dias = (objetivo - ahora.weekday()) % 7
    candidata = base + _dt.timedelta(days=delta_dias)
    if candidata <= ahora:
        candidata += _dt.timedelta(days=7)
    return candidata


def codigo_dia_schtasks(dia: str) -> str:
    return _CODIGOS_DIA.get(dia, "SUN")


def ejecutar_tarea_programada(id_: str, tareas: dict,
                              registrar,
                              escribir_resultado,
                              ahora=None) -> dict:
    """Disparador: corre LA tarea pedida y deja constancia.

    tareas: {id: callable() -> resumen str}. registrar(tipo, detalle)
    y escribir_resultado(id, resultado) son los ganchos (registro de
    actividad y JSON por tarea). Devuelve el resultado guardado.
    """
    import time as _time

    marca = float(ahora() if callable(ahora) else _time.time())
    funcion = (tareas or {}).get(id_)
    if funcion is None:
        resultado = {"cuando": marca, "ok": False,
                     "resumen": f"Tarea desconocida: {id_}"}
    else:
        try:
            resultado = {"cuando": marca, "ok": True,
                         "resumen": str(funcion())}
        except Exception as exc:
            resultado = {"cuando": marca, "ok": False,
                         "resumen": f"No se pudo completar: {exc}"}
    try:
        registrar("programada",
                  f"{id_}: {resultado['resumen']}")
    except Exception:
        pass
    try:
        escribir_resultado(id_, resultado)
    except Exception:
        pass
    return resultado
