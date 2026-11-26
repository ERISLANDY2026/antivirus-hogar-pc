"""Tarjeta «Pendientes» de Inicio (v1.0.16, frente 3): la lista
accionable de lo que necesita atención, calculada SOLO con
datos reales.

El anillo de salud ya decía el número; esta lista dice QUÉ:
cada pendiente nace de un dato comprobado (una revisión
guardada, el registro de actividad, el informe de salud, los
veredictos de la VPN, la tendencia del disco). Si un dato no
existe, su pendiente NO se enseña — nada de inventar «nunca»
donde la app simplemente no lo sabe: la única excepción es el
escaneo, donde «ningún escaneo registrado» SÍ es el dato (el
registro de actividad es la memoria de la app desde su
primera versión).

Lógica pura (sin Qt, sin Windows): la página recoge los datos
y aquí se decide la lista. Cada pendiente trae su destino de
navegación para que el botón de la tarjeta lleve a su pantalla.
"""
import time
from dataclasses import dataclass

DIAS_ESCANEO = 7        # sin escanear en una semana → pendiente
DIAS_OPTIMIZACION = 30  # sin optimizar en un mes → pendiente


@dataclass
class Pendiente:
    clave: str          # "escaneo" | "drivers" | "optimizar" | …
    destino: str        # id de página a la que navega su botón
    aviso: bool = False  # True = merece color de aviso (ámbar/rojo)
    dias: int | None = None
    cantidad: int | None = None


def _dias_desde(epoch: float | None, ahora: float) -> int | None:
    if not epoch:
        return None
    return max(0, int((ahora - float(epoch)) // 86400))


def calcular_pendientes(
        *, ahora: float | None = None,
        ultimo_escaneo: float | None = None,
        revision_drivers: dict | None = None,
        ultima_optimizacion: dict | None = None,
        actualizaciones_windows: int | None = None,
        vpn: dict | None = None,
        tendencia_disco: dict | None = None) -> list[Pendiente]:
    """La lista de pendientes con los datos disponibles.

    - ultimo_escaneo: epoch del último escaneo registrado
      (None = ninguno registrado nunca).
    - revision_drivers: dict de core.estado_mantenimiento
      (None = nunca se revisó: sin dato, no se enseña).
    - ultima_optimizacion: dict de core.estado_mantenimiento
      (None = sin dato: no se enseña).
    - actualizaciones_windows: nº de pendientes de Windows
      (None = no se pudo leer: no se enseña).
    - vpn: {"total": n, "verificados": m} de la lista vigente
      (None o total 0 = no aplica).
    - tendencia_disco: dict de core.historial_discos (solo
      pinta si viene «bajando»).
    """
    ahora = float(ahora if ahora is not None else time.time())
    pendientes: list[Pendiente] = []

    # Salud del disco bajando: el aviso más importante de la lista.
    if tendencia_disco and tendencia_disco.get("bajando"):
        pendientes.append(Pendiente(
            clave="disco_bajando", destino="discos", aviso=True,
            dias=tendencia_disco.get("dias")))

    dias = _dias_desde(ultimo_escaneo, ahora)
    if ultimo_escaneo is None:
        pendientes.append(Pendiente(
            clave="escaneo_nunca", destino="escaner", aviso=True))
    elif dias is not None and dias >= DIAS_ESCANEO:
        pendientes.append(Pendiente(
            clave="escaneo_viejo", destino="escaner", dias=dias))

    if revision_drivers and revision_drivers.get("confirmado", True):
        n = int(revision_drivers.get("desactualizados") or 0)
        if n > 0:
            pendientes.append(Pendiente(
                clave="drivers", destino="drivers", aviso=True,
                cantidad=n))

    if ultima_optimizacion and ultima_optimizacion.get("ok"):
        dias_opt = _dias_desde(ultima_optimizacion.get("cuando"), ahora)
        if dias_opt is not None and dias_opt >= DIAS_OPTIMIZACION:
            pendientes.append(Pendiente(
                clave="optimizar", destino="discos", dias=dias_opt))

    if actualizaciones_windows:
        pendientes.append(Pendiente(
            clave="windows", destino="actualizaciones", aviso=True,
            cantidad=int(actualizaciones_windows)))

    if vpn:
        total = int(vpn.get("total") or 0)
        verificados = int(vpn.get("verificados") or 0)
        if total > 0 and verificados < total:
            pendientes.append(Pendiente(
                clave="vpn_sin_verificar", destino="red",
                cantidad=total - verificados))

    return pendientes
