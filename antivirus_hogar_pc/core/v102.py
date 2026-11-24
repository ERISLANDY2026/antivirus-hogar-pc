"""Lógica pura de la v1.0.2 (sin Qt, sin Windows): porcentajes honestos,
impacto de programas de arranque, mapa de uso de disco y velocidad.

REGLA DE ORO del usuario: porcentaje SOLO donde se puede contar de
verdad (archivos revisados, drivers x de y, pasos de una operación).
Donde el sistema no expone un porcentaje real (la instalación de Windows
Update), se enseña la etapa y el conteo de pasos — NUNCA un % inventado.
"""


def porcentaje(parte: float, total: float) -> int | None:
    """% real 0-100; None si no hay total con el que contar (no inventar)."""
    if total is None or total <= 0:
        return None
    pct = int(round(100.0 * float(parte) / float(total)))
    return max(0, min(100, pct))


def texto_porcentaje(parte: float, total: float, unidad: str = "") -> str:
    """«37 % · 12 de 32 archivos». Sin total válido: «…» (la UI decide)."""
    pct = porcentaje(parte, total)
    if pct is None:
        return "…"
    sufijo = f" · {int(parte)} de {int(total)}"
    if unidad:
        sufijo += f" {unidad}"
    return f"{pct} %{sufijo}"


def texto_etapa(paso: int, total_pasos: int, etapa: str) -> str:
    """Progreso por pasos para operaciones sin % real (Windows Update):
    «Paso 2 de 3 · Instalando con Windows Update». Nunca un porcentaje."""
    return f"Paso {paso} de {total_pasos} · {etapa}"


# --- Impacto de los programas de arranque -------------------------------------
# Heurística honesta y explicable: programas conocidos por cargar mucho al
# arrancar (suites con actualizadores y residentes pesados) = alto; clientes
# y lanzadores medianos = medio; el resto = bajo. Se enseña el motivo.
_PESADOS = (
    "adobe", "acrobat", "creative cloud", "steam", "epic games", "battle.net",
    "battlenet", "itunes", "bonjour", "vmware", "virtualbox", "docker",
    "teams", "microsoft teams", "skype", "zoom", "webex",
)
_MEDIOS = (
    "spotify", "discord", "onedrive", "dropbox", "google drive", "googledrive",
    "telegram", "whatsapp", "office", "edge", "chrome", "firefox", "opera",
    "nvidia", "geforce", "realtek", "java", "update",
)


def clasificar_impacto_arranque(nombre: str, comando: str = "") -> tuple[str, str]:
    """(nivel, motivo): nivel en {"alto", "medio", "bajo"}."""
    texto = f"{nombre} {comando}".lower()
    for clave in _PESADOS:
        if clave in texto:
            return "alto", f"«{nombre}» carga varios procesos al arrancar."
    for clave in _MEDIOS:
        if clave in texto:
            return "medio", f"«{nombre}» deja un proceso residente al arrancar."
    return "bajo", f"«{nombre}» apenas carga al arrancar."


# --- Mapa de uso de disco -------------------------------------------------------
def mapa_desde_tamanos(tamanos: dict[str, int]) -> list[dict]:
    """[{nombre, bytes, pct}] ordenado de mayor a menor.

    pct es el % de cada carpeta SOBRE EL TOTAL MEDIDO (no sobre el disco):
    la UI lo dice así para no engañar."""
    total = sum(max(0, int(v)) for v in tamanos.values())
    salida = []
    for nombre, bytes_ in tamanos.items():
        b = max(0, int(bytes_))
        salida.append({
            "nombre": nombre,
            "bytes": b,
            "pct": porcentaje(b, total) if total else 0,
        })
    salida.sort(key=lambda d: d["bytes"], reverse=True)
    return salida


# --- Velocidad de internet --------------------------------------------------------
def calcular_mbps(bytes_recibidos: int, segundos: float) -> float:
    """Megabits por segundo de una descarga medida; 0 si no es medible."""
    if segundos <= 0 or bytes_recibidos <= 0:
        return 0.0
    return round(bytes_recibidos * 8 / segundos / 1_000_000, 1)


def valorar_velocidad(bajada_mbps: float) -> str:
    if bajada_mbps <= 0:
        return "No se pudo medir la velocidad de bajada."
    if bajada_mbps >= 100:
        return "Bajada excelente: sobra para vídeo 4K y descargas grandes."
    if bajada_mbps >= 25:
        return "Bajada buena: vídeo en alta definición sin problema."
    if bajada_mbps >= 5:
        return "Bajada justa: sirve para navegar y vídeo normal."
    return "Bajada lenta: las descargas y el vídeo en HD costarán."
