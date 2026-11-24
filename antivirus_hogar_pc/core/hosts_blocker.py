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


def _es_entrada_bloque(linea: str) -> bool:
    """True si la línea tiene la forma de una entrada del bloque
    («0.0.0.0 dominio»): la escribe SOLO generar_bloque."""
    partes = linea.strip().split()
    return len(partes) == 2 and partes[0] == "0.0.0.0" and "." in partes[1]


def analizar_bloque(texto_hosts: str) -> dict:
    """Salud de la sección propia dentro del hosts (v1.0.6).

    Devuelve {presente, danado, motivo}: «danado» cubre los estados en
    los que quitar_bloque clásico ya no basta — marcador de inicio sin
    su fin (bloque truncado, p. ej. una escritura cortada a mitad),
    marcador de fin huérfano, marcadores duplicados o invertidos. Esos
    estados son los que dejaron a la PC del usuario sin navegación el
    2026-11-24 y sin forma de repararlos desde la propia app.
    """
    inicios: list[int] = []
    fines: list[int] = []
    for i, linea in enumerate(texto_hosts.splitlines()):
        limpia = linea.strip()
        if limpia == MARCADOR_INICIO:
            inicios.append(i)
        elif limpia == MARCADOR_FIN:
            fines.append(i)
    presente = bool(inicios or fines)
    if not presente:
        return {"presente": False, "danado": False, "motivo": ""}
    if len(inicios) == 1 and len(fines) == 1 and inicios[0] < fines[0]:
        return {"presente": True, "danado": False, "motivo": ""}
    if not fines:
        motivo = "falta el marcador de fin (bloque truncado)"
    elif not inicios:
        motivo = "falta el marcador de inicio (fin huérfano)"
    elif len(inicios) > 1 or len(fines) > 1:
        motivo = "marcadores duplicados"
    else:
        motivo = "marcadores invertidos"
    return {"presente": True, "danado": True, "motivo": motivo}


def quitar_bloque_robusto(texto_hosts: str) -> str:
    """Retira la sección de la app AUNQUE esté dañada (v1.0.6).

    quitar_bloque clásico exige la pareja de marcadores sana; esta
    variante es una máquina de estados tolerante: marcador de inicio
    duplicado se descarta, un fin huérfano arrastra la racha de
    entradas «0.0.0.0 dominio» que lo precede (el cuerpo del bloque
    huérfano) y un inicio sin fin descarta hasta el final del archivo
    (el bloque siempre se añade al final). El resto del hosts — lo que
    no es de la app — queda intacto, igual que en la retirada clásica.
    """
    if not analizar_bloque(texto_hosts)["presente"]:
        return texto_hosts
    salida: list[str] = []
    dentro = False
    for linea in texto_hosts.splitlines():
        limpia = linea.strip()
        if limpia == MARCADOR_INICIO:
            dentro = True
            continue
        if limpia == MARCADOR_FIN:
            if not dentro:
                # Fin huérfano: la racha de entradas ya emitida justo
                # antes era el cuerpo del bloque sin su inicio.
                while salida and _es_entrada_bloque(salida[-1]):
                    salida.pop()
            dentro = False
            continue
        if not dentro:
            salida.append(linea)
    resultado = "\n".join(salida)
    if texto_hosts.endswith("\n") and resultado and not resultado.endswith("\n"):
        resultado += "\n"
    return resultado


def aplicar_bloque(texto_hosts: str, dominios: list[str]) -> str:
    """Texto del hosts con el bloque de la app (reemplaza uno anterior)."""
    limpio = quitar_bloque_robusto(texto_hosts)
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
