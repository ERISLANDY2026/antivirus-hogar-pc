"""VPN Gate en Windows: delegación en SoftEther VPN Client u OpenVPN Connect.

La app genera el .ovpn desde la API de VPN Gate y lo abre con el cliente
instalado. No implementa el túnel (eso exigiría un driver firmado).
"""
import os
import subprocess
import sys

from . import WindowsNoDisponible, es_windows

RUTAS_SOFTETHER = [
    r"C:\Program Files\SoftEther VPN Client\vpncmgr.exe",
    r"C:\Program Files (x86)\SoftEther VPN Client\vpncmgr.exe",
]
RUTAS_OPENVPN_CONNECT = [
    r"C:\Program Files\OpenVPN Connect\OpenVPNConnect.exe",
    r"C:\Program Files (x86)\OpenVPN Connect\OpenVPNConnect.exe",
]
RUTAS_OPENVPN_GUI = [
    r"C:\Program Files\OpenVPN\bin\openvpn-gui.exe",
]


def clientes_vpn_instalados() -> list[dict]:
    """Clientes VPN conocidos presentes en el equipo."""
    encontrados = []
    for nombre, rutas in (
        ("SoftEther VPN Client (recomendado por VPN Gate)", RUTAS_SOFTETHER),
        ("OpenVPN Connect", RUTAS_OPENVPN_CONNECT),
        ("OpenVPN GUI (Community)", RUTAS_OPENVPN_GUI),
    ):
        for ruta in rutas:
            if os.path.isfile(ruta):
                encontrados.append({"nombre": nombre, "ruta": ruta})
                break
    return encontrados


def guardar_ovpn(contenido: str, carpeta: str, nombre_archivo: str) -> str:
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, nombre_archivo)
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(contenido)
    return ruta


def abrir_perfil_vpn(ruta_ovpn: str, ruta_cliente: str = "") -> bool:
    """Abre el .ovpn con el cliente elegido (o con la asociación de Windows)."""
    if not es_windows():
        raise WindowsNoDisponible("La delegación VPN se hace en Windows.")
    try:
        if ruta_cliente and os.path.isfile(ruta_cliente):
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen([ruta_cliente, ruta_ovpn], creationflags=flags)
        else:
            os.startfile(ruta_ovpn)  # noqa: S606 - abre el cliente asociado
        return True
    except OSError:
        return False


def ip_publica_actual(timeout: int = 15) -> str:
    """IP pública actual (para enseñar el cambio tras conectar la VPN)."""
    import urllib.request

    try:
        req = urllib.request.Request("https://api.ipify.org", headers={"User-Agent": "AntivirusHogarPC"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("ascii", errors="replace").strip()
    except Exception:
        return ""


def carpeta_perfiles_vpn() -> str:
    from .. import config

    ruta = os.path.join(config.carpeta_datos(), "vpn")
    os.makedirs(ruta, exist_ok=True)
    return ruta


_ = sys  # (compatibilidad de imports en empaquetado)
