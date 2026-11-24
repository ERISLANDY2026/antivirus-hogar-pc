"""Discos: salud SMART y optimización con la herramienta de Windows.

Salud: Get-PhysicalDisk (HealthStatus) + Get-StorageReliabilityCounter
(desgaste SSD, temperatura, horas, errores). Muchos discos tras puente USB
o RAID no devuelven contadores: se devuelve None y la UI dice «no se puede
leer», nunca «sano».

Optimización: Optimize-Volume — desfragmenta discos mecánicos (HDD) y hace
ReTrim en SSD. NUNCA desfragmentación clásica sobre un SSD.

v1.0.5: la optimización corre ELEVADA pero OCULTA, en segundo plano
(antes Windows abría su Shell en primer plano y la app no enseñaba
nada). El proceso elevado no puede devolver su salida por tubería, así
que vuelca su salida -Verbose en un archivo de progreso y el desenlace
en otro de resultado; aquí se vigilan ambos y cada avance interpretado
(modules.system.smart_logic) se entrega a al_progreso(fase, pct|None):
el % es el que el propio comando reporta, nunca uno inventado.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

from ..modules.system.smart_logic import interpretar_progreso_optimizacion
from . import WindowsNoDisponible, es_windows
from .powershell import (como_lista, ejecutar_powershell_json,
                         lanzar_elevado_oculto)


def discos_fisicos() -> list[dict]:
    script = (
        "Get-PhysicalDisk | ForEach-Object { $d = $_; $r = $null; "
        "try { $r = $d | Get-StorageReliabilityCounter -ErrorAction Stop } catch {} "
        "[PSCustomObject]@{ Nombre = $d.FriendlyName; Tipo = [string]$d.MediaType; "
        "Salud = [string]$d.HealthStatus; Tamano = [int64]$d.Size; "
        "Desgaste = if ($r) { $r.Wear } else { $null }; "
        "Temperatura = if ($r) { $r.Temperature } else { $null }; "
        "Horas = if ($r) { $r.PowerOnHours } else { $null }; "
        "ErroresLectura = if ($r) { $r.ReadErrorsTotal } else { $null } } } | ConvertTo-Json"
    )
    datos = como_lista(ejecutar_powershell_json(script, timeout=120))
    discos: list[dict] = []
    for d in datos:
        discos.append({
            "nombre": d.get("Nombre", "Disco"),
            "tipo": d.get("Tipo", ""),  # SSD / HDD / Unspecified
            "salud": d.get("Salud", ""),  # Healthy / Warning / Unhealthy
            "tamano": int(d.get("Tamano") or 0),
            "desgaste_pct": d.get("Desgaste"),
            "temperatura": d.get("Temperatura"),
            "horas": d.get("Horas"),
            "errores_lectura": d.get("ErroresLectura"),
            "sano": (d.get("Salud") == "Healthy"),
            "sin_datos": d.get("Salud") in (None, "", "Unknown"),
        })
    return discos


def volumenes() -> list[dict]:
    script = (
        "Get-Volume | Where-Object { $_.DriveLetter } | Select-Object DriveLetter, "
        "FileSystemLabel, FileSystem, Size, SizeRemaining | ConvertTo-Json"
    )
    datos = como_lista(ejecutar_powershell_json(script))
    return [
        {
            "letra": d.get("DriveLetter", ""),
            "etiqueta": d.get("FileSystemLabel", ""),
            "sistema_archivos": d.get("FileSystem", ""),
            "tamano": int(d.get("Size") or 0),
            "libre": int(d.get("SizeRemaining") or 0),
        }
        for d in datos if d.get("DriveLetter")
    ]


def _script_optimizacion(letra: str, operacion: str,
                         ruta_progreso: str, ruta_resultado: str) -> str:
    """Script que corre ELEVADO y oculto: Optimize-Volume volcando su
    salida -Verbose al archivo de progreso y el desenlace (OK / ERROR:
    causa) al de resultado. Las rutas van entre comillas simples de
    PowerShell (se escapan las comillas que pudieran traer)."""
    def q(ruta: str) -> str:
        return "'" + ruta.replace("'", "''") + "'"

    return (
        "$ErrorActionPreference = 'Stop'\n"
        "try {\n"
        # v1.0.6: cada registro verbose se anexa al archivo de
        # progreso con una escritura .NET INMEDIATA. Con la tubería
        # directa a Out-File, PowerShell amortiguaba la salida y el
        # archivo llegaba de golpe al final: la barra saltaba de
        # «esperando» al 100 % sin progresar (visto en la PC real).
        f"  Optimize-Volume -DriveLetter {letra} {operacion} -Verbose 4>&1 | "
        "ForEach-Object { [System.IO.File]::AppendAllText("
        f"{q(ruta_progreso)}, ($_ | Out-String -Width 4096), "
        "[System.Text.Encoding]::UTF8) }\n"
        f"  'OK' | Out-File -FilePath {q(ruta_resultado)} -Encoding ascii\n"
        "} catch {\n"
        f"  ('ERROR: ' + $_.Exception.Message) | Out-File -FilePath {q(ruta_resultado)} "
        "-Encoding utf8\n"
        "} finally {\n"
        # v1.0.6: el archivo de resultado NUNCA queda vacío — si el
        # proceso muere entre el cmdlet y la escritura, el finally
        # deja constancia en vez de un «causa desconocida» mudo.
        f"  if (-not (Test-Path {q(ruta_resultado)}) -or "
        f"(Get-Item {q(ruta_resultado)}).Length -eq 0) {{\n"
        f"    'ERROR: Optimize-Volume terminó sin dejar resultado.' | "
        f"Out-File -FilePath {q(ruta_resultado)} -Encoding utf8\n"
        "  }\n"
        "}\n"
    )


# Líneas de la salida detallada que suelen traer la CAUSA real cuando
# el archivo de resultado no la trae (v1.0.6).
_MARCAS_CAUSA = ("optimize-volume", "error", "failed", "cannot",
                 "no se puede", "no es posible", "denegado", "denied",
                 "not supported", "no admite", "no compatible")

# Marcas de que la salida detallada llegó a su INFORME FINAL: la
# optimización recorrió todas sus pasadas y cerró con el reporte
# posterior (v1.0.7). Optimize-Volume titula ese cierre «Post
# Defragmentation Report» / «Post Retrim Report» (en Windows en
# español, «Informe posterior a la desfragmentación»).
_MARCAS_FIN_VERBOSE = ("post defragmentation report",
                       "post retrim report",
                       "post-defragmentation report",
                       "informe posterior a la desfragmentación",
                       "informe posterior a la desfragmentacion",
                       "the operation completed successfully",
                       "la operación se completó correctamente",
                       "la operacion se completo correctamente")

# Marcas en los eventos del optimizador (registro de eventos de
# Windows, fuente/canal Defrag): el servicio anota el desenlace de
# cada volumen aunque el cmdlet no deje constancia en su salida.
_MARCAS_EVENTO_EXITO = ("successfully completed",
                        "se completó correctamente",
                        "se completo correctamente",
                        "completed defragmentation",
                        "completed retrim",
                        "finalizó correctamente",
                        "finalizo correctamente")
_MARCAS_EVENTO_FALLO = ("unable to complete", "could not complete",
                        "couldn't complete", "cannot complete",
                        "no se pudo completar", "no pudo completar",
                        "failed", "falló", "fallo")


def interpretar_eventos_optimizacion(eventos, letra: str) -> dict | None:
    """Desenlace según el registro de eventos de Windows (v1.0.7).

    ``eventos``: lista de dicts con al menos «mensaje» (se aceptan
    también las claves «Mensaje»/«Message»), del MÁS RECIENTE al más
    antiguo, ya filtrados a la ventana de la corrida. Solo cuentan
    los que nombran la unidad pedida. Devuelve {"ok": bool,
    "causa": str} del primer evento concluyente, o None si ningún
    evento habla de esa unidad.
    """
    letra = (letra or "").strip().rstrip(":").lower()
    if not letra:
        return None
    marcas_unidad = (f"({letra}:)", f" {letra}: ", f" {letra}:\\",
                     f"unidad {letra}", f"volume {letra}")
    for evento in eventos or []:
        if isinstance(evento, dict):
            texto = str(evento.get("mensaje") or evento.get("Mensaje")
                        or evento.get("Message") or "")
        else:
            texto = str(evento or "")
        bajo = texto.lower()
        if not any(m in bajo for m in marcas_unidad):
            continue
        if any(m in bajo for m in _MARCAS_EVENTO_EXITO):
            return {"ok": True, "causa": ""}
        if any(m in bajo for m in _MARCAS_EVENTO_FALLO):
            # La causa viaja en el propio texto del evento: se enseña
            # recortada y el texto entero queda en el detalle.
            return {"ok": False, "causa": texto.strip()}
    return None


def consultar_eventos_optimizacion(letra: str, desde_epoch: float) -> list:
    """Eventos del optimizador de Windows desde ``desde_epoch``.

    Se consultan DOS sitios: el registro de Aplicación (fuente
    «Defrag», donde el servicio anota «successfully completed…» o el
    motivo del fallo por volumen) y el canal operativo
    Microsoft-Windows-Defrag/Operational si existe. Cualquier fallo
    (canal ausente, permisos, no-Windows) devuelve []: los eventos
    son una fuente MÁS de evidencia, nunca un requisito.
    """
    if not es_windows():
        return []
    segundos = max(60, int(time.time() - float(desde_epoch)) + 180)
    script = (
        "$ErrorActionPreference = 'SilentlyContinue'\n"
        f"$desde = (Get-Date).AddSeconds(-{segundos})\n"
        "$lista = @()\n"
        "try { $lista += Get-WinEvent -FilterHashtable "
        "@{LogName='Application'; ProviderName='Defrag'; "
        "StartTime=$desde} -ErrorAction Stop } catch {}\n"
        "try { $lista += Get-WinEvent -FilterHashtable "
        "@{LogName='Microsoft-Windows-Defrag/Operational'; "
        "StartTime=$desde} -ErrorAction Stop } catch {}\n"
        "$lista | Sort-Object TimeCreated -Descending | "
        "Select-Object -First 12 @{n='Id';e={$_.Id}}, "
        "@{n='Mensaje';e={$_.Message}} | ConvertTo-Json"
    )
    try:
        datos = ejecutar_powershell_json(script, timeout=90)
    except Exception:
        return []
    eventos = []
    for e in como_lista(datos):
        if isinstance(e, dict):
            eventos.append({"id": e.get("Id"),
                            "mensaje": str(e.get("Mensaje") or "")})
    return eventos


def interpretar_resultado_optimizacion(resultado_crudo: str,
                                       texto_progreso: str,
                                       letra: str,
                                       nombre_op: str,
                                       eventos=None) -> dict:
    """Traduce el desenlace de Optimize-Volume a {ok, mensaje, detalle}.

    v1.0.6 (nota del usuario): si el archivo de resultado no empieza
    por «OK» ni «ERROR:», la causa ya NO cae en un «causa desconocida»
    que lo pierde todo: se busca la causa en la COLA de la salida
    detallada (donde el propio Optimize-Volume explica el rechazo) y
    el detalle COMPLETO (resultado crudo + cola del verbose) viaja en
    «detalle» para que la página lo guarde en el registro de
    actividad antes de que la carpeta temporal se borre.

    v1.0.7 (nota de su PC real): en su Toughbook la optimización
    corre COMPLETA (la barra llega al 100 %) pero el «OK» del
    archivo de resultado no llega, y la app decía «no se completó».
    Ahora el desenlace se extrae de DOS fuentes más antes de juzgar:
    (a) el registro de eventos de Windows (el optimizador anota ahí
    el éxito o el motivo, por volumen) y (b) la salida detallada
    COMPLETA (si llegó a su informe final, la optimización terminó).
    Si la evidencia confirma que terminó, el mensaje es
    «Optimización finalizada»; si falló, la causa verdadera de esas
    fuentes, nunca «causa desconocida» a secas.
    """
    resultado = (resultado_crudo or "").strip()
    if resultado.startswith("OK"):
        return {"ok": True,
                "mensaje": (f"Optimización finalizada. Windows optimizó "
                            f"la unidad {letra}: ({nombre_op}) en segundo "
                            "plano, sin abrir ninguna ventana."),
                "detalle": ""}
    cola = (texto_progreso or "").strip()
    cola_corta = cola[-1500:]
    if resultado.startswith("ERROR:"):
        causa = resultado[6:].strip() or "Windows no dio el motivo."
        detalle = f"Resultado de Windows: {resultado}"
        if cola_corta:
            detalle += f"\nSalida detallada (final):\n{cola_corta}"
        return {"ok": False,
                "mensaje": (f"La optimización de la unidad {letra}: no se "
                            f"completó. Causa de Windows: {causa[:220]}"),
                "detalle": detalle}
    # Sin veredicto directo: manda la EVIDENCIA (eventos y verbose).
    detalle = (f"Resultado crudo: {resultado!r}\n"
               f"Salida detallada (final):\n{cola_corta or '(sin salida)'}")
    por_eventos = interpretar_eventos_optimizacion(eventos, letra)
    if por_eventos is not None:
        texto_evento = por_eventos.get("causa") or ""
        if texto_evento:
            detalle += f"\nEvento de Windows: {texto_evento}"
        if por_eventos["ok"]:
            return {"ok": True,
                    "mensaje": (f"Optimización finalizada. El registro "
                                f"de eventos de Windows confirma que la "
                                f"unidad {letra}: quedó optimizada "
                                f"({nombre_op})."),
                    "detalle": detalle}
        causa = texto_evento or "el registro de eventos no dio el motivo."
        return {"ok": False,
                "mensaje": (f"La optimización de la unidad {letra}: no se "
                            f"completó. Causa según el registro de "
                            f"eventos de Windows: {causa[:220]}"),
                "detalle": detalle}
    bajo = cola.lower()
    if any(m in bajo for m in _MARCAS_FIN_VERBOSE):
        return {"ok": True,
                "mensaje": (f"Optimización finalizada. La salida de "
                            f"Windows llegó a su informe final: la "
                            f"unidad {letra}: recorrió todas sus "
                            f"pasadas ({nombre_op})."),
                "detalle": detalle}
    # Ni eventos ni informe final: la causa se busca en el verbose.
    causa = ""
    for linea in reversed(cola.splitlines()):
        limpia = linea.strip()
        if limpia and any(m in limpia.lower() for m in _MARCAS_CAUSA):
            causa = limpia
            break
    if causa:
        mensaje = (f"La optimización de la unidad {letra}: no se "
                   f"completó. Causa de Windows: {causa[:220]}")
    else:
        mensaje = (f"La optimización de la unidad {letra}: no se "
                   "completó y Windows no dio la causa en ninguna de "
                   "sus fuentes (ni el resultado, ni el registro de "
                   "eventos, ni la salida detallada). El detalle "
                   "completo quedó guardado en el registro de actividad "
                   "de Inicio.")
    return {"ok": False, "mensaje": mensaje, "detalle": detalle}


def _leer_texto_tolerante(ruta: str) -> str:
    """Lee un archivo que otro proceso puede estar escribiendo: si está
    bloqueado o aún no existe, devuelve lo que haya (o cadena vacía)."""
    try:
        with open(ruta, "rb") as f:
            return f.read().decode("utf-8-sig", errors="replace")
    except OSError:
        return ""


def _proceso_vivo(pid: int) -> bool:
    """¿Sigue vivo el proceso elevado? (solo Windows; tasklist oculto)."""
    try:
        proc = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True, errors="replace", timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if sys.platform.startswith("win") else 0,
        )
        return str(pid) in (proc.stdout or "")
    except Exception:
        return True  # si no se puede comprobar, se asume vivo


def optimizar_volumen(letra: str, es_ssd: bool, al_progreso=None,
                      timeout: int = 1800, intervalo: float = 0.7) -> dict:
    """Optimize-Volume OCULTO en segundo plano, con progreso real.

    al_progreso(fase, porcentaje|None) se llama cada vez que la salida
    del comando trae algo nuevo: el porcentaje es el que reporta el
    propio Optimize-Volume en su salida detallada (por pasadas); en las
    fases sin % fiable se pasa None y la fase en texto.

    Devuelve {"ok": bool, "mensaje": str, "detalle": str} — el mensaje
    es la frase clara para el usuario; el detalle, la causa técnica.
    """
    if not es_windows():
        raise WindowsNoDisponible("La optimización solo existe en Windows.")
    letra = (letra or "").strip().rstrip(":").upper()
    if len(letra) != 1 or not letra.isalpha():
        raise ValueError(f"Letra de unidad no válida: {letra!r}")
    operacion = "-ReTrim" if es_ssd else "-Defrag"
    nombre_op = "TRIM" if es_ssd else "la desfragmentación"

    carpeta = tempfile.mkdtemp(prefix="ahpc-opt-")
    ruta_progreso = os.path.join(carpeta, "progreso.txt")
    ruta_resultado = os.path.join(carpeta, "resultado.txt")
    inicio = time.time()  # ventana para el registro de eventos (v1.0.7)
    try:
        script = _script_optimizacion(letra, operacion,
                                       ruta_progreso, ruta_resultado)
        try:
            pid = lanzar_elevado_oculto(script)
        except RuntimeError as exc:
            return {"ok": False,
                    "mensaje": (f"La optimización de la unidad {letra}: no "
                                "arrancó: se canceló el aviso de administrador "
                                "de Windows."),
                    "detalle": str(exc)}
        if al_progreso is not None:
            al_progreso("Esperando a que Windows empiece…", None)
        limite = time.time() + timeout
        ultimo_texto = ""
        muerto_desde: float | None = None
        while time.time() < limite:
            if os.path.isfile(ruta_resultado):
                break
            texto = _leer_texto_tolerante(ruta_progreso)
            if texto != ultimo_texto:
                ultimo_texto = texto
                if al_progreso is not None:
                    progreso = interpretar_progreso_optimizacion(texto)
                    try:
                        al_progreso(progreso.fase, progreso.porcentaje)
                    except Exception:
                        pass  # el progreso jamás debe tumbar el proceso
            if not _proceso_vivo(pid):
                # Sin archivo de resultado y sin proceso: terminó mal
                # (se da un margen por si el archivo llega con retraso).
                if muerto_desde is None:
                    muerto_desde = time.time()
                elif time.time() - muerto_desde > 5:
                    # v1.0.7: sin archivo de resultado, el registro de
                    # eventos puede aun así confirmar el desenlace.
                    eventos = consultar_eventos_optimizacion(letra, inicio)
                    por_eventos = interpretar_eventos_optimizacion(
                        eventos, letra)
                    if por_eventos is not None and por_eventos["ok"]:
                        return {"ok": True,
                                "mensaje": (f"Optimización finalizada. El "
                                            f"registro de eventos de Windows "
                                            f"confirma que la unidad {letra}: "
                                            f"quedó optimizada ({nombre_op})."),
                                "detalle": "El proceso elevado terminó sin "
                                           "archivo de resultado; el desenlace "
                                           "lo confirma el registro de eventos."}
                    return {"ok": False,
                            "mensaje": (f"La optimización de la unidad {letra}: "
                                        "el proceso de Windows terminó sin "
                                        "confirmar el resultado."),
                            "detalle": "Proceso elevado finalizado sin "
                                       "archivo de resultado."}
            time.sleep(intervalo)
        else:
            return {"ok": False,
                    "mensaje": (f"La optimización de la unidad {letra}: tardó "
                                "demasiado y se dejó de vigilar. Revisa el "
                                "resultado en la herramienta de Windows."),
                    "detalle": f"Tiempo de vigilancia agotado ({timeout} s)."}

        resultado = _leer_texto_tolerante(ruta_resultado).strip()
        # El archivo puede existir un instante ANTES de que el proceso
        # elevado vuelque su contenido (en Windows se ve vacío): si se
        # lee vacío, se espera y se relee con un margen antes de juzgar.
        for _ in range(10):
            if resultado:
                break
            time.sleep(0.2)
            resultado = _leer_texto_tolerante(ruta_resultado).strip()
        # La salida detallada también se lee ANTES de juzgar (v1.0.6):
        # si el resultado no trae la causa, puede estar en su cola, y
        # la carpeta temporal se borra al salir de aquí.
        texto_progreso = _leer_texto_tolerante(ruta_progreso)
        # v1.0.7: si el resultado no trae veredicto directo (ni «OK»
        # ni «ERROR:»), se consulta el registro de eventos de Windows
        # de la ventana de la corrida antes de juzgar.
        eventos = None
        if not resultado.startswith(("OK", "ERROR:")):
            eventos = consultar_eventos_optimizacion(letra, inicio)
        desenlace = interpretar_resultado_optimizacion(
            resultado, texto_progreso, letra, nombre_op, eventos=eventos)
        if desenlace["ok"] and al_progreso is not None:
            try:
                al_progreso("Completado", 100)
            except Exception:
                pass
        return desenlace
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)
