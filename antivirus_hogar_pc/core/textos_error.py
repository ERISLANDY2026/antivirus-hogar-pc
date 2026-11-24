"""Mensajes de error comprensibles para el usuario (v1.0.4).

La UI nunca debe enseñar el texto técnico crudo de una librería (en
inglés, pensado para programadores): se traduce a una frase clara en
español y el detalle técnico queda solo en el registro de actividad,
donde sí sirve para diagnosticar.
"""
import sqlite3


def mensaje_para_usuario(exc: BaseException) -> str:
    """Frase en español claro para enseñar en pantalla."""
    texto = str(exc)
    if (
        "created in a thread" in texto
        or "can only be used in that same thread" in texto
        or isinstance(exc, sqlite3.ProgrammingError)
    ):
        return (
            "La base de datos interna de la app chocó con otra tarea en "
            "curso. Cierra la app, vuelve a abrirla e inténtalo de nuevo."
        )
    if isinstance(exc, sqlite3.Error) or "sqlite" in texto.lower():
        return (
            "Hubo un problema con la base de datos interna de la app. "
            "Cierra la app, vuelve a abrirla e inténtalo de nuevo."
        )
    if isinstance(exc, PermissionError):
        return (
            "Windows no dio permiso para leer o escribir algo que la app "
            "necesita. Prueba a abrir la app como administrador."
        )
    if isinstance(exc, FileNotFoundError):
        return "No se encontró un archivo o carpeta que la app necesitaba."
    return texto
