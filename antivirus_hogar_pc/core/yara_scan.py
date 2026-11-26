"""Segundo motor de escaneo: reglas YARA (v1.0.21).

Trabaja JUNTO al motor de huellas (core.scanner), no lo sustituye:
las reglas del paquete «core» de YARA Forge detectan familias y
comportamientos que una huella exacta no caza. Cada coincidencia
conserva el NOMBRE de la regla, su AUTOR y su LICENCIA tal como
vienen en el meta de la regla — la atribución es parte del dato.

Motor: YARA-X (bindings oficiales de VirusTotal) como primera
opción; si su módulo nativo no está disponible en la instalación,
se usa yara-python (el bindings oficial clásico), y si ninguno
está, el motor queda «no disponible» con el motivo, sin romper
nada: el escaneo por huellas sigue funcionando igual.

Las reglas empaquetadas viven en assets/yara/ (paquete core de
YARA Forge, con autor y licencia por regla en su propio texto).
"""
import os
import threading
from dataclasses import dataclass, field

from .. import config

LIMITE_LECTURA = 64 * 1024 * 1024  # 64 MB por archivo, como el resto


@dataclass
class CoincidenciaYara:
    regla: str
    autor: str = ""
    licencia: str = ""
    descripcion: str = ""
    motor: str = ""


@dataclass
class EstadoMotor:
    disponible: bool = False
    motor: str = ""  # yara-x | yara-python
    motivo: str = ""
    archivos_reglas: list[str] = field(default_factory=list)


class _Motor:
    """Compila una vez (con candado) y escanea bytes o archivos."""

    def __init__(self) -> None:
        self._candado = threading.Lock()
        self._listo = False
        self.estado = EstadoMotor()
        self._escaner = None       # yara_x.Scanner
        self._reglas_py = None     # yara.Rules

    # -- carga ------------------------------------------------------------
    def _rutas_reglas(self) -> list[str]:
        rutas: list[str] = []
        for base in (os.path.join(config.carpeta_datos(), "yara"),
                     os.path.join(config.carpeta_activos(), "yara")):
            if os.path.isdir(base):
                for nombre in sorted(os.listdir(base)):
                    if nombre.lower().endswith((".yar", ".yara")):
                        ruta = os.path.join(base, nombre)
                        if ruta not in rutas:
                            rutas.append(ruta)
        return rutas

    def asegurar(self) -> EstadoMotor:
        if self._listo:
            return self.estado
        with self._candado:
            if self._listo:
                return self.estado
            self._listo = True
            rutas = self._rutas_reglas()
            self.estado.archivos_reglas = rutas
            if not rutas:
                self.estado.motivo = "sin_reglas"
                return self.estado
            error_x = ""
            try:
                import yara_x

                compilador = yara_x.Compiler()
                for ruta in rutas:
                    with open(ruta, "r", encoding="utf-8",
                              errors="replace") as fh:
                        compilador.add_source(fh.read())
                self._escaner = yara_x.Scanner(compilador.build())
                self.estado.disponible = True
                self.estado.motor = "yara-x"
                return self.estado
            except Exception as exc:  # sin módulo o reglas inválidas
                error_x = f"{type(exc).__name__}: {exc}"
            try:
                import yara

                espacios = {f"forge{i}": r for i, r in enumerate(rutas)}
                self._reglas_py = yara.compile(filepaths=espacios)
                self.estado.disponible = True
                self.estado.motor = "yara-python"
                return self.estado
            except Exception as exc:
                self.estado.motivo = (
                    f"yara-x: {error_x} | yara-python: "
                    f"{type(exc).__name__}: {exc}")
                return self.estado

    # -- escaneo ------------------------------------------------------------
    def escanear_datos(self, datos: bytes) -> list[CoincidenciaYara]:
        estado = self.asegurar()
        if not estado.disponible:
            return []
        salida: list[CoincidenciaYara] = []
        if self._escaner is not None:
            resultado = self._escaner.scan(datos)
            for regla in resultado.matching_rules:
                meta = dict(regla.metadata or {})
                salida.append(CoincidenciaYara(
                    regla=str(regla.identifier),
                    autor=str(meta.get("author", "") or ""),
                    licencia=str(meta.get("license", "") or ""),
                    descripcion=str(meta.get("description", "") or ""),
                    motor="yara-x"))
        elif self._reglas_py is not None:
            for m in self._reglas_py.match(data=datos):
                meta = m.meta or {}
                salida.append(CoincidenciaYara(
                    regla=str(m.rule),
                    autor=str(meta.get("author", "") or ""),
                    licencia=str(meta.get("license", "") or ""),
                    descripcion=str(meta.get("description", "") or ""),
                    motor="yara-python"))
        return salida

    def escanear_archivo(self, ruta: str) -> list[CoincidenciaYara]:
        try:
            with open(ruta, "rb") as fh:
                datos = fh.read(LIMITE_LECTURA)
        except OSError:
            return []
        return self.escanear_datos(datos)


_MOTOR = _Motor()


def estado_motor() -> EstadoMotor:
    return _MOTOR.asegurar()


def escanear_archivo(ruta: str) -> list[CoincidenciaYara]:
    return _MOTOR.escanear_archivo(ruta)


def escanear_datos(datos: bytes) -> list[CoincidenciaYara]:
    return _MOTOR.escanear_datos(datos)
