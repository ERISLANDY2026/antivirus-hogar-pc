"""CONTRATOS CONGELADOS — Ola 0 (2026-11-24). NO cambiar sin el integrador.

Todo intercambio entre módulos usa estas formas. Las páginas se construyen
contra estos dataclasses (con datos fake de cada módulo) y las
implementaciones reales deben devolver exactamente esto.

Reglas:
- Ningún dataclass de contrato importa Qt ni hace llamadas al sistema.
- Los errores viajan en ResultadoModulo, no como excepciones a la UI.
- Los tipos ya existentes en core/ se re-exportan aquí: ESTA es la puerta.
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# --- Tipos de core que quedan congelados como contrato ----------------------
from .core.drivers_logic import DriverInstalado, EstadoDriver  # noqa: F401
from .core.health import EstadoSalud, ResultadoSalud  # noqa: F401
from .core.scanner import Hallazgo, ResultadoEscaneo  # noqa: F401
from .core.vpngate import ServidorVPN  # noqa: F401
from .core.wifi_parse import InfoWifi  # noqa: F401
from .core.winget_parse import ProgramaDesactualizado  # noqa: F401
from .core.watch_logic import ProgramaInstalado  # noqa: F401


# --- Sobre genérico de resultado ----------------------------------------------
@dataclass
class ResultadoModulo:
    """Toda operación de módulo devuelve esto (nunca lanza a la UI)."""
    ok: bool
    mensaje: str = ""          # frase en español llano para el usuario
    datos: Any = None          # el dataclass de contrato que corresponda
    detalle_tecnico: str = ""  # para «Ver detalles», nunca en la vista principal


# --- Panel de salud (Carril A; datos de sistema vía psutil) --------------------
@dataclass
class DatosPanel:
    cpu_pct: float | None = None
    ram_pct: float | None = None
    ram_usada_gb: float | None = None
    ram_total_gb: float | None = None
    disco_sistema_pct: float | None = None
    disco_libre_gb: float | None = None
    disco_total_gb: float | None = None
    tiempo_encendido_h: float | None = None


@dataclass
class InformeSalud:
    """Lo que pinta la pantalla de Inicio."""
    salud: ResultadoSalud                 # puntuación explicada (core.health)
    defender: dict = field(default_factory=dict)   # winapi.defender.estado_defender()
    firewall_activo: bool | None = None
    actualizaciones_windows: int | None = None     # nº pendientes
    windows_sin_soporte: bool = False              # Win10 sin ESU
    cfa: dict = field(default_factory=dict)        # winapi.defender.estado_cfa()
    panel: DatosPanel = field(default_factory=DatosPanel)
    ultimo_escaneo: dict = field(default_factory=dict)


# --- SMART (Carril C; fuente: pySMART/smartctl o Get-PhysicalDisk) -------------
@dataclass
class SmartInfo:
    disco: str                       # nombre/modelo
    tipo: str = ""                   # SSD | HDD | NVMe | ""
    salud: str = "desconocido"       # "bien" | "regular" | "mal" | "desconocido"
    temperatura_c: int | None = None
    horas_encendido: int | None = None
    desgaste_pct: int | None = None  # SSD: % de vida consumida
    errores: int | None = None
    sin_datos: bool = False          # True = «no se puede leer» (USB/RAID), NUNCA «sano»
    detalle: str = ""


# --- Bloqueador hosts (Carril B) -------------------------------------------------
@dataclass
class HostsEstado:
    activo: bool = False
    dominios_bloqueados: int = 0
    base_usada: str = "semilla"      # "semilla" (19.563, por defecto) | "fusionada" (100.776)
    ruta_respaldo: str = ""          # copia del hosts previo, si la hay
    dns_reforzado: bool = False


# --- Tune-up (Carril C; psutil + shell de Windows) --------------------------------
@dataclass
class PartidaLimpieza:
    nombre: str
    ruta: str
    tamano: int = 0                  # bytes


@dataclass
class InformeTuneUp:
    partidas: list[PartidaLimpieza] = field(default_factory=list)
    papelera_bytes: int = 0

    @property
    def total_bytes(self) -> int:
        return sum(p.tamano for p in self.partidas) + self.papelera_bytes


# --- Actualizaciones de Windows (Carril D; COM Microsoft.Update.Session) ---------
@dataclass
class ActualizacionWindows:
    titulo: str
    descargada: bool = False
    requiere_reinicio: bool = False
    es_driver: bool = False


# --- Contexto que recibe cada página ------------------------------------------------
@dataclass
class ContextoModulo:
    """Lo único que una página necesita del resto de la app.

    `servicios` es ui.services.ServiciosApp (firmas, caché, cuarentena,
    ajustes). Las páginas NO importan main_window ni otros módulos.
    """
    servicios: Any = None
    al_navegar: Optional[Callable[[str], None]] = None  # ir a otro módulo por id


# --- Registro declarativo de módulos ---------------------------------------------------
@dataclass(frozen=True)
class RegistroModulo:
    id: str            # único, minúsculas con guiones: "panel", "escaner", …
    titulo: str        # texto de navegación, en español
    icono: str         # nombre en ui.icons._SVG
    orden: int         # posición en la barra lateral
    carril: str        # "A" | "B" | "C" | "D"  (propietario del código)
    ola: int           # 1 = v1 instalable · 2 · 3
    pagina: str        # "paquete.modulo:funcion" — crear_pagina(ctx) -> QWidget


VERSION_CONTRATOS = "1.0-ola0"
