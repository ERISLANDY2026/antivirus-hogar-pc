"""Datos fake del Panel (Ola 0): forma realista, incluidos casos límite."""
from antivirus_hogar_pc.contracts import DatosPanel, InformeSalud
from antivirus_hogar_pc.core.health import EstadoSalud, calcular_salud


def informe_fake() -> InformeSalud:
    estado = EstadoSalud(
        defender_activo=True, defender_firmas_al_dia=True,
        firewall_activo=True, windows_al_dia=False, windows_con_soporte=False,
        cfa_activo=False, hallazgos_recientes=0, disco_sano=True,
        entradas_arranque=9,
    )
    return InformeSalud(
        salud=calcular_salud(estado),
        defender={"activo": True, "tiempo_real": True, "version_firmas": "1.421.1507.0",
                  "firmas_al_dia": True, "tamper_protection": True},
        firewall_activo=True,
        actualizaciones_windows=3,
        windows_sin_soporte=True,
        cfa={"valor": 0, "texto": "Desactivada", "activo": False},
        panel=DatosPanel(cpu_pct=23.0, ram_pct=54.0, ram_usada_gb=8.6, ram_total_gb=16.0,
                         disco_sistema_pct=61.0, disco_libre_gb=178.0, disco_total_gb=456.0,
                         tiempo_encendido_h=26.5),
        ultimo_escaneo={"revisados": 1240, "hallazgos": 0},
    )
