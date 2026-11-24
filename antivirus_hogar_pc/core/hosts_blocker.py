"""Bloqueador por archivo hosts gestionado.

La app escribe SOLO su bloque, marcado con comentarios propios
(«# === Antivirus Hogar INICIO/FIN ===»), conserva intacto el resto del
archivo hosts, hace copia de seguridad antes de tocarlo y puede quitar
todo dejando el hosts como estaba. Bloquea por DOMINIO (no por URL): es el
límite honesto de esta vía, sin certificado local.

La generación y el merge son lógica pura (probada en Linux); la escritura
del hosts real de Windows la hace winapi con elevación.
"""

MARCADOR_INICIO = "# === Antivirus Hogar INICIO (no editar a mano) ==="
MARCADOR_FIN = "# === Antivirus Hogar FIN ==="


def cargar_dominios(rutas: list[str]) -> list[str]:
    """Lee archivos de dominios (uno por línea, # = comentario)."""
    dominios: set[str] = set()
    import os

    for ruta in rutas:
        if not ruta or not os.path.isfile(ruta):
            continue
        with open(ruta, "r", encoding="utf-8", errors="replace") as f:
            for linea in f:
                d = linea.strip().lower()
                if not d or d.startswith("#"):
                    continue
                # En listas tipo hosts puede venir «0.0.0.0 dominio».
                partes = d.split()
                if len(partes) == 2 and partes[0] in ("0.0.0.0", "127.0.0.1"):
                    d = partes[1]
                if "." in d and " " not in d:
                    dominios.add(d)
    return sorted(dominios)


def generar_bloque(dominios: list[str]) -> str:
    lineas = [MARCADOR_INICIO]
    lineas += [f"0.0.0.0 {d}" for d in dominios]
    lineas.append(MARCADOR_FIN)
    return "\n".join(lineas) + "\n"


def bloque_activo(texto_hosts: str) -> bool:
    return MARCADOR_INICIO in texto_hosts


def quitar_bloque(texto_hosts: str) -> str:
    """Elimina el bloque de la app si existe; si no, devuelve el texto igual."""
    if not bloque_activo(texto_hosts):
        return texto_hosts
    salida: list[str] = []
    dentro = False
    for linea in texto_hosts.splitlines():
        if linea.strip() == MARCADOR_INICIO:
            dentro = True
            continue
        if linea.strip() == MARCADOR_FIN:
            dentro = False
            continue
        if not dentro:
            salida.append(linea)
    resultado = "\n".join(salida)
    if texto_hosts.endswith("\n") and not resultado.endswith("\n"):
        resultado += "\n"
    return resultado


def aplicar_bloque(texto_hosts: str, dominios: list[str]) -> str:
    """Texto del hosts con el bloque de la app (reemplaza uno anterior)."""
    limpio = quitar_bloque(texto_hosts)
    if limpio and not limpio.endswith("\n"):
        limpio += "\n"
    return limpio + generar_bloque(dominios)


def contar_bloqueados(texto_hosts: str) -> int:
    if not bloque_activo(texto_hosts):
        return 0
    n = 0
    dentro = False
    for linea in texto_hosts.splitlines():
        if linea.strip() == MARCADOR_INICIO:
            dentro = True
            continue
        if linea.strip() == MARCADOR_FIN:
            break
        if dentro and linea.startswith("0.0.0.0 "):
            n += 1
    return n
