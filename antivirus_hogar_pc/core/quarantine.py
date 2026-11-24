"""Cuarentena propia.

Mover un archivo a cuarentena: se traslada a la carpeta de cuarentena de la
app, se renombra con sufijo «.cuarentena» y se le quitan los permisos de
ejecución/escritura. Se guardan los metadatos (ruta original, huellas,
fecha, motivo) para poder RESTAURAR. Nada de esto ocurre sin que el usuario
pulse el botón: la app nunca actúa sola.
"""
import json
import os
import shutil
import time
from dataclasses import asdict, dataclass


@dataclass
class EntradaCuarentena:
    id: str
    ruta_original: str
    nombre_guardado: str
    sha256: str
    md5: str
    etiqueta: str
    fecha: float


class Cuarentena:
    def __init__(self, carpeta: str) -> None:
        self.carpeta = carpeta
        os.makedirs(carpeta, exist_ok=True)
        self.ruta_indice = os.path.join(carpeta, "indice.json")

    # -- índice -------------------------------------------------------------
    def _leer_indice(self) -> list[EntradaCuarentena]:
        if not os.path.isfile(self.ruta_indice):
            return []
        try:
            with open(self.ruta_indice, "r", encoding="utf-8") as f:
                datos = json.load(f)
            return [EntradaCuarentena(**d) for d in datos]
        except (OSError, ValueError, TypeError):
            return []

    def _escribir_indice(self, entradas: list[EntradaCuarentena]) -> None:
        with open(self.ruta_indice, "w", encoding="utf-8") as f:
            json.dump([asdict(e) for e in entradas], f, ensure_ascii=False, indent=1)

    # -- operaciones ----------------------------------------------------------
    def poner_en_cuarentena(self, ruta: str, sha256: str, md5: str, etiqueta: str) -> EntradaCuarentena:
        if not os.path.isfile(ruta):
            raise FileNotFoundError(ruta)
        marca = time.strftime("%Y%m%d-%H%M%S")
        base = os.path.basename(ruta)
        nombre_guardado = f"{marca}_{base}.cuarentena"
        destino = os.path.join(self.carpeta, nombre_guardado)
        contador = 1
        while os.path.exists(destino):
            contador += 1
            nombre_guardado = f"{marca}_{contador}_{base}.cuarentena"
            destino = os.path.join(self.carpeta, nombre_guardado)
        shutil.move(ruta, destino)
        try:
            os.chmod(destino, 0o400)  # solo lectura: no ejecutable, no escribible
        except OSError:
            pass
        entrada = EntradaCuarentena(
            id=nombre_guardado, ruta_original=ruta, nombre_guardado=nombre_guardado,
            sha256=sha256, md5=md5, etiqueta=etiqueta, fecha=time.time(),
        )
        entradas = self._leer_indice()
        entradas.append(entrada)
        self._escribir_indice(entradas)
        return entrada

    def listar(self) -> list[EntradaCuarentena]:
        return self._leer_indice()

    def restaurar(self, id_entrada: str) -> str:
        """Devuelve el archivo a su ruta original. Devuelve la ruta final."""
        entradas = self._leer_indice()
        entrada = next((e for e in entradas if e.id == id_entrada), None)
        if entrada is None:
            raise KeyError(id_entrada)
        origen = os.path.join(self.carpeta, entrada.nombre_guardado)
        destino = entrada.ruta_original
        os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
        if os.path.exists(destino):
            raise FileExistsError(f"Ya existe un archivo en {destino}")
        try:
            os.chmod(origen, 0o600)
        except OSError:
            pass
        shutil.move(origen, destino)
        self._escribir_indice([e for e in entradas if e.id != id_entrada])
        return destino

    def eliminar_definitivo(self, id_entrada: str) -> None:
        entradas = self._leer_indice()
        entrada = next((e for e in entradas if e.id == id_entrada), None)
        if entrada is None:
            raise KeyError(id_entrada)
        ruta = os.path.join(self.carpeta, entrada.nombre_guardado)
        try:
            os.chmod(ruta, 0o600)
        except OSError:
            pass
        if os.path.exists(ruta):
            os.remove(ruta)
        self._escribir_indice([e for e in entradas if e.id != id_entrada])
