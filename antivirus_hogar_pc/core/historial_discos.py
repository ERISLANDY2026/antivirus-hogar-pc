"""Historial y TENDENCIA de salud de los discos (v1.0.16, frente 4).

La app ya leía la salud SMART del momento («la foto de hoy»);
desde esta versión cada lectura con datos se guarda en un
historial local (historial_discos.json en la carpeta de datos)
y el Panel puede decir si la salud está ESTABLE o BAJANDO
respecto a hace ~30 días — el aviso que importa en un SSD es
el cambio, no la foto.

Honestidad (regla de la casa):
- Sin lecturas suficientes (la primera, o todas demasiado
  recientes), la tendencia es «sin_historial» y la UI dice
  «historial en construcción»: jamás una tendencia inventada.
- Las lecturas sin datos (sin_datos: disco tras puente USB o
  RAID) NO se guardan: no aporten ni ruido ni falsas alarmas.
- Nivel comparable entre lecturas: si hay desgaste (% de vida
  consumida), nivel = 100 − desgaste; si no, el estado
  Healthy/Warning/Unhealthy vale 100/55/10. «Bajando» = el
  nivel cae ≥ 3 puntos contra la referencia o el estado sano
  pasa a no sano.

Sin Qt y sin Windows: la ruta se inyecta y las lecturas son los
dicts de winapi.disks.discos_fisicos() (o SmartInfo convertida),
así la suite lo prueba en Linux.
"""
import json
import os
import time

ARCHIVO = "historial_discos.json"
_ESPACIO_MINIMO = 6 * 3600          # entre lecturas guardadas del mismo disco
_VENTANA_REFERENCIA = (5 * 86400, 45 * 86400)   # ~30 días, con margen
_MAX_POR_DISCO = 400
_CAIDA_MINIMA = 3.0                 # puntos de nivel para decir «bajando»


def ruta_historial() -> str:
    from .. import config

    return os.path.join(config.carpeta_datos(), ARCHIVO)


def nivel_salud(lectura: dict) -> float | None:
    """Nivel 0..100 comparable de UNA lectura, o None sin datos."""
    if lectura.get("sin_datos"):
        return None
    desgaste = lectura.get("desgaste_pct")
    if isinstance(desgaste, (int, float)):
        return max(0.0, min(100.0, 100.0 - float(desgaste)))
    salud = str(lectura.get("salud") or "")
    if salud == "Healthy":
        return 100.0
    if salud == "Warning":
        return 55.0
    if salud == "Unhealthy":
        return 10.0
    if lectura.get("sano") is True:
        return 100.0
    if lectura.get("sano") is False:
        return 10.0
    return None


def _clave_disco(lectura: dict) -> str:
    return str(lectura.get("nombre") or "Disco").strip()


def cargar(ruta: str) -> dict:
    """El historial guardado: {nombre: [ {cuando, nivel, salud,
    desgaste_pct}, … ]} ordenado por fecha. {} si no hay o está
    corrupto (se empieza de cero, sin romper nada)."""
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
        if isinstance(datos, dict):
            return {str(k): [e for e in v if isinstance(e, dict)]
                    for k, v in datos.items() if isinstance(v, list)}
    except (OSError, ValueError):
        pass
    return {}


def guardar(historial: dict, ruta: str) -> None:
    try:
        os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(historial, f, ensure_ascii=False, indent=1)
    except OSError:
        pass  # el historial nunca debe romper la lectura que lo alimenta


def registrar_lecturas(discos: list[dict], ruta: str,
                       ahora: float | None = None) -> dict:
    """Añade las lecturas CON datos al historial y lo persiste.

    Espaciado: del mismo disco solo se guarda una lectura cada
    ~6 h (salvo que el nivel cambie, que siempre se anota), para
    que abrir la app diez veces al día no infle el archivo.
    Devuelve el historial resultante."""
    ahora = float(ahora if ahora is not None else time.time())
    historial = cargar(ruta)
    cambio = False
    for disco in discos or []:
        nivel = nivel_salud(disco)
        if nivel is None:
            continue  # sin datos: no se guarda (honestidad)
        clave = _clave_disco(disco)
        entradas = historial.setdefault(clave, [])
        ultima = entradas[-1] if entradas else None
        if ultima is not None:
            mismo_nivel = abs(float(ultima.get("nivel", -1)) - nivel) < 0.01
            if mismo_nivel and ahora - float(ultima.get("cuando", 0)) \
                    < _ESPACIO_MINIMO:
                continue
        entradas.append({
            "cuando": ahora,
            "nivel": nivel,
            "salud": str(disco.get("salud") or ""),
            "desgaste_pct": disco.get("desgaste_pct"),
        })
        entradas.sort(key=lambda e: float(e.get("cuando", 0)))
        del entradas[:-_MAX_POR_DISCO]
        cambio = True
    if cambio:
        guardar(historial, ruta)
    return historial


def _referencia(entradas: list[dict], ahora: float) -> dict | None:
    """La lectura de referencia (~30 días atrás): la más cercana
    a ese punto dentro de la ventana; si ninguna cae en la
    ventana, la más antigua SOLO si tiene ≥ 5 días (una
    tendencia con dos fotos del mismo día no significa nada)."""
    if not entradas:
        return None
    objetivo = ahora - 30 * 86400
    en_ventana = [e for e in entradas
                  if _VENTANA_REFERENCIA[0]
                  <= ahora - float(e.get("cuando", 0))
                  <= _VENTANA_REFERENCIA[1]]
    if en_ventana:
        return min(en_ventana,
                   key=lambda e: abs(float(e.get("cuando", 0)) - objetivo))
    antigua = entradas[0]
    if ahora - float(antigua.get("cuando", 0)) >= _VENTANA_REFERENCIA[0]:
        return antigua
    return None


def tendencia_disco(entradas: list[dict], nivel_actual: float | None,
                    ahora: float | None = None) -> dict:
    """Tendencia de UN disco: {estado, bajando, dias, delta}.

    estado: «bajando» | «estable» | «sin_historial»."""
    ahora = float(ahora if ahora is not None else time.time())
    if nivel_actual is None:
        return {"estado": "sin_historial", "bajando": False,
                "dias": None, "delta": None}
    ordenadas = sorted(entradas or [],
                       key=lambda e: float(e.get("cuando", 0)))
    ref = _referencia(ordenadas, ahora)
    if ref is None:
        return {"estado": "sin_historial", "bajando": False,
                "dias": None, "delta": None}
    delta = nivel_actual - float(ref.get("nivel", nivel_actual))
    dias = int(round((ahora - float(ref.get("cuando", ahora))) / 86400))
    bajando = delta <= -_CAIDA_MINIMA
    return {"estado": "bajando" if bajando else "estable",
            "bajando": bajando, "dias": dias, "delta": round(delta, 1)}


def tendencia_principal(discos: list[dict], historial: dict,
                        ahora: float | None = None) -> dict:
    """La tendencia del PRIMER disco con datos (el principal):
    {estado, bajando, disco, dias, delta}."""
    for disco in discos or []:
        nivel = nivel_salud(disco)
        if nivel is None:
            continue
        clave = _clave_disco(disco)
        t = tendencia_disco(historial.get(clave, []), nivel, ahora)
        t["disco"] = clave
        return t
    return {"estado": "sin_historial", "bajando": False, "disco": "",
            "dias": None, "delta": None}
