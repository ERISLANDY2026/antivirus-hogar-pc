"""Prueba de velocidad de internet (v1.0.2).

Mide contra el servicio público de Cloudflare (speed.cloudflare.com):
- ping: tiempo de ida y vuelta de una petición mínima.
- bajada: descarga de un bloque de bytes cronometrada → Mbps reales.

El `abridor` (url, timeout) -> bytes es inyectable para la suite: en la
app es urllib; en los tests, una función falsa con reloj controlado.
"""
import time
import urllib.request

_URL_PING = "https://speed.cloudflare.com/__down?bytes=0"
_URL_BAJADA = "https://speed.cloudflare.com/__down?bytes={n}"


def _abridor_real(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "AntivirusHogarPC"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def medir_velocidad(abridor=None, bytes_bajada: int = 3_000_000,
                    timeout: float = 30.0, reloj=time.monotonic) -> dict:
    """{ok, ping_ms, bajada_mbps, bytes} — ok=False si no hubo conexión."""
    abrir = abridor or _abridor_real
    try:
        t0 = reloj()
        abrir(_URL_PING, timeout)
        ping_ms = max(1, int(round((reloj() - t0) * 1000)))
    except Exception:
        return {"ok": False, "ping_ms": None, "bajada_mbps": 0.0, "bytes": 0}
    try:
        t0 = reloj()
        datos = abrir(_URL_BAJADA.format(n=bytes_bajada), timeout)
        segundos = reloj() - t0
    except Exception:
        return {"ok": False, "ping_ms": ping_ms, "bajada_mbps": 0.0, "bytes": 0}
    from .v102 import calcular_mbps

    return {
        "ok": True,
        "ping_ms": ping_ms,
        "bajada_mbps": calcular_mbps(len(datos), segundos),
        "bytes": len(datos),
    }
