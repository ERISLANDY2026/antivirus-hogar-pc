"""Caché incremental de escaneo (SQLite).

Guarda por archivo: ruta, tamaño, fecha de modificación (mtime) y huellas.
Si un archivo no cambió de tamaño ni de fecha, se reutilizan sus huellas
sin volver a leerlo — igual que el ScanCache de la v6 de Android.

Tradeoff declarado (el mismo de Android): un archivo que cambiara su
contenido sin cambiar tamaño ni fecha escaparía a esta caché. Mitigación:
los ejecutables de Descargas se re-hashean siempre (ver scanner.py).

HILOS (v1.0.4): la caché se CREA en el hilo principal de la ventana
(ServiciosApp) pero el escaneo la USA dentro de su QThread trabajador.
sqlite3 prohíbe usar una conexión en un hilo distinto al que la creó
(«SQLite objects created in a thread can only be used in that same
thread» — el fallo que el usuario vio en el escaneo rápido de la
v1.0.3). Por eso cada hilo tiene SU PROPIA conexión (threading.local)
sobre el mismo archivo: la conexión nace en el hilo que la usa, que es
lo que sqlite exige, y un Lock serializa las escrituras entre hilos.
"""
import os
import sqlite3
import threading
import time


class CacheEscaneo:
    def __init__(self, ruta_bd: str) -> None:
        self.ruta_bd = ruta_bd
        os.makedirs(os.path.dirname(ruta_bd), exist_ok=True)
        self._local = threading.local()
        self._conexiones: set[sqlite3.Connection] = set()
        self._cerrojo_registro = threading.Lock()
        self._cerrojo_escritura = threading.Lock()
        # Crea la tabla ya, en el hilo que construye la caché.
        self._conexion().execute(
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
        self._conexion().commit()

    # -- conexión por hilo -------------------------------------------------
    def _conexion(self) -> sqlite3.Connection:
        """La conexión DE ESTE HILO (se crea la primera vez que la pide)."""
        con = getattr(self._local, "con", None)
        if con is None:
            con = sqlite3.connect(self.ruta_bd, timeout=30)
            try:
                con.execute("PRAGMA journal_mode=WAL")
            except sqlite3.Error:
                pass  # WAL es una mejora de concurrencia, no un requisito
            con.execute(
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
            con.commit()
            with self._cerrojo_registro:
                self._conexiones.add(con)
            self._local.con = con
        return con

    # Compatibilidad: el atributo histórico apunta a la conexión del hilo
    # que lo pide (nunca a una creada en otro hilo).
    @property
    def _con(self) -> sqlite3.Connection:
        return self._conexion()

    @_con.setter
    def _con(self, valor) -> None:
        self._local.con = valor

    # -- API ---------------------------------------------------------------
    def buscar(self, ruta: str, tamano: int, mtime: float) -> tuple[str, str] | None:
        """(sha256, md5) si hay una entrada válida para ese estado del archivo."""
        cur = self._conexion().execute(
            "SELECT sha256, md5 FROM archivos WHERE ruta=? AND tamano=? AND mtime=?",
            (ruta, tamano, mtime),
        )
        fila = cur.fetchone()
        if fila:
            return fila[0], fila[1]
        return None

    def guardar(self, ruta: str, tamano: int, mtime: float, sha256: str, md5: str) -> None:
        with self._cerrojo_escritura:
            self._conexion().execute(
                "INSERT OR REPLACE INTO archivos (ruta, tamano, mtime, sha256, md5, escaneado_en)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (ruta, tamano, mtime, sha256, md5, time.time()),
            )

    def confirmar(self) -> None:
        with self._cerrojo_escritura:
            self._conexion().commit()

    def total(self) -> int:
        cur = self._conexion().execute("SELECT COUNT(*) FROM archivos")
        return int(cur.fetchone()[0])

    def cerrar(self) -> None:
        with self._cerrojo_registro:
            conexiones = list(self._conexiones)
            self._conexiones.clear()
        for con in conexiones:
            try:
                con.commit()
                con.close()
            except sqlite3.Error:
                pass
        self._local.con = None
