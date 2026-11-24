"""Base de huellas de malware conocido.

Se carga desde la semilla de fábrica (seed_signatures.txt, formato
«huella  etiqueta») y desde el archivo de firmas extra que escribe la
actualización de amenazas (core/threats_update.py) cuando el usuario la
ejecuta. Soporta SHA-256 (64 hex) y MD5 (32 hex).

Límite honesto (igual que en Android): esto solo detecta malware CONOCIDO y
sin modificar. El motor completo es Microsoft Defender.
"""
import os


class BaseFirmas:
    def __init__(self) -> None:
        self.sha256: dict[str, str] = {}
        self.md5: dict[str, str] = {}

    # -- carga -------------------------------------------------------------
    def cargar_archivo(self, ruta: str) -> int:
        """Carga un archivo de firmas. Devuelve cuántas entradas nuevas."""
        nuevas = 0
        if not ruta or not os.path.isfile(ruta):
            return 0
        with open(ruta, "r", encoding="utf-8", errors="replace") as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith("#"):
                    continue
                partes = linea.split(None, 1)
                huella = partes[0].strip().lower()
                etiqueta = partes[1].strip() if len(partes) > 1 else "Malware conocido"
                if len(huella) == 64 and _es_hex(huella):
                    if huella not in self.sha256:
                        nuevas += 1
                    self.sha256[huella] = etiqueta
                elif len(huella) == 32 and _es_hex(huella):
                    if huella not in self.md5:
                        nuevas += 1
                    self.md5[huella] = etiqueta
        return nuevas

    def cargar_semilla(self, carpeta_activos: str) -> int:
        return self.cargar_archivo(os.path.join(carpeta_activos, "seed_signatures.txt"))

    # -- consulta ----------------------------------------------------------
    def buscar(self, sha256: str = "", md5: str = "") -> str | None:
        """Devuelve la etiqueta si alguna huella coincide; si no, None."""
        if sha256 and sha256.lower() in self.sha256:
            return self.sha256[sha256.lower()]
        if md5 and md5.lower() in self.md5:
            return self.md5[md5.lower()]
        return None

    @property
    def total(self) -> int:
        return len(self.sha256) + len(self.md5)


def _es_hex(texto: str) -> bool:
    try:
        int(texto, 16)
        return True
    except ValueError:
        return False
