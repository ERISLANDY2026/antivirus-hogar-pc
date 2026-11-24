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


def buscar_drivers_windows_update() -> list[dict]:
    """Actualizaciones de tipo Driver ofrecidas por Windows Update."""
    script = (
        "$s = New-Object -ComObject Microsoft.Update.Session; "
        "$b = $s.CreateUpdateSearcher(); "
        "$r = $b.Search(\"Type='Driver' and IsInstalled=0 and IsHidden=0\"); "
        "$r.Updates | ForEach-Object { [PSCustomObject]@{ "
        "Titulo = $_.Title; Id = $_.Identity.UpdateID; "
        "Fecha = [string]$_.LastDeploymentChangeTime } } | ConvertTo-Json"
    )
    datos = como_lista(ejecutar_powershell_json(script, timeout=900))
    return [
        {"titulo": d.get("Titulo", ""), "id": d.get("Id", ""),
         "fecha": d.get("Fecha", ""), "version": ""}
        for d in datos
    ]


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
