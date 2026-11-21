"""Consumo de un servicio EXTERNO: la API pública de Open Library (Internet Archive).
El catálogo la consulta por HTTP/JSON y entrega al cliente solo los datos que necesita."""
import re
import requests
from flask import Blueprint, jsonify, request

externo = Blueprint("externo", __name__, url_prefix="/api/externo")
URL_OPEN_LIBRARY = "https://openlibrary.org/search.json"
# Open Library pide identificar a la aplicación en el User-Agent.
ENCABEZADOS = {"User-Agent": "BiblioServ/1.0 (proyecto escolar UTP)"}


def es_isbn(texto):
    return re.fullmatch(r"[\dXx-]{10,17}", texto) is not None


def simplificar(doc):
    """Toma un resultado de Open Library y deja solo los campos de un libro de BiblioServ."""
    isbns = doc.get("isbn") or []
    isbn = next((i for i in isbns if len(i) == 13), isbns[0] if isbns else "")
    return {
        "titulo": doc.get("title", ""),
        "autor": ", ".join((doc.get("author_name") or [])[:2]),
        "anio": doc.get("first_publish_year"),
        "isbn": isbn,
        "portada": f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-M.jpg" if doc.get("cover_i") else "",
    }


@externo.get("/buscar")
def buscar():
    """GET /api/externo/buscar?q=título o ISBN"""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify(error="Escribe un título o un ISBN"), 400
    parametros = {"limit": 5, "fields": "title,author_name,first_publish_year,isbn,cover_i"}
    if es_isbn(q):
        parametros["isbn"] = q.replace("-", "")
    else:
        parametros["q"] = q
    try:
        respuesta = requests.get(URL_OPEN_LIBRARY, params=parametros, headers=ENCABEZADOS, timeout=10)
        respuesta.raise_for_status()
        docs = respuesta.json().get("docs", [])
    except (requests.RequestException, ValueError):
        return jsonify(error="Open Library no respondió; intenta más tarde"), 502
    return jsonify(fuente="Open Library", resultados=[simplificar(d) for d in docs])
