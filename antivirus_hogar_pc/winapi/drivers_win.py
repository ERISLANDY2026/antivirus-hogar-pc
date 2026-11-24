"""Drivers en Windows: enumeración, búsqueda en Windows Update e instalación.

- Enumerar: Get-CimInstance Win32_PnPSignedDriver.
- Buscar: API COM de Windows Update con criterio Type='Driver' (prioridad 1
  de la cadena del usuario). Microsoft Update Catalog queda como respaldo
  web (core.drivers_logic.consulta_catalogo).
- Instalar: el propio Windows Update (descargador/instalador COM), siempre
  tras crear un punto de restauración y solo drivers firmados (Windows
  Update solo sirve drivers firmados por Microsoft).
"""
from ..core.drivers_logic import DriverInstalado
from .powershell import como_lista, ejecutar_elevado, ejecutar_powershell_json


def enumerar_drivers() -> list[DriverInstalado]:
    script = (
        "Get-CimInstance Win32_PnPSignedDriver | "
        "Select-Object DeviceName, DriverVersion, DriverDate, Manufacturer, "
        "InfName, DeviceID, IsSigned | ConvertTo-Json"
    )
    datos = como_lista(ejecutar_powershell_json(script, timeout=300))
    if not datos:
        # En un Windows real esta consulta SIEMPRE devuelve decenas de
        # drivers: vacío = la consulta CIM falló en silencio, y eso debe
        # verse como error con causa, no como «0 drivers» (bug 5).
        raise RuntimeError(
            "La consulta de drivers de Windows (Win32_PnPSignedDriver) no "
            "devolvió ningún dato: PowerShell no pudo leer la lista de "
            "drivers de esta PC.")
    drivers: list[DriverInstalado] = []
    for d in datos:
        nombre = (d.get("DeviceName") or "").strip()
        if not nombre:
            continue
        drivers.append(DriverInstalado(
            dispositivo=nombre,
            version=str(d.get("DriverVersion") or ""),
            fecha=_fecha_legible(d.get("DriverDate")),
            fabricante=str(d.get("Manufacturer") or ""),
            inf=str(d.get("InfName") or ""),
            device_id=str(d.get("DeviceID") or ""),
            firmado=bool(d.get("IsSigned")),
        ))
    drivers.sort(key=lambda x: x.dispositivo.lower())
    return drivers


def _fecha_legible(valor) -> str:
    texto = str(valor or "")
    # CIM serializa como /Date(ms)/ vía ConvertTo-Json clásico o ISO.
    if texto.startswith("/Date("):
        from .defender import _parsear_fecha_ms

        fecha = _parsear_fecha_ms(texto)
        return fecha.strftime("%d/%m/%Y") if fecha else ""
    return texto[:10]


def buscar_drivers_windows_update(timeout: int = 240) -> list[dict]:
    """Actualizaciones de tipo Driver ofrecidas por Windows Update.

    v1.0.3 (problema «todo Sin confirmar»): la búsqueda va envuelta en
    try/catch y devuelve un JSON ESTRUCTURADO {ok, codigo, causa,
    actualizaciones}. Antes, si el COM de búsqueda fallaba, PowerShell
    terminaba sin salida útil y el resultado vacío se confundía con
    «no hay novedades»: TODOS los drivers quedaban «Sin confirmar» sin
    que nadie supiera por qué. Ahora:
    - Búsqueda completada (ResultCode 2 o 3), ofrezca 0 o N: se devuelve
      la lista (vacía = sin novedades, la consulta SÍ se hizo).
    - Búsqueda fallida o incompleta: se LANZA RuntimeError con la causa
      real (mensaje/HRESULT de Windows Update) para que la app la
      enseñe; nada de vacío silencioso.

    v1.0.5: el límite baja de 900 s a 240 s — en la Toughbook del
    usuario la búsqueda agotó los 900 s y dejó los 196 drivers sin
    confirmar; ahora es solo UNA fuente de la cadena (Catálogo antes,
    almacén después) y va con reintento (buscar_drivers_wu_con_reintento)."""
    script = (
        "$ErrorActionPreference = 'Stop'; "
        "try { "
        "$s = New-Object -ComObject Microsoft.Update.Session; "
        "$b = $s.CreateUpdateSearcher(); "
        "$r = $b.Search(\"Type='Driver' and IsInstalled=0 and IsHidden=0\"); "
        "$cod = [int]$r.ResultCode; "
        "$ups = @($r.Updates | ForEach-Object { [PSCustomObject]@{ "
        "Titulo = $_.Title; Id = $_.Identity.UpdateID; "
        "Fecha = [string]$_.LastDeploymentChangeTime } }); "
        "$bien = ($cod -eq 2 -or $cod -eq 3); "
        "$causa = ''; if (-not $bien) { $causa = "
        "\"Windows Update terminó la búsqueda con código $cod "
        "(2=correcta, 3=correcta con avisos)\" }; "
        "[PSCustomObject]@{ ok = $bien; codigo = $cod; causa = $causa; "
        "actualizaciones = $ups } | ConvertTo-Json -Depth 4 "
        "} catch { "
        "[PSCustomObject]@{ ok = $false; codigo = -1; "
        "causa = $_.Exception.Message; actualizaciones = @() } "
        "| ConvertTo-Json -Depth 4 }"
    )
    datos = ejecutar_powershell_json(script, timeout=timeout)
    if not isinstance(datos, dict) or "ok" not in datos:
        raise RuntimeError(
            "Windows Update no devolvió una respuesta interpretable "
            "al buscar drivers (la búsqueda COM no completó).")
    if not datos.get("ok"):
        causa = str(datos.get("causa") or "").strip()
        raise RuntimeError(
            "La búsqueda de drivers en Windows Update falló"
            + (f": {causa}" if causa else " sin detalle de Windows."))
    return [
        {"titulo": d.get("Titulo", ""), "id": d.get("Id", ""),
         "fecha": d.get("Fecha", ""), "version": ""}
        for d in como_lista(datos.get("actualizaciones"))
    ]


def buscar_drivers_wu_con_reintento(timeout: int = 240,
                                    intentos: int = 2) -> list[dict]:
    """La búsqueda COM de Windows Update con UN reintento automático
    (v1.0.5): si el primer intento agota el tiempo o falla, se prueba
    otra vez antes de dar la fuente por caída. Lanza la última causa."""
    ultimo: Exception | None = None
    for _ in range(max(1, intentos)):
        try:
            return buscar_drivers_windows_update(timeout=timeout)
        except Exception as exc:
            ultimo = exc
    assert ultimo is not None
    raise ultimo


def paquetes_almacen_drivers(timeout: int = 120) -> list[dict]:
    """Paquetes del almacén de drivers (pnputil /enum-drivers), ya
    parseados: la fuente LOCAL de la cadena de confirmación (v1.0.5).
    Proceso oculto, como todo PowerShell de la app."""
    from ..core.drivers_logic import parsear_pnputil
    from .powershell import ejecutar_powershell

    texto = ejecutar_powershell("pnputil /enum-drivers | Out-String -Width 300",
                                timeout=timeout)
    return parsear_pnputil(texto)


def crear_punto_restauracion(descripcion: str = "Antivirus Hogar PC — antes de actualizar drivers") -> bool:
    """Checkpoint-Computer (elevado). Puede fallar si la protección del
    sistema está desactivada en la unidad: se intenta activarla primero."""
    desc = descripcion.replace("'", "''")
    script = (
        "try { Enable-ComputerRestore -Drive 'C:\\' -ErrorAction SilentlyContinue } catch {} "
        f"Checkpoint-Computer -Description '{desc}' -RestorePointType 'MODIFY_SETTINGS'"
    )
    return ejecutar_elevado(script, timeout=300)


def instalar_drivers_windows_update(ids: list[str] | None = None) -> bool:
    """Descarga e instala (elevado) las actualizaciones de driver ofrecidas.
    Si `ids` viene, solo esas; si no, todas las de tipo Driver pendientes."""
    filtro_ids = ""
    if ids:
        lista = ",".join(f"'{i}'" for i in ids)
        filtro_ids = f" | Where-Object {{ @({lista}) -contains $_.Identity.UpdateID }}"
    script = (
        "$s = New-Object -ComObject Microsoft.Update.Session; "
        "$b = $s.CreateUpdateSearcher(); "
        "$r = $b.Search(\"Type='Driver' and IsInstalled=0 and IsHidden=0\"); "
        f"$pendientes = $r.Updates{filtro_ids}; "
        "if ($pendientes.Count -eq 0) { exit 3 } "
        "$col = New-Object -ComObject Microsoft.Update.UpdateColl; "
        "foreach ($u in $pendientes) { if (-not $u.EulaAccepted) { $u.AcceptEula() } "
        "[void]$col.Add($u) } "
        "$d = $s.CreateUpdateDownloader(); $d.Updates = $col; [void]$d.Download(); "
        "$i = $s.CreateUpdateInstaller(); $i.Updates = $col; "
        "$res = $i.Install(); exit $res.ResultCode"
    )
    # ResultCode 2 = Succeeded, 3 = SucceededWithErrors: ambos aceptables.
    return ejecutar_elevado(script, timeout=1800)
