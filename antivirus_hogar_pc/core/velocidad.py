"""Prueba de velocidad de internet (v1.0.2; en vivo en v1.0.5).

Mide contra el servicio público de Cloudflare (speed.cloudflare.com):
- ping: tiempo de ida y vuelta de una petición mínima.
- bajada: descarga de un bloque de bytes cronometrada → Mbps reales.

Fuente elegida (v1.0.5): los endpoints oficiales de la prueba de
velocidad de Cloudflare — `__down?bytes=N` para descargar y `__up`
para subir. Son públicos, sin clave ni registro, los mantiene
Cloudflare para su propia herramienta speed.cloudflare.com y devuelven
bytes arbitrarios a la carta: ideales para medir sin cuentas ni
servicios de terceros dudosos. (LibreSpeed exigiría localizar un
servidor público concreto y su disponibilidad varía.)

El `abridor` (url, timeout) -> bytes es inyectable para la suite: en la
app es urllib; en los tests, una función falsa con reloj controlado.
La medición EN VIVO (medir_velocidad_en_vivo) usa un `transporte`
inyectable con descargar/subir por bloques y emite el progreso
mientras transfiere: primero la bajada y después la subida.
"""
import http.client
import io
import time
import urllib.request

_URL_PING = "https://speed.cloudflare.com/__down?bytes=0"
_URL_BAJADA = "https://speed.cloudflare.com/__down?bytes={n}"
_URL_SUBIDA = "https://speed.cloudflare.com/__up"
_HOST_MEDICION = "speed.cloudflare.com"


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


# --- Medición EN VIVO (v1.0.5) -------------------------------------------------
#
# Hasta la v1.0.4 el botón «Medir velocidad» solo enseñaba el resultado
# final (y en la práctica el usuario lo veía «sin hacer nada» durante
# la medición, sin subida siquiera). Ahora la transferencia va por
# bloques y al_progreso(fase, mbps) se llama DURANTE la medición:
# primero ("bajada", …) y después ("subida", …), para pintar los
# valores en la app mientras se mide, no solo al final.

class _LectorContador(io.RawIOBase):
    """Cuerpo de subida que avisa de cada bloque leído por http.client."""

    def __init__(self, datos: bytes, al_bloque):
        super().__init__()
        self._buf = io.BytesIO(datos)
        self._al_bloque = al_bloque
        self.enviados = 0

    def readable(self) -> bool:
        return True

    def read(self, n: int = -1) -> bytes:
        bloque = self._buf.read(n if n and n > 0 else 8192)
        self.enviados += len(bloque)
        if bloque:
            self._al_bloque(self.enviados)
        return bloque

    def __len__(self) -> int:
        return self._buf.getbuffer().nbytes


class _TransporteCloudflare:
    """Transporte real contra speed.cloudflare.com, por bloques."""

    def descargar(self, url: str, timeout: float, al_bloque) -> int:
        req = urllib.request.Request(
            url, headers={"User-Agent": "AntivirusHogarPC"})
        total = 0
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            while True:
                bloque = resp.read(65536)
                if not bloque:
                    break
                total += len(bloque)
                al_bloque(total)
        return total

    def subir(self, url: str, datos: bytes, timeout: float, al_bloque) -> int:
        lector = _LectorContador(datos, al_bloque)
        conexion = http.client.HTTPSConnection(_HOST_MEDICION,
                                               timeout=timeout)
        try:
            conexion.request("POST", "/__up", body=lector, headers={
                "User-Agent": "AntivirusHogarPC",
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(datos)),
            })
            respuesta = conexion.getresponse()
            respuesta.read()
            if respuesta.status >= 400:
                raise OSError(f"Cloudflare respondió HTTP {respuesta.status}")
        finally:
            conexion.close()
        return lector.enviados


def medir_velocidad_en_vivo(al_progreso=None, bytes_bajada: int = 10_000_000,
                            bytes_subida: int = 3_000_000,
                            timeout: float = 60.0, transporte=None,
                            reloj=time.monotonic) -> dict:
    """Mide ping, BAJADA y SUBIDA emitiendo el progreso en vivo.

    al_progreso(fase, mbps_actual): fase «bajada» o «subida»; se llama
    periódicamente durante cada transferencia con la velocidad media
    hasta ese instante y una última vez con el valor final de la fase.

    Devuelve {ok, ping_ms, bajada_mbps, subida_mbps, bytes_bajada,
    bytes_subida, causa}. ok=False (con la causa) si algo falla: sin
    conexión no se inventan números.
    """
    from .v102 import calcular_mbps

    trans = transporte or _TransporteCloudflare()
    emitir = al_progreso or (lambda _fase, _mbps: None)

    def _medir_fase(fase: str, accion) -> tuple[int, float]:
        """accion(al_bloque) -> bytes transferidos; emite en vivo."""
        t0 = reloj()
        ultimo_aviso = [0.0]

        def al_bloque(acumulado: int) -> None:
            ahora = reloj()
            if ahora - ultimo_aviso[0] >= 0.15 or acumulado == 0:
                ultimo_aviso[0] = ahora
                emitir(fase, calcular_mbps(acumulado, max(ahora - t0, 1e-9)))

        total = accion(al_bloque)
        segundos = max(reloj() - t0, 1e-9)
        final = calcular_mbps(total, segundos)
        emitir(fase, final)
        return total, final

    try:
        t0 = reloj()
        trans.descargar(_URL_PING, min(timeout, 15.0), lambda _n: None)
        ping_ms = max(1, int(round((reloj() - t0) * 1000)))
    except Exception as exc:
        return {"ok": False, "ping_ms": None, "bajada_mbps": 0.0,
                "subida_mbps": 0.0, "bytes_bajada": 0, "bytes_subida": 0,
                "causa": f"Sin respuesta de {_HOST_MEDICION}: {exc}"}
    try:
        n_bajada, bajada = _medir_fase(
            "bajada",
            lambda al_bloque: trans.descargar(
                _URL_BAJADA.format(n=bytes_bajada), timeout, al_bloque))
        cuerpo = b"\0" * bytes_subida
        n_subida, subida = _medir_fase(
            "subida",
            lambda al_bloque: trans.subir(_URL_SUBIDA, cuerpo, timeout,
                                          al_bloque))
    except Exception as exc:
        return {"ok": False, "ping_ms": ping_ms, "bajada_mbps": 0.0,
                "subida_mbps": 0.0, "bytes_bajada": 0, "bytes_subida": 0,
                "causa": f"La medición se cortó: {exc}"}
    return {"ok": True, "ping_ms": ping_ms, "bajada_mbps": bajada,
            "subida_mbps": subida, "bytes_bajada": n_bajada,
            "bytes_subida": n_subida, "causa": ""}
