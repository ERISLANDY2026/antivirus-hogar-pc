"""Parseo de la salida de `winget upgrade` (columnas fijas según cabecera).

winget imprime una tabla cuyas columnas se alinean con la cabecera
(Nombre/Id/Versión/Disponible/Origen, en español o inglés según el sistema).
Se localizan las posiciones en la cabecera y se corta cada fila por ellas.
"""
from dataclasses import dataclass


@dataclass
class ProgramaDesactualizado:
    nombre: str
    id_paquete: str
    version_actual: str
    version_disponible: str
    origen: str = ""


_CABECERAS = {
    "id": ("Id", "ID"),
    "version": ("Versión", "Version"),
    "disponible": ("Disponible", "Available"),
    "origen": ("Origen", "Source"),
}


def _posicion(cabecera: str, nombres: tuple[str, ...]) -> int:
    for nombre in nombres:
        idx = cabecera.find(nombre)
        if idx >= 0:
            return idx
    return -1


def parsear_winget_upgrade(texto: str) -> list[ProgramaDesactualizado]:
    lineas = [ln.rstrip("\n") for ln in texto.splitlines()]
    idx_cab = -1
    posiciones: dict[str, int] = {}
    for i, linea in enumerate(lineas):
        pos_id = _posicion(linea, _CABECERAS["id"])
        pos_ver = _posicion(linea, _CABECERAS["version"])
        pos_dis = _posicion(linea, _CABECERAS["disponible"])
        if pos_id > 0 and pos_ver > pos_id and pos_dis > pos_ver:
            idx_cab = i
            posiciones = {
                "id": pos_id, "version": pos_ver, "disponible": pos_dis,
                "origen": _posicion(linea, _CABECERAS["origen"]),
            }
            break
    if idx_cab < 0:
        return []

    def corte(linea: str, desde: int, hasta: int) -> str:
        if hasta < 0:
            return linea[desde:].strip()
        return linea[desde:hasta].strip()

    programas: list[ProgramaDesactualizado] = []
    for linea in lineas[idx_cab + 1:]:
        if not linea.strip():
            continue
        if set(linea.strip()) <= {"-", " "}:
            continue  # línea separadora de guiones
        if linea.strip().startswith(("Se han encontrado", "actualizaciones disponibles", "packages have")):
            continue
        nombre = linea[: posiciones["id"]].strip()
        id_paq = corte(linea, posiciones["id"], posiciones["version"])
        if not nombre or not id_paq:
            continue
        programas.append(
            ProgramaDesactualizado(
                nombre=nombre,
                id_paquete=id_paq,
                version_actual=corte(linea, posiciones["version"], posiciones["disponible"]),
                version_disponible=corte(linea, posiciones["disponible"], posiciones["origen"]),
                origen=corte(linea, posiciones["origen"], -1) if posiciones["origen"] > 0 else "",
            )
        )
    return programas
