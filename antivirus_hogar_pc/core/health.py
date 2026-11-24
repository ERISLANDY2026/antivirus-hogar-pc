"""Puntuación de salud del equipo (0–100), siempre explicada.

Composición transparente (la de la investigación, patrón «Security Advisor»):
  Defender activo y al día .... 30
  Firewall activo ............. 15
  Windows al día / con ESU .... 15
  Carpetas anti-ransomware .... 10
  Sin hallazgos recientes ..... 15
  Disco sano .................. 10
  Arranque limpio .............. 5

Los componentes sin datos no restan: se excluyen del máximo y se dice.
Nunca una cifra sin el porqué: cada punto perdido lleva su motivo en español.
"""
from dataclasses import dataclass, field


@dataclass
class EstadoSalud:
    defender_activo: bool | None = None
    defender_firmas_al_dia: bool | None = None
    firewall_activo: bool | None = None
    windows_al_dia: bool | None = None      # sin actualizaciones pendientes
    windows_con_soporte: bool | None = None  # Win11, o Win10 con ESU
    cfa_activo: bool | None = None          # True si activado o en auditoría
    hallazgos_recientes: int | None = None  # 0 = limpio
    disco_sano: bool | None = None
    entradas_arranque: int | None = None    # <= umbral = limpio


@dataclass
class ResultadoSalud:
    puntuacion: int
    maximo_conocido: int
    motivos: list[str] = field(default_factory=list)   # por qué no es 100
    aciertos: list[str] = field(default_factory=list)  # lo que está bien


UMBRAL_ARRANQUE_LIMPIO = 12


def calcular_salud(estado: EstadoSalud) -> ResultadoSalud:
    puntos = 0
    maximo = 0
    motivos: list[str] = []
    aciertos: list[str] = []

    # Defender (30): 20 por activo + 10 por firmas al día
    if estado.defender_activo is not None:
        maximo += 20
        if estado.defender_activo:
            puntos += 20
            aciertos.append("Microsoft Defender está activo.")
        else:
            motivos.append("Microsoft Defender está DESACTIVADO: es tu protección en tiempo real.")
    if estado.defender_firmas_al_dia is not None:
        maximo += 10
        if estado.defender_firmas_al_dia:
            puntos += 10
            aciertos.append("Las firmas de Defender están al día.")
        else:
            motivos.append("Las firmas de Defender están atrasadas.")

    # Firewall (15)
    if estado.firewall_activo is not None:
        maximo += 15
        if estado.firewall_activo:
            puntos += 15
            aciertos.append("El firewall de Windows está activo.")
        else:
            motivos.append("El firewall de Windows está desactivado en algún perfil.")

    # Windows (15): 8 por estar al día + 7 por tener soporte/ESU
    if estado.windows_al_dia is not None:
        maximo += 8
        if estado.windows_al_dia:
            puntos += 8
            aciertos.append("Windows no tiene actualizaciones pendientes.")
        else:
            motivos.append("Hay actualizaciones de Windows pendientes de instalar.")
    if estado.windows_con_soporte is not None:
        maximo += 7
        if estado.windows_con_soporte:
            puntos += 7
        else:
            motivos.append("Este Windows ya no recibe parches de seguridad (fin de soporte).")

    # CFA anti-ransomware (10)
    if estado.cfa_activo is not None:
        maximo += 10
        if estado.cfa_activo:
            puntos += 10
            aciertos.append("La protección de carpetas contra ransomware está activa.")
        else:
            motivos.append("La protección de carpetas contra ransomware está desactivada.")

    # Sin hallazgos (15)
    if estado.hallazgos_recientes is not None:
        maximo += 15
        if estado.hallazgos_recientes == 0:
            puntos += 15
            aciertos.append("Sin hallazgos en los escaneos recientes.")
        else:
            motivos.append(f"Hay {estado.hallazgos_recientes} hallazgo(s) reciente(s) sin resolver.")

    # Disco (10)
    if estado.disco_sano is not None:
        maximo += 10
        if estado.disco_sano:
            puntos += 10
            aciertos.append("El disco principal está sano.")
        else:
            motivos.append("El disco principal reporta problemas de salud: haz copia ya.")

    # Arranque (5)
    if estado.entradas_arranque is not None:
        maximo += 5
        if estado.entradas_arranque <= UMBRAL_ARRANQUE_LIMPIO:
            puntos += 5
            aciertos.append("El arranque no está sobrecargado.")
        else:
            motivos.append(f"Hay {estado.entradas_arranque} programas que arrancan con Windows.")

    if maximo == 0:
        return ResultadoSalud(0, 0, ["Aún no hay datos suficientes para puntuar."], [])
    puntuacion = round(100 * puntos / maximo)
    return ResultadoSalud(puntuacion, maximo, motivos, aciertos)
