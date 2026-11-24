"""Discos: salud SMART y optimización con la herramienta de Windows.

Salud: Get-PhysicalDisk (HealthStatus) + Get-StorageReliabilityCounter
(desgaste SSD, temperatura, horas, errores). Muchos discos tras puente USB
o RAID no devuelven contadores: se devuelve None y la UI dice «no se puede
leer», nunca «sano».

Optimización: Optimize-Volume — desfragmenta discos mecánicos (HDD) y hace
ReTrim en SSD. NUNCA desfragmentación clásica sobre un SSD.
"""
from .powershell import como_lista, ejecutar_elevado, ejecutar_powershell_json


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


def optimizar_volumen(letra: str, es_ssd: bool) -> bool:
    """Optimize-Volume con la operación correcta según el medio (elevado)."""
    operacion = "-ReTrim" if es_ssd else "-Defrag"
    return ejecutar_elevado(
        f"Optimize-Volume -DriveLetter {letra} {operacion} -Verbose",
        timeout=1800,
    )
