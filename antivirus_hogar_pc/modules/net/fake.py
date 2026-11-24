"""Datos fake del Carril D (Ola 0)."""
import base64

from antivirus_hogar_pc.contracts import ActualizacionWindows
from antivirus_hogar_pc.core.vpngate import ServidorVPN
from antivirus_hogar_pc.core.wifi_parse import InfoWifi
from antivirus_hogar_pc.core.winget_parse import ProgramaDesactualizado

_OVPN_FAKE = base64.b64encode(
    b"client\ndev tun\nproto udp\nremote ejemplo.vpngate.net 1194\n").decode()


def servidores_fake() -> list[ServidorVPN]:
    return [
        ServidorVPN("vpn123456789.opengw.net", "203.0.113.10", 812345, 18, 450_000_000,
                    "Japan", "JP", 12, 123456, 3400, "voluntario-ejemplo", "", _OVPN_FAKE),
        ServidorVPN("vpn987654321.opengw.net", "198.51.100.7", 640120, 95, 210_000_000,
                    "United States", "US", 30, 98765, 8900, "voluntario-ejemplo", "", _OVPN_FAKE),
    ]


def wifi_fake() -> InfoWifi:
    return InfoWifi(nombre="Wi-Fi", ssid="CasaGuerra", autenticacion="WPA2-Personal",
                    cifrado="CCMP", senal_pct=82, banda="5 GHz", canal="44",
                    tipo_radio="802.11ac")


def winget_fake() -> list[ProgramaDesactualizado]:
    return [
        ProgramaDesactualizado("VLC media player", "VideoLAN.VLC", "3.0.20", "3.0.21", "winget"),
        ProgramaDesactualizado("7-Zip", "7zip.7zip", "23.01", "24.09", "winget"),
    ]


def windows_update_fake() -> list[ActualizacionWindows]:
    return [
        ActualizacionWindows("Actualización acumulativa para Windows 10 (KB5060000)", False, True),
        ActualizacionWindows("Definiciones de seguridad de Microsoft Defender", True, False),
        ActualizacionWindows("Realtek — Net — 10.60.615.2023", False, False, es_driver=True),
    ]
