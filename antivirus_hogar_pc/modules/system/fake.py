"""Datos fake del Carril C (Ola 0), incluidos casos sin datos."""
from antivirus_hogar_pc.contracts import InformeTuneUp, PartidaLimpieza, SmartInfo
from antivirus_hogar_pc.core.drivers_logic import DriverInstalado, EstadoDriver


def smart_fake() -> list[SmartInfo]:
    return [
        SmartInfo(disco="Samsung SSD 980 500GB", tipo="NVMe", salud="bien",
                  temperatura_c=41, horas_encendido=5210, desgaste_pct=12, errores=0),
        SmartInfo(disco="WD Elements (USB)", tipo="HDD", salud="desconocido",
                  sin_datos=True, detalle="Disco tras puente USB: no se puede leer su salud."),
    ]


def drivers_fake() -> list[EstadoDriver]:
    return [
        EstadoDriver(
            driver=DriverInstalado("Realtek PCIe GbE Family Controller", "10.60.615.2022",
                                   "15/06/2022", "Realtek", "rt640x64.inf"),
            estado="hay_uno_mas_nuevo",
            detalle="Windows Update ofrece una versión más nueva.",
            fuente="Windows Update"),
        EstadoDriver(
            driver=DriverInstalado("NVIDIA GeForce RTX 4060", "32.0.15.6094",
                                   "12/08/2024", "NVIDIA", "nv_dispi.inf"),
            estado="al_dia", detalle="Windows Update no ofrece una versión más nueva."),
        EstadoDriver(
            driver=DriverInstalado("Dispositivo de audio USB", "10.0.22621.1",
                                   "21/06/2022", "Microsoft", "wdma_usb.inf"),
            estado="sin_datos", detalle="Sin datos todavía: pulsa «Escanear drivers»."),
    ]


def tuneup_fake() -> InformeTuneUp:
    return InformeTuneUp(
        partidas=[
            PartidaLimpieza("Temporales del usuario", r"C:\Users\Familia\AppData\Local\Temp", 482_000_000),
            PartidaLimpieza("Temporales de Windows", r"C:\Windows\Temp", 96_000_000),
            PartidaLimpieza("Miniaturas e iconos", r"…\Explorer", 12_000_000),
        ],
        papelera_bytes=210_000_000,
    )
