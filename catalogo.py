"""Servicio de catálogo: API REST de libros (CRUD) sobre SQLite.
Leer es público; crear, editar y borrar requiere el token del servicio de autenticación."""
from flask import Blueprint, jsonify, request
from autenticacion import requiere_token
from basedatos import a_diccionario, conexion

catalogo = Blueprint("catalogo", __name__, url_prefix="/api/libros")
CAMPOS_TEXTO = ("titulo", "autor", "isbn", "portada")


def validar(datos, parcial=False):
    """Revisa y limpia los datos de un libro. Regresa (libro, None) o (None, mensaje de error).
    parcial=True (PUT) permite mandar solo algunos campos."""
    if not isinstance(datos, dict):
        return None, "Se esperaba un objeto JSON"
    libro = {}
    for campo in CAMPOS_TEXTO:
        if campo in datos:
            valor = datos[campo]
            if valor is not None and not isinstance(valor, str):
                return None, f"«{campo}» debe ser texto"
            libro[campo] = (valor or "").strip()
    for campo in ("titulo", "autor"):
        if (not parcial or campo in libro) and not libro.get(campo):
            return None, f"El campo «{campo}» es obligatorio"
    if datos.get("anio") not in (None, ""):
        try:
            libro["anio"] = int(datos["anio"])
        except (TypeError, ValueError):
            return None, "«anio» debe ser un número"
        if not 0 < libro["anio"] <= 2100:
            return None, "«anio» no es válido"
    elif "anio" in datos:
        libro["anio"] = None
    if "disponible" in datos:
        libro["disponible"] = 1 if datos["disponible"] else 0
    return libro, None


def buscar_libro(id_libro):
    return conexion().execute("SELECT * FROM libros WHERE id = ?", (id_libro,)).fetchone()


@catalogo.get("")
def listar():
    """GET /api/libros?q=texto — busca en título, autor o ISBN."""
    q = f"%{request.args.get('q', '').strip()}%"
    filas = conexion().execute(
        "SELECT * FROM libros WHERE titulo LIKE ? OR autor LIKE ? OR isbn LIKE ? ORDER BY id", (q, q, q))
    return jsonify([a_diccionario(f) for f in filas])


@catalogo.get("/<int:id_libro>")
def obtener(id_libro):
    fila = buscar_libro(id_libro)
    if fila is None:
        return jsonify(error="No existe ese libro"), 404
    return jsonify(a_diccionario(fila))


@catalogo.post("")
@requiere_token
def crear():
    libro, error = validar(request.get_json(silent=True))
    if error:
        return jsonify(error=error), 400
    libro.setdefault("disponible", 1)
    campos = list(libro)
    cursor = conexion().execute(
        f"INSERT INTO libros({', '.join(campos)}) VALUES ({', '.join('?' * len(campos))})",
        [libro[c] for c in campos])
    conexion().commit()
    return jsonify(a_diccionario(buscar_libro(cursor.lastrowid))), 201


@catalogo.put("/<int:id_libro>")
@requiere_token
def actualizar(id_libro):
    if buscar_libro(id_libro) is None:
        return jsonify(error="No existe ese libro"), 404
    cambios, error = validar(request.get_json(silent=True), parcial=True)
    if error:
        return jsonify(error=error), 400
    if cambios:
        asignaciones = ", ".join(f"{c} = ?" for c in cambios)
        conexion().execute(f"UPDATE libros SET {asignaciones} WHERE id = ?", [*cambios.values(), id_libro])
        conexion().commit()
    return jsonify(a_diccionario(buscar_libro(id_libro)))


@catalogo.delete("/<int:id_libro>")
@requiere_token
def borrar(id_libro):
    if buscar_libro(id_libro) is None:
        return jsonify(error="No existe ese libro"), 404
    conexion().execute("DELETE FROM libros WHERE id = ?", (id_libro,))
    conexion().commit()
    return "", 204
