"""Parseo de `netsh wlan show interfaces` (español o inglés) y valoración.

netsh localiza las claves según el idioma del sistema; se aceptan ambas.
La valoración es en lenguaje llano: cifrado abierto/WEP/WPA antiguo = débil.
"""
from dataclasses import dataclass


@dataclass
class InfoWifi:
    nombre: str = ""
    ssid: str = ""
    autenticacion: str = ""
    cifrado: str = ""
    senal_pct: int | None = None
    banda: str = ""
    canal: str = ""
    tipo_radio: str = ""

    @property
    def conectada(self) -> bool:
        return bool(self.ssid)


_CLAVES = {
    "nombre": ("Nombre", "Name"),
    "ssid": ("SSID",),
    "autenticacion": ("Autenticación", "Autentificación", "Authentication"),
    "cifrado": ("Cifrado", "Cipher"),
    "senal": ("Señal", "Signal"),
    "banda": ("Banda", "Band"),
    "canal": ("Canal", "Channel"),
    "tipo_radio": ("Tipo de radio", "Radio type"),
}


def parsear_netsh_wlan(texto: str) -> InfoWifi:
    info = InfoWifi()
    for linea in texto.splitlines():
        if ":" not in linea:
            continue
        clave, _, valor = linea.partition(":")
        clave = clave.strip()
        valor = valor.strip()
        for campo, nombres in _CLAVES.items():
            if clave in nombres:
                if campo == "senal":
                    numero = "".join(c for c in valor if c.isdigit())
                    info.senal_pct = int(numero) if numero else None
                else:
                    setattr(info, campo if campo != "senal" else "senal_pct", valor)
                break
    return info


def parsear_perfiles_guardados(texto: str) -> list[str]:
    """Nombres de redes guardadas de `netsh wlan show profiles` (es/en)."""
    perfiles: list[str] = []
    for linea in texto.splitlines():
        if ":" not in linea:
            continue
        clave, _, valor = linea.partition(":")
        clave = clave.strip().lower()
        if "perfil" in clave or "profile" in clave:
            nombre = valor.strip()
            if nombre and nombre not in perfiles:
                perfiles.append(nombre)
    return perfiles


def valorar_wifi(info: InfoWifi) -> tuple[str, str]:
    """(nivel, frase): nivel = "bien" | "regular" | "mal" | "sin_datos"."""
    if not info.conectada:
        return "sin_datos", "No hay ninguna red Wi-Fi conectada ahora mismo."
    aut = info.autenticacion.lower()
    if "abierta" in aut or "open" in aut:
        return "mal", "Esta red Wi-Fi está ABIERTA: cualquiera puede ver el tráfico. Evita banca y compras."
    if "wep" in aut:
        return "mal", "Esta red usa WEP, un cifrado roto hace años: cámbialo en el router a WPA2 o WPA3."
    if aut.startswith("wpa-") or "wpa personal" in aut or aut == "wpa":
        return "regular", "Esta red usa WPA (primera versión): mejorable a WPA2/WPA3 en el router."
    if "wpa2" in aut or "wpa3" in aut:
        return "bien", f"Red protegida con {info.autenticacion}: correcto."
    return "regular", f"Autenticación «{info.autenticacion}»: no se ha podido valorar con seguridad."
