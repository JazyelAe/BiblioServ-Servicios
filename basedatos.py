"""Base de datos SQLite del servicio de catálogo.
Se crea y se llena con libros de ejemplo al arrancar la aplicación (también con gunicorn y en las pruebas)."""
import sqlite3
from flask import current_app, g

LIBROS_EJEMPLO = [
    # (titulo, autor, año, isbn, disponible)
    ("Cien años de soledad", "Gabriel García Márquez", 1967, "9780307474728", 1),
    ("El laberinto de la soledad", "Octavio Paz", 1950, "9780140183108", 1),
    ("Pedro Páramo", "Juan Rulfo", 1955, "9780802133908", 0),
    ("Como agua para chocolate", "Laura Esquivel", 1989, "9780385420174", 1),
    ("La muerte de Artemio Cruz", "Carlos Fuentes", 1962, "9780374522834", 1),
]


def inicializar(ruta):
    """Crea la tabla si no existe y agrega los libros de ejemplo si está vacía."""
    con = sqlite3.connect(ruta)
    con.execute("""CREATE TABLE IF NOT EXISTS libros(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL,
        autor TEXT NOT NULL,
        anio INTEGER,
        isbn TEXT,
        portada TEXT,
        disponible INTEGER NOT NULL DEFAULT 1)""")
    if con.execute("SELECT COUNT(*) FROM libros").fetchone()[0] == 0:
        con.executemany(
            "INSERT INTO libros(titulo, autor, anio, isbn, disponible) VALUES (?, ?, ?, ?, ?)", LIBROS_EJEMPLO)
    con.commit()
    con.close()


def conexion():
    """Una conexión por petición, guardada en g y cerrada al terminar (ver cerrar)."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def cerrar(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def a_diccionario(fila):
    """Convierte una fila de SQLite al JSON que entrega la API."""
    libro = dict(fila)
    libro["disponible"] = bool(libro["disponible"])
    return libro
