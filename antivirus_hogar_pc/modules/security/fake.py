"""Datos fake del Carril B (Ola 0)."""
from antivirus_hogar_pc.contracts import HostsEstado
from antivirus_hogar_pc.core.scanner import Hallazgo, ResultadoEscaneo


def escaneo_fake() -> ResultadoEscaneo:
    resultado = ResultadoEscaneo(archivos_revisados=1240, archivos_desde_cache=1180, errores=2)
    resultado.hallazgos = [
        Hallazgo(
            ruta=r"C:\Users\Familia\Downloads\instalador_gratis.exe",
            sha256="275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f",
            md5="44d88612fea8a8f36de82e1278abb02f",
            etiqueta="EICAR-Test-File (archivo de prueba antivirus)",
            tamano=68,
        )
    ]
    return resultado


def hosts_fake() -> HostsEstado:
    return HostsEstado(activo=True, dominios_bloqueados=19563, base_usada="semilla",
                       ruta_respaldo="", dns_reforzado=False)
