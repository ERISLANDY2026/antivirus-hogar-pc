"""VPN Gate: parseo de su API pública CSV y generación de perfiles .ovpn.

La API (https://www.vpngate.net/api/iphone/) devuelve un CSV con comentarios
«*…», una cabecera que empieza por «#» y una fila por servidor; la última
columna trae la configuración OpenVPN en Base64. La app NO implementa el
túnel: genera el .ovpn y lo delega a SoftEther VPN Client u OpenVPN Connect.

Aviso honesto (también en la UI): los servidores son de VOLUNTARIOS; el
operador puede registrar la conexión. No usar para banca ni anonimato.
"""
import base64
import csv
import io
from dataclasses import dataclass


@dataclass
class ServidorVPN:
    hostname: str
    ip: str
    puntuacion: int
    ping_ms: int
    velocidad_bps: int
    pais: str
    pais_corto: str
    sesiones: int
    uptime: int
    total_usuarios: int
    operador: str
    mensaje: str
    ovpn_base64: str

    @property
    def velocidad_mbps(self) -> float:
        return self.velocidad_bps / 1_000_000

    def generar_ovpn(self) -> str:
        datos = base64.b64decode(self.ovpn_base64)
        return datos.decode("utf-8", errors="replace")


def _entero(texto: str, defecto: int = 0) -> int:
    try:
        return int(str(texto).strip())
    except (ValueError, TypeError):
        return defecto


def parsear_csv_vpngate(texto: str) -> list[ServidorVPN]:
    """Parsea la respuesta de la API de VPN Gate. Tolera comas extra en el
    campo Message (se recompone) y líneas de comentario «*»."""
    lineas_utiles: list[str] = []
    for linea in texto.splitlines():
        if not linea.strip():
            continue
        if linea.startswith("*"):
            continue
        if linea.startswith("#"):
            linea = linea[1:]
        lineas_utiles.append(linea)
    if not lineas_utiles:
        return []
    lector = csv.reader(io.StringIO("\n".join(lineas_utiles)))
    filas = list(lector)
    if not filas:
        return []
    servidores: list[ServidorVPN] = []
    for fila in filas[1:]:  # la primera es la cabecera
        if len(fila) < 15:
            continue
        if len(fila) > 15:
            # Message con comas sin entrecomillar: recomponer y dejar el
            # Base64 (última columna) intacto.
            fila = fila[:13] + [",".join(fila[13:-1])] + [fila[-1]]
        servidores.append(
            ServidorVPN(
                hostname=fila[0].strip(),
                ip=fila[1].strip(),
                puntuacion=_entero(fila[2]),
                ping_ms=_entero(fila[3], 9999),
                velocidad_bps=_entero(fila[4]),
                pais=fila[5].strip(),
                pais_corto=fila[6].strip(),
                sesiones=_entero(fila[7]),
                uptime=_entero(fila[8]),
                total_usuarios=_entero(fila[9]),
                operador=fila[12].strip(),
                mensaje=fila[13].strip(),
                ovpn_base64=fila[14].strip(),
            )
        )
    return servidores


def ordenar_servidores(servidores: list[ServidorVPN], criterio: str = "velocidad") -> list[ServidorVPN]:
    if criterio == "ping":
        return sorted(servidores, key=lambda s: (s.ping_ms, -s.velocidad_bps))
    if criterio == "puntuacion":
        return sorted(servidores, key=lambda s: -s.puntuacion)
    if criterio == "sesiones":
        return sorted(servidores, key=lambda s: (s.sesiones, -s.velocidad_bps))
    if criterio == "pais":
        return sorted(servidores, key=lambda s: (s.pais.lower(), -s.velocidad_bps))
    return sorted(servidores, key=lambda s: -s.velocidad_bps)


def descargar_lista_servidores(url: str, timeout: int = 60) -> list[ServidorVPN]:
    """Descarga la lista pública de VPN Gate y la parsea.

    Lanza la excepción de red correspondiente si no se puede descargar;
    quien llama (la página, vía ui.services.seguro) la traduce a un
    ResultadoModulo con mensaje en español.
    """
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "AntivirusHogarPC"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        texto = resp.read().decode("utf-8", errors="replace")
    return parsear_csv_vpngate(texto)


def paises_disponibles(servidores: list[ServidorVPN]) -> list[str]:
    return sorted({s.pais for s in servidores if s.pais})
