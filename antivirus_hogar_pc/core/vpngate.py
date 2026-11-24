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


def _descargar_texto(url: str, timeout: int = 45) -> str:
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "AntivirusHogarPC"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def descargar_lista_servidores(url: str, timeout: int = 60) -> list[ServidorVPN]:
    """Descarga la lista pública de VPN Gate y la parsea.

    Lanza la excepción de red correspondiente si no se puede descargar;
    quien llama (la página, vía ui.services.seguro) la traduce a un
    ResultadoModulo con mensaje en español.
    """
    return parsear_csv_vpngate(_descargar_texto(url, timeout))


# --- Cadena con respaldo + semilla (v1.0.3, problema 5) ----------------------
# En la v1.0.2 la lista se pedía UNA sola vez al endpoint HTTPS principal.
# En un Windows real eso puede quedar vacío por: un corte TLS/conexión
# transitorio, la lentitud de vpngate.net (servidores en Japón), o una
# respuesta irreconocible — y no había ni reintento ni respaldo.
# Verificado desde el entorno de construcción el 2026-11-24: el endpoint
# HTTPS principal falló (conexión cortada) mientras el mismo API por
# HTTP respondió 200 con 99 servidores; por eso la cadena prueba las
# tres rutas, con reintento, antes de rendirse a la semilla.

def descargar_lista_con_respaldo(urls, timeout: int = 20,
                                 intentos_por_url: int = 1,
                                 descargador=None,
                                 dormir=None,
                                 plazo_total: float = 75.0,
                                 reloj=None) -> tuple[list[ServidorVPN], str]:
    """Prueba cada URL (con reintentos) hasta que una devuelva servidores.
    Devuelve (servidores, url_que_funciono). Si todas fallan, lanza
    RuntimeError con la causa del último intento. `descargador(url,
    timeout) -> texto`, `dormir(segundos)` y `reloj()` son inyectables
    para tests.

    PLAZO TOTAL (corrección v1.0.5, causa raíz del desplegable vacío):
    hasta la v1.0.4 la cadena no tenía límite global — 3 rutas × 2
    intentos × 45 s por operación de socket, y el `timeout` de urllib
    es POR OPERACIÓN: una conexión que gotea (hotspot inestable) lo
    estiraba sin fin, el hilo nunca volvía y ni la lista ni la semilla
    llegaban a la página. Ahora el conjunto entero tiene `plazo_total`
    segundos de reloj; cada intento recibe como timeout lo que quede
    de plazo, y agotado el plazo se lanza la excepción para que el
    respaldo (la semilla) entre al momento.
    """
    import time as _time

    bajar = descargador or _descargar_texto
    esperar = dormir if dormir is not None else _time.sleep
    ahora = reloj or _time.monotonic
    inicio = ahora()
    ultimo_error: Exception | None = None
    for url in urls:
        for intento in range(max(1, intentos_por_url)):
            restante = plazo_total - (ahora() - inicio)
            if restante <= 0:
                break
            try:
                servidores = parsear_csv_vpngate(
                    bajar(url, min(timeout, max(1.0, restante))))
                if servidores:
                    return servidores, url
                ultimo_error = RuntimeError(
                    "la respuesta de VPN Gate llegó vacía o en un formato "
                    "que no se pudo leer")
            except Exception as exc:  # red/TLS/timeout: a la siguiente ruta
                ultimo_error = exc
            if intento + 1 < max(1, intentos_por_url):
                esperar(min(1.5, max(0.0, plazo_total - (ahora() - inicio))))
    raise RuntimeError(str(ultimo_error) if ultimo_error else
                       "sin rutas de descarga configuradas")


def leer_semilla_vpngate(carpeta_activos: str) -> tuple[list[ServidorVPN], str]:
    """Lista SEMILLA incluida en la app (assets/vpngate_seed.csv):
    servidores REALES descargados de la API al construir la versión.
    Devuelve (servidores, fecha_de_la_descarga). Si el archivo no está
    o no parsea, devuelve ([], "")."""
    import os
    import re

    ruta = os.path.join(carpeta_activos, "vpngate_seed.csv")
    try:
        with open(ruta, encoding="utf-8", errors="replace") as f:
            texto = f.read()
    except OSError:
        return [], ""
    fecha = ""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", texto)
    if m:
        fecha = m.group(1)
    return parsear_csv_vpngate(texto), fecha


def paises_disponibles(servidores: list[ServidorVPN]) -> list[str]:
    return sorted({s.pais for s in servidores if s.pais})
