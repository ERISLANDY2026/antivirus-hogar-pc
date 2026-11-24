"""Registro de actividad de la app (v1.0.2).

Guarda, en un archivo JSON por líneas dentro de la carpeta de datos, qué
hizo la aplicación y cuándo: escaneos, limpiezas, actualizaciones de
drivers y de programas. La página de Inicio lo enseña y permite
exportarlo como texto.

Sin Qt y sin Windows: la ruta se inyecta, así la suite lo prueba en Linux.
"""
import json
import os
import time
from dataclasses import dataclass


@dataclass
class EntradaActividad:
    cuando: float          # epoch (segundos)
    tipo: str              # "escaneo" | "limpieza" | "drivers" | "programas" | "app" | "sistema"
    detalle: str           # frase en español para el usuario

    def fecha_legible(self) -> str:
        return time.strftime("%d/%m/%Y %H:%M", time.localtime(self.cuando))

    def linea(self) -> str:
        return f"{self.fecha_legible()} — {self.detalle}"


class RegistroActividad:
    """Append-only sobre un archivo .jsonl; tolera líneas corruptas."""

    def __init__(self, ruta: str):
        self.ruta = ruta

    def registrar(self, tipo: str, detalle: str, cuando: float | None = None) -> None:
        entrada = EntradaActividad(
            cuando=float(cuando if cuando is not None else time.time()),
            tipo=tipo, detalle=detalle)
        try:
            os.makedirs(os.path.dirname(self.ruta) or ".", exist_ok=True)
            with open(self.ruta, "a", encoding="utf-8") as f:
                f.write(json.dumps(
                    {"cuando": entrada.cuando, "tipo": entrada.tipo,
                     "detalle": entrada.detalle}, ensure_ascii=False) + "\n")
        except OSError:
            pass  # el registro nunca debe romper la operación que anota

    def leer(self, limite: int = 200) -> list[EntradaActividad]:
        """Todas las entradas, la más reciente primero."""
        entradas: list[EntradaActividad] = []
        try:
            with open(self.ruta, "r", encoding="utf-8") as f:
                lineas = f.readlines()
        except OSError:
            return []
        for linea in lineas:
            linea = linea.strip()
            if not linea:
                continue
            try:
                datos = json.loads(linea)
                entradas.append(EntradaActividad(
                    cuando=float(datos.get("cuando", 0)),
                    tipo=str(datos.get("tipo", "")),
                    detalle=str(datos.get("detalle", ""))))
            except (ValueError, TypeError):
                continue  # línea corrupta: se salta, no se inventa
        entradas.sort(key=lambda e: e.cuando, reverse=True)
        return entradas[:limite]

    def exportar_texto(self) -> str:
        entradas = self.leer(limite=100000)
        if not entradas:
            return "Registro de actividad de Antivirus Hogar PC\n(sin actividad registrada todavía)\n"
        lineas = ["Registro de actividad de Antivirus Hogar PC", ""]
        lineas += [e.linea() for e in reversed(entradas)]
        return "\n".join(lineas) + "\n"
