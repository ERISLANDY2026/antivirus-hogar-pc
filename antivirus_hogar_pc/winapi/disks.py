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
import threading
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

    Se consultan DOS sitios: el registro de Aplicación (donde el
    servicio anota «successfully completed…» o el motivo del fallo
    por volumen) y el canal operativo
    Microsoft-Windows-Defrag/Operational si existe. Cualquier fallo
    (canal ausente, permisos, no-Windows) devuelve []: los eventos
    son una fuente MÁS de evidencia, nunca un requisito.

    v1.0.19 (nota 5, CAUSA RAÍZ medida en la Toughbook real): el
    proveedor que escribe esos eventos se llama
    «Microsoft-Windows-Defrag», NO «Defrag». La consulta anterior
    filtraba con FilterHashtable @{ProviderName='Defrag'} y
    Get-WinEvent LANZA «The parameter is incorrect» cuando el
    nombre no es un proveedor válido de ese registro: la excepción
    caía en el catch silencioso y el testigo devolvía [] SIEMPRE,
    aunque el evento 258 de éxito estuviera escrito segundos
    antes (comprobado en campo el 2026-11-26: retrim completado
    a las 09:43:44 y la app declaró «no se pudo confirmar» a las
    09:43:50). Por eso ahora el registro se pide SOLO por ventana
    de tiempo y el proveedor se filtra EN CÓDIGO (Where-Object),
    aceptando ambos nombres; el canal operativo se pide sin
    filtro de proveedor (es exclusivo de defrag) y solo si
    existe en el equipo (en la Toughbook no existe: allí solo
    está Microsoft-Windows-Defrag-Core/Debug).
    """
    if not es_windows():
        return []
    segundos = max(60, int(time.time() - float(desde_epoch)) + 180)
    script = (
        "$ErrorActionPreference = 'SilentlyContinue'\n"
        f"$desde = (Get-Date).AddSeconds(-{segundos})\n"
        "$lista = @()\n"
        "try { $lista += Get-WinEvent -FilterHashtable "
        "@{LogName='Application'; StartTime=$desde} "
        "-ErrorAction Stop | Where-Object { $_.ProviderName -in "
        "@('Microsoft-Windows-Defrag', 'Defrag') } } catch {}\n"
        "try { if (Get-WinEvent -ListLog "
        "'Microsoft-Windows-Defrag/Operational' "
        "-ErrorAction Stop) { $lista += Get-WinEvent "
        "-FilterHashtable "
        "@{LogName='Microsoft-Windows-Defrag/Operational'; "
        "StartTime=$desde} -ErrorAction Stop } } catch {}\n"
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


_MARCAS_FIN_DEFRAG = ("the operation completed successfully",
                      "la operación se completó correctamente",
                      "la operacion se completo correctamente",
                      "operation completed successfully")

_MARCAS_ERROR_DEFRAG = ("error", "failed", "cannot", "could not",
                        "unable", "denied", "no se puede",
                        "no se pudo", "falló", "fallo", "denegado",
                        "not supported", "no admite")


def _script_defrag(letra: str, es_ssd: bool, ruta_salida: str,
                   ruta_resultado: str) -> str:
    """Script ELEVADO y oculto: pre-chequeos + defrag.exe con
    salida completa a archivo y código de salida al resultado.
    El archivo de resultado lleva líneas CLAVE=valor:
    PRECHECK=OK|TRIM_DESHABILITADO|SERVICIO_DESHABILITADO y
    EXITCODE=<n>. Nunca queda vacío (finally).

    v1.0.18 (nota 3): el resultado se escribe de forma ATÓMICA y
    verificable — primero a un hermano «.tmp» y después se
    renombra encima (el renombrado en el mismo volumen es
    atómico: quien vigila ve el archivo solo cuando está
    COMPLETO, nunca a mitad de escritura) — y la salida de error
    de defrag.exe va a su PROPIO archivo (antes el script pasaba
    «$salida.err», que PowerShell lee como una propiedad nula:
    el error estándar se perdía o el propio Start-Process
    fallaba). Si el proceso no deja código, el script lo dice
    tal cual (EXITCODE=SIN_CODIGO) para que mande el testigo
    independiente: el registro de eventos de Windows."""
    def q(ruta: str) -> str:
        return "'" + ruta.replace("'", "''") + "'"

    ruta_error = ruta_salida + ".err"
    modo = "/L" if es_ssd else "/D"
    return (
        "$ErrorActionPreference = 'Continue'\n"
        f"$resultado = {q(ruta_resultado)}\n"
        f"$salida = {q(ruta_salida)}\n"
        f"$salidaErr = {q(ruta_error)}\n"
        # Escritura ATÓMICA del resultado: .tmp + renombrado.
        "function Guardar-Resultado([string]$contenido) {\n"
        "  $tmp = $resultado + '.tmp'\n"
        "  [System.IO.File]::WriteAllText($tmp, $contenido)\n"
        "  Move-Item -LiteralPath $tmp -Destination $resultado "
        "-Force\n"
        "}\n"
        "try {\n"
        # (a) TRIM habilitado en el sistema (solo SSD): si está
        # deshabilitado, defrag /L no puede aplicar ReTrim.
        + (("  $fsutil = fsutil behavior query DisableDeleteNotify "
            "2>&1 | Out-String\n"
            "  if ($fsutil -match 'DisableDeleteNotify\\s*=\\s*1') {\n"
            "    Guardar-Resultado 'PRECHECK=TRIM_DESHABILITADO'\n"
            "    exit\n"
            "  }\n") if es_ssd else "")
        # (b) El servicio del optimizador debe poder arrancar.
        + "  $svc = Get-Service -Name defragsvc -ErrorAction SilentlyContinue\n"
        "  if ($svc -and $svc.StartType -eq 'Disabled') {\n"
        "    Guardar-Resultado 'PRECHECK=SERVICIO_DESHABILITADO'\n"
        "    exit\n"
        "  }\n"
        f"  $p = Start-Process -FilePath defrag.exe -ArgumentList "
        f"'{letra}:','{modo}','/U','/V' -NoNewWindow -Wait -PassThru "
        "-RedirectStandardOutput $salida -RedirectStandardError "
        "$salidaErr\n"
        "  if ($null -eq $p.ExitCode) {\n"
        "    Guardar-Resultado ('PRECHECK=OK' + "
        "[Environment]::NewLine + 'EXITCODE=SIN_CODIGO')\n"
        "  } else {\n"
        "    Guardar-Resultado ('PRECHECK=OK' + "
        "[Environment]::NewLine + 'EXITCODE=' + $p.ExitCode)\n"
        "  }\n"
        "} catch {\n"
        "  Guardar-Resultado ('PRECHECK=ERROR_SCRIPT' + "
        "[Environment]::NewLine + 'ERROR=' + $_.Exception.Message)\n"
        "} finally {\n"
        "  if (-not (Test-Path $resultado)) {\n"
        "    Guardar-Resultado 'PRECHECK=SIN_RESULTADO'\n"
        "  }\n"
        "}\n"
    )


def interpretar_resultado_defrag(resultado_crudo: str,
                                 salida_defrag: str,
                                 letra: str,
                                 nombre_op: str,
                                 eventos=None) -> dict:
    """Veredicto CIERTO a partir del resultado de defrag.exe.

    Sin comodines: cada desenlace posible nombra su causa real.
    - PRECHECK=TRIM_DESHABILITADO -> la causa es el ajuste de
      Windows (DisableDeleteNotify=1), dicho tal cual.
    - PRECHECK=SERVICIO_DESHABILITADO -> el servicio «Optimize
      drives» (defragsvc) está deshabilitado.
    - EXITCODE=0 -> «Optimización finalizada».
    - EXITCODE!=0 -> la causa sale de las líneas de error de la
      salida de defrag; sin líneas, del propio código.

    v1.0.18 (nota 3): si el ayudante elevado no dejó un código
    utilizable (era el «terminó sin dejar el código de salida»
    que el usuario vio en su Toughbook), manda el TESTIGO
    INDEPENDIENTE: el registro de eventos de Windows
    (``eventos``, interpretado por
    interpretar_eventos_optimizacion). Éxito en el registro ->
    «Optimización finalizada»; fallo en el registro -> su causa.
    Sin código y sin eventos, el desenlace se marca
    ``sin_evidencia`` para que optimizar_volumen RECAPTURE
    dentro del mismo clic antes de decir nada; el mensaje de
    ese desenlace nombra las fuentes comprobadas, jamás la
    frase eliminada.
    """
    datos: dict[str, str] = {}
    for linea in (resultado_crudo or "").splitlines():
        if "=" in linea:
            clave, valor = linea.split("=", 1)
            datos[clave.strip().upper()] = valor.strip()
    salida = (salida_defrag or "").strip()
    detalle = (f"Resultado: {resultado_crudo.strip()!r}\n"
               f"Salida de defrag (final):\n{salida[-1500:] or '(sin salida)'}")
    pre = datos.get("PRECHECK", "")
    if pre == "TRIM_DESHABILITADO":
        return {"ok": False,
                "mensaje": (f"La optimización de la unidad {letra}: no "
                            "se aplicó porque Windows tiene el TRIM "
                            "deshabilitado (fsutil DisableDeleteNotify "
                            "= 1). Sin TRIM habilitado, la orden de "
                            "optimizar un SSD no puede ejecutarse."),
                "detalle": detalle}
    if pre == "SERVICIO_DESHABILITADO":
        return {"ok": False,
                "mensaje": (f"La optimización de la unidad {letra}: no "
                            "se aplicó porque el servicio de Windows "
                            "«Optimize drives» (defragsvc) está "
                            "deshabilitado en este equipo."),
                "detalle": detalle}
    if pre == "ERROR_SCRIPT":
        return {"ok": False,
                "mensaje": (f"La optimización de la unidad {letra}: el "
                            f"script elevado falló: "
                            f"{datos.get('ERROR', '')[:220]}"),
                "detalle": detalle}
    codigo_txt = datos.get("EXITCODE", "")
    try:
        codigo = int(codigo_txt)
    except (TypeError, ValueError):
        codigo = None
    if codigo == 0:
        return {"ok": True,
                "mensaje": (f"Optimización finalizada. Windows optimizó "
                            f"la unidad {letra}: ({nombre_op}) con "
                            "defrag.exe en segundo plano, sin abrir "
                            "ninguna ventana."),
                "detalle": detalle}
    # Fallo real: la causa sale de la salida del propio defrag.
    causa = ""
    for linea in reversed(salida.splitlines()):
        limpia = linea.strip()
        if limpia and any(m in limpia.lower()
                          for m in _MARCAS_ERROR_DEFRAG):
            causa = limpia
            break
    if causa:
        mensaje = (f"La optimización de la unidad {letra}: no se "
                   f"completó. Causa de Windows: {causa[:220]}")
    elif codigo is not None:
        mensaje = (f"La optimización de la unidad {letra}: no se "
                   f"completó. defrag.exe terminó con el código "
                   f"{codigo} sin dejar más explicación en su salida.")
    else:
        # v1.0.18: sin código utilizable manda el testigo
        # independiente (registro de eventos de Windows).
        por_eventos = interpretar_eventos_optimizacion(
            eventos, letra)
        if por_eventos is not None:
            texto_evento = por_eventos.get("causa") or ""
            if texto_evento:
                detalle += f"\nEvento de Windows: {texto_evento}"
            if por_eventos["ok"]:
                return {"ok": True,
                        "mensaje": (f"Optimización finalizada. El "
                                    f"registro de eventos de "
                                    f"Windows confirma que la "
                                    f"unidad {letra}: quedó "
                                    f"optimizada ({nombre_op})."),
                        "detalle": detalle}
            causa_evento = (texto_evento
                            or "el registro de eventos no dio el motivo.")
            return {"ok": False,
                    "mensaje": (f"La optimización de la unidad "
                                f"{letra}: no se completó. Causa "
                                f"según el registro de eventos de "
                                f"Windows: {causa_evento[:220]}"),
                    "detalle": detalle}
        mensaje = (f"La optimización de la unidad {letra}: no se "
                   "pudo confirmar el resultado. El ayudante "
                   "elevado no dejó un resultado verificable y el "
                   "registro de eventos de Windows no registra "
                   "esta optimización; el detalle completo quedó "
                   "guardado en el registro de actividad.")
        return {"ok": False, "mensaje": mensaje,
                "detalle": detalle, "sin_evidencia": True}
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


def _progreso_desde_defrag(texto: str):
    """Progreso desde la salida de defrag.exe: su ÚLTIMO porcentaje
    impreso (defrag /U lo reporta por fases); sin % fiable, None."""
    import re as _re
    hallados = _re.findall(r"(\d{1,3})\s*%", texto or "")
    if not hallados:
        return ("Optimizando con defrag.exe…", None)
    pct = max(0, min(100, int(hallados[-1])))
    return (f"Optimizando… {pct} %", pct)


def optimizar_volumen(letra: str, es_ssd: bool, al_progreso=None,
                      timeout: int = 1800, intervalo: float = 0.7) -> dict:
    """Optimiza un volumen con VEREDICTO CIERTO (v1.0.15).

    Orden directa del usuario (2026-11-25): «ya no quiero que diga
    no se completó. Busca una solución definitiva». La vía anterior
    (Optimize-Volume + evidencia secundaria) podía cerrar sin
    causa porque un ReTrim de SSD es silencioso por diseño. Ahora:
    pre-chequeos que ya son veredicto (TRIM deshabilitado en
    Windows, servicio defragsvc deshabilitado) y defrag.exe
    elevado con su salida completa y su CÓDIGO DE SALIDA
    capturados: exit 0 = «Optimización finalizada»; exit != 0 =
    la causa sale de la propia salida de defrag o de su código.
    El desenlace «Windows no dio la causa» ya no existe.
    """
    if not es_windows():
        raise WindowsNoDisponible("La optimización solo existe en Windows.")
    letra = (letra or "").strip().rstrip(":").upper()
    if len(letra) != 1 or not letra.isalpha():
        raise ValueError(f"Letra de unidad no válida: {letra!r}")
    nombre_op = "TRIM" if es_ssd else "la desfragmentación"

    carpeta = tempfile.mkdtemp(prefix="ahpc-opt-")
    ruta_salida = os.path.join(carpeta, "salida-defrag.txt")
    ruta_resultado = os.path.join(carpeta, "resultado.txt")
    inicio = time.time()
    try:
        script = _script_defrag(letra, es_ssd, ruta_salida, ruta_resultado)
        try:
            pid = lanzar_elevado_oculto(script)
        except RuntimeError as exc:
            return {"ok": False,
                    "mensaje": (f"La optimización de la unidad {letra}: no "
                                "arrancó: se canceló el aviso de "
                                "administrador de Windows."),
                    "detalle": str(exc)}
        if al_progreso is not None:
            al_progreso("Esperando a que Windows empiece…", None)
        limite = time.time() + timeout
        ultimo_texto = ""
        muerto_desde: float | None = None
        # v1.0.19 (nota 5): el TESTIGO (registro de eventos) se
        # sondea TAMBIÉN durante la espera, no solo tras el
        # fracaso — pero en un HILO APARTE que deposita su
        # veredicto en una casilla: en la Toughbook real defrag
        # terminó bien (evento 258, 09:43:44) y el canal de
        # archivos llegó vacío, así que la app declaró «no se
        # pudo confirmar» a las 09:43:50 teniendo la prueba
        # escrita en el registro. El sondeo jamás corre dentro
        # del bucle: consultar el registro tarda segundos
        # (PowerShell) y bloquearía el progreso — la CI de
        # Windows lo cazó perdiendo el % intermedio de defrag.
        # Un éxito del testigo cierra el veredicto en cuanto
        # aparece; el fracaso por eventos solo se acepta con el
        # proceso ya terminado (vía muerta/recaptura), para no
        # condenar una corrida aún en curso.
        testigo: dict = {"veredicto": None}
        testigo_parar = threading.Event()

        def _sondear_testigo() -> None:
            while not testigo_parar.wait(6):
                try:
                    eventos_t = consultar_eventos_optimizacion(
                        letra, inicio)
                except Exception:
                    continue  # el testigo calla; el canal manda
                veredicto_t = interpretar_eventos_optimizacion(
                    eventos_t, letra)
                if veredicto_t is not None:
                    testigo["veredicto"] = veredicto_t
                    return

        threading.Thread(target=_sondear_testigo,
                         daemon=True).start()
        while time.time() < limite:
            # El resultado solo vale CON CONTENIDO: la escritura
            # es atómica (v1.0.18), así que un archivo vacío no
            # es un veredicto, es un canal aún sin entregar.
            if os.path.isfile(ruta_resultado) and \
                    _leer_texto_tolerante(ruta_resultado).strip():
                break
            texto = _leer_texto_tolerante(ruta_salida)
            if texto != ultimo_texto:
                ultimo_texto = texto
                if al_progreso is not None:
                    fase, pct = _progreso_desde_defrag(texto)
                    try:
                        al_progreso(fase, pct)
                    except Exception:
                        pass  # el progreso jamás tumba el proceso
            por_testigo = testigo["veredicto"]
            if por_testigo is not None and por_testigo["ok"]:
                testigo_parar.set()
                return {"ok": True,
                        "mensaje": (f"Optimización finalizada. "
                                    f"El registro de eventos "
                                    f"de Windows confirma que "
                                    f"la unidad {letra}: quedó "
                                    f"optimizada ({nombre_op})."),
                        "detalle": "Confirmado por el registro "
                                   "de eventos de Windows "
                                   "(optimizador de "
                                   "almacenamiento) durante la "
                                   "espera; el archivo de "
                                   "resultado del ayudante no "
                                   "llegó con contenido."}
            if not _proceso_vivo(pid):
                if muerto_desde is None:
                    muerto_desde = time.time()
                elif time.time() - muerto_desde > 5:
                    # v1.0.18: antes de declarar el fracaso, el
                    # testigo independiente: defrag pudo terminar
                    # y anotarlo en el registro de eventos aunque
                    # el ayudante muriera sin dejar resultado.
                    eventos_muerte = consultar_eventos_optimizacion(
                        letra, inicio)
                    por_eventos = interpretar_eventos_optimizacion(
                        eventos_muerte, letra)
                    if por_eventos is not None and por_eventos["ok"]:
                        testigo_parar.set()
                        return {"ok": True,
                                "mensaje": (f"Optimización "
                                            f"finalizada. El "
                                            f"registro de eventos "
                                            f"de Windows confirma "
                                            f"que la unidad "
                                            f"{letra}: quedó "
                                            f"optimizada "
                                            f"({nombre_op})."),
                                "detalle": "El proceso elevado "
                                           "terminó sin archivo "
                                           "de resultado; el "
                                           "registro de eventos "
                                           "confirma el éxito."}
                    if por_eventos is not None:
                        return {"ok": False,
                                "mensaje": (f"La optimización de "
                                            f"la unidad {letra}: "
                                            "no se completó. Causa "
                                            "según el registro de "
                                            "eventos de Windows: "
                                            f"{(por_eventos.get('causa') or 'sin motivo en el evento.')[:220]}"),
                                "detalle": "El proceso elevado "
                                           "terminó sin archivo "
                                           "de resultado."}
                    testigo_parar.set()
                    return {"ok": False,
                            "mensaje": (f"La optimización de la unidad "
                                        f"{letra}: el proceso elevado de "
                                        "Windows terminó sin dejar un "
                                        "resultado verificable y el "
                                        "registro de eventos no "
                                        "registra esta optimización."),
                            "detalle": "Proceso elevado finalizado sin "
                                       "archivo de resultado ni "
                                       "eventos."}
            time.sleep(intervalo)
        else:
            testigo_parar.set()
            return {"ok": False,
                    "mensaje": (f"La optimización de la unidad {letra}: "
                                "tardó demasiado y se dejó de vigilar. "
                                "Revisa el resultado en la herramienta "
                                "de Windows."),
                    "detalle": f"Tiempo de vigilancia agotado ({timeout} s)."}
        testigo_parar.set()
        resultado = _leer_texto_tolerante(ruta_resultado).strip()
        for _ in range(10):
            if resultado:
                break
            time.sleep(0.2)
            resultado = _leer_texto_tolerante(ruta_resultado).strip()
        salida = _leer_texto_tolerante(ruta_salida)
        error_txt = _leer_texto_tolerante(ruta_salida + ".err")
        if error_txt:
            salida = (salida + "\n" + error_txt).strip()
        desenlace = interpretar_resultado_defrag(
            resultado, salida, letra, nombre_op)
        if desenlace.get("sin_evidencia"):
            # v1.0.18 (nota 3): RECAPTURA dentro del mismo clic —
            # se espera un margen, se releen los archivos (la
            # escritura atómica pudo llegar tras la vigilancia) y
            # se consulta el testigo independiente (el registro
            # de eventos) antes de dar ningún veredicto.
            time.sleep(3)
            resultado2 = _leer_texto_tolerante(ruta_resultado).strip()
            salida2 = _leer_texto_tolerante(ruta_salida)
            error2 = _leer_texto_tolerante(ruta_salida + ".err")
            if error2:
                salida2 = (salida2 + "\n" + error2).strip()
            eventos = consultar_eventos_optimizacion(letra, inicio)
            desenlace = interpretar_resultado_defrag(
                resultado2 or resultado, salida2 or salida,
                letra, nombre_op, eventos=eventos)
        if desenlace["ok"] and al_progreso is not None:
            try:
                al_progreso("Completado", 100)
            except Exception:
                pass
        return desenlace
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)
