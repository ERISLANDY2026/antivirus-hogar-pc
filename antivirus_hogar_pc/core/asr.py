"""Asistente de reglas ASR de Defender (v1.0.21): lógica pura.

ASR = Attack Surface Reduction, las reglas de reducción de
superficie de ataque de Microsoft Defender. El preset de la app es
CONSERVADOR: las reglas estándar de Microsoft con menos falsos
positivos conocidos en un PC doméstico. Nada de presets «MAX» ni
aplicaciones en bloque: cada regla se aplica DE UNA EN UNA, con
confirmación del usuario dentro de la app, primero en modo
AUDITORÍA cuando la regla lo permite, y siempre reversible desde
la propia app (volver a «desactivada» es la misma operación).

Los GUID son los oficiales de Microsoft. Las acciones de
MpPreference: 0 = desactivada, 1 = bloqueo, 2 = auditoría,
6 = aviso (warn). La lectura/escritura vive en winapi.defender;
aquí solo hay datos y decisiones puras, probables sin Windows.
"""

# guid → (clave de nombre para i18n, admite_auditoria)
REGLAS_ASR: list[dict] = [
    {"guid": "BE9BA2D9-53EA-4CDC-84E5-9B1EEEE46550",
     "clave": "asr_lsass", "auditoria": True,
     "nombre": "Bloquear el robo de credenciales desde LSASS"},
    {"guid": "D4F940AB-401B-4EFC-AADC-AD5F3C50688A",
     "clave": "asr_office_hijos", "auditoria": True,
     "nombre": "Bloquear que Office cree procesos hijos"},
    {"guid": "3B576869-A4EC-4529-8536-B80A7769E899",
     "clave": "asr_office_ejecutable", "auditoria": True,
     "nombre": "Bloquear que Office cree contenido ejecutable"},
    {"guid": "75668C1F-73B5-4CF0-BB93-3ECF5CB7CC84",
     "clave": "asr_office_inyeccion", "auditoria": True,
     "nombre": "Bloquear que Office inyecte código en otros procesos"},
    {"guid": "92E97FA1-2EDF-4476-BDD6-9DD0B4DDDC7B",
     "clave": "asr_macros_win32", "auditoria": True,
     "nombre": "Bloquear llamadas a Win32 desde macros de Office"},
    {"guid": "D3E037E1-3EB8-44C8-A917-57927947596D",
     "clave": "asr_scripts_descargado", "auditoria": True,
     "nombre": "Bloquear que JavaScript o VBScript lancen ejecutables descargados"},
    {"guid": "01443614-CD74-433A-B99E-2ECDC07BFC25",
     "clave": "asr_adobe_hijos", "auditoria": True,
     "nombre": "Bloquear que Adobe Reader cree procesos hijos"},
    {"guid": "B2B3F03D-6A65-4F7B-A9C7-1C7EF74A9BA4",
     "clave": "asr_usb_no_confiable", "auditoria": True,
     "nombre": "Bloquear procesos no confiables o sin firmar desde USB"},
]

ACCIONES = {0: "desactivada", 1: "bloqueo", 2: "auditoria", 6: "aviso"}
MODOS_VALIDOS = ("auditoria", "bloqueo", "desactivada")


def regla_por_guid(guid: str) -> dict | None:
    g = (guid or "").strip().upper()
    for regla in REGLAS_ASR:
        if regla["guid"] == g:
            return regla
    return None


def interpretar_estado(datos: dict | None) -> dict[str, str]:
    """{guid: modo} desde el JSON de Get-MpPreference.

    datos: {"ids": [...], "acciones": [...]} tal como los devuelve
    winapi.defender.leer_estado_asr. Las reglas del preset que no
    aparezcan quedan «desactivada» (así las trata Defender).
    """
    estado: dict[str, str] = {r["guid"]: "desactivada" for r in REGLAS_ASR}
    if not isinstance(datos, dict):
        return estado
    ids = datos.get("ids") or []
    acciones = datos.get("acciones") or []
    for guid, accion in zip(ids, acciones):
        g = str(guid or "").strip().upper()
        if g in estado:
            try:
                estado[g] = ACCIONES.get(int(accion), "desactivada")
            except (TypeError, ValueError):
                estado[g] = "desactivada"
    return estado


def accion_para_modo(modo: str) -> str:
    """El valor de -AttackSurfaceReductionRules_Actions."""
    return {"auditoria": "AuditMode", "bloqueo": "Block",
            "desactivada": "Disabled"}[modo]


def modo_inicial_sugerido(regla: dict) -> str:
    """La primera aplicación sugerida: auditoría si la regla la
    admite (así se observa sin romper nada); si no, bloqueo."""
    return "auditoria" if regla.get("auditoria") else "bloqueo"
