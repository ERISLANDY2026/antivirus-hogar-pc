"""Configuración y rutas de Antivirus Hogar PC.

Sin dependencias de Qt ni de Windows: se puede importar en cualquier
plataforma (las pruebas unitarias lo usan en Linux).
"""
import os
import sys

APP_ID = "AntivirusHogarPC"
VERSION = "1.0.18"

# ---------------------------------------------------------------------------
# Canal de actualización propio (mismo esquema que en Android: un
# version-pc.json publicado en la carpeta «Antivirus Hogar PC» de Drive).
# La URL se puede cambiar en Ajustes; si está vacía, la app avisa de que el
# canal aún no está configurado en vez de fallar.
# ---------------------------------------------------------------------------
UPDATE_VERSION_URL = "https://drive.usercontent.google.com/download?id=1Kfd_pELWJhp37fO1iaERdSIzpRkAqK4R&export=download"

# Fuentes de inteligencia de amenazas (abuse.ch). La API exige Auth-Key
# gratuita desde 2025; la clave la crea el usuario una vez y se guarda en
# Ajustes. Los exports públicos se usan sin clave cuando están disponibles.
MALWAREBAZAAR_API = "https://mb-api.abuse.ch/api/v1/"
URLHAUS_HOSTFILE = "https://urlhaus.abuse.ch/downloads/hostfile/"
OPENPHISH_FEED = "https://openphish.com/feed.txt"
VPNGATE_API = "https://www.vpngate.net/api/iphone/"
# Cadena de rutas del API de VPN Gate (v1.0.3): la principal HTTPS, la
# HTTPS sin «www» y la HTTP del mismo servicio oficial. Verificado en
# construcción: cuando la HTTPS principal corta, la HTTP responde.
# v1.0.14: cuarta ruta, el ESPEJO público en GitHub (la misma lista
# oficial republicada dos veces por hora, con las configs completas):
# misma data y mismas credenciales, un camino más si el sitio
# oficial cae entero (INVESTIGACION-FUENTES-VPN-EXTRA.md).
VPNGATE_APIS = (
    "https://www.vpngate.net/api/iphone/",
    "https://vpngate.net/api/iphone/",
    "http://www.vpngate.net/api/iphone/",
    "https://cdn.jsdelivr.net/gh/GeorgeXie2333/vpngate-list-mirror@latest/data/vpngate.csv",
)

# DNS filtrantes ofrecidos en el modo reforzado del bloqueador.
DNS_FILTRANTES = {
    "AdGuard DNS (anuncios y rastreo)": ("94.140.14.14", "94.140.15.15"),
    "Quad9 (malware)": ("9.9.9.9", "149.112.112.112"),
}


def carpeta_activos() -> str:
    """Carpeta de activos (semillas). Funciona en fuente y en PyInstaller."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        candidata = os.path.join(base, "antivirus_hogar_pc", "assets")
        if os.path.isdir(candidata):
            return candidata
        return os.path.join(base, "assets")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def carpeta_datos() -> str:
    """Datos del usuario: %LOCALAPPDATA%\\AntivirusHogarPC en Windows."""
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    ruta = os.path.join(base, APP_ID)
    os.makedirs(ruta, exist_ok=True)
    return ruta


def ruta_bd_cache() -> str:
    return os.path.join(carpeta_datos(), "cache_escaneo.sqlite3")


def ruta_cuarentena() -> str:
    ruta = os.path.join(carpeta_datos(), "cuarentena")
    os.makedirs(ruta, exist_ok=True)
    return ruta


def ruta_informes() -> str:
    ruta = os.path.join(carpeta_datos(), "informes")
    os.makedirs(ruta, exist_ok=True)
    return ruta


def ruta_respaldos() -> str:
    ruta = os.path.join(carpeta_datos(), "respaldos")
    os.makedirs(ruta, exist_ok=True)
    return ruta


def ruta_actividad() -> str:
    return os.path.join(carpeta_datos(), "actividad.jsonl")


def ruta_cache_fuentes_vpn() -> str:
    """v1.0.14: la caché en disco de la lista VPN fusionada buena
    (fuentes verificadas + veredictos de la sonda)."""
    return os.path.join(carpeta_datos(), "vpn_fuentes_cache.json")


def ruta_estado_fuentes_vpn() -> str:
    """v1.0.14: el estado/cadencia del refresco de fuentes VPN."""
    return os.path.join(carpeta_datos(), "vpn_fuentes_estado.json")
