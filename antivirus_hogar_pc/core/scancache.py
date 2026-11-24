"""Caché incremental de escaneo (SQLite).

Guarda por archivo: ruta, tamaño, fecha de modificación (mtime) y huellas.
Si un archivo no cambió de tamaño ni de fecha, se reutilizan sus huellas
sin volver a leerlo — igual que el ScanCache de la v6 de Android.

Tradeoff declarado (el mismo de Android): un archivo que cambiara su
contenido sin cambiar tamaño ni fecha escaparía a esta caché. Mitigación:
los ejecutables de Descargas se re-hashean siempre (ver scanner.py).
"""
import os
import sqlite3
import time


class CacheEscaneo:
    def __init__(self, ruta_bd: str) -> None:
        self.ruta_bd = ruta_bd
        os.makedirs(os.path.dirname(ruta_bd), exist_ok=True)
        self._con = sqlite3.connect(ruta_bd)
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS archivos (
                ruta TEXT PRIMARY KEY,
                tamano INTEGER NOT NULL,
                mtime REAL NOT NULL,
                sha256 TEXT NOT NULL,
                md5 TEXT NOT NULL,
                escaneado_en REAL NOT NULL
            )
            """
        )
        self._con.commit()

    def buscar(self, ruta: str, tamano: int, mtime: float) -> tuple[str, str] | None:
        """(sha256, md5) si hay una entrada válida para ese estado del archivo."""
        cur = self._con.execute(
            "SELECT sha256, md5 FROM archivos WHERE ruta=? AND tamano=? AND mtime=?",
            (ruta, tamano, mtime),
        )
        fila = cur.fetchone()
        if fila:
            return fila[0], fila[1]
        return None

    def guardar(self, ruta: str, tamano: int, mtime: float, sha256: str, md5: str) -> None:
        self._con.execute(
            "INSERT OR REPLACE INTO archivos (ruta, tamano, mtime, sha256, md5, escaneado_en)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (ruta, tamano, mtime, sha256, md5, time.time()),
        )

    def confirmar(self) -> None:
        self._con.commit()

    def total(self) -> int:
        cur = self._con.execute("SELECT COUNT(*) FROM archivos")
        return int(cur.fetchone()[0])

    def cerrar(self) -> None:
        try:
            self._con.commit()
            self._con.close()
        except sqlite3.Error:
            pass
