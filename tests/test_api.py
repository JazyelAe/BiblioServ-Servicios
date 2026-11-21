"""Pruebas de los servicios de BiblioServ con el cliente de pruebas de Flask.
Ejecutar:  pytest -v"""
import os
import sys
import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import crear_app  # noqa: E402
import externo  # noqa: E402


@pytest.fixture
def cliente(tmp_path):
    """Cada prueba usa una base nueva con los 5 libros de ejemplo."""
    app = crear_app({"DATABASE": str(tmp_path / "prueba.db"), "SECRET_KEY": "clave-de-prueba"})
    return app.test_client()


@pytest.fixture
def token(cliente):
    r = cliente.post("/api/login", json={"usuario": "bibliotecario", "password": "demo1234"})
    return {"Authorization": "Bearer " + r.get_json()["token"]}


# ---------- Servicio de catálogo (lectura pública) ----------
def test_lista_publica_sin_token(cliente):
    r = cliente.get("/api/libros")
    assert r.status_code == 200
    assert len(r.get_json()) == 5


def test_busqueda_en_catalogo(cliente):
    libros = cliente.get("/api/libros?q=rulfo").get_json()
    assert [l["titulo"] for l in libros] == ["Pedro Páramo"]


def test_libro_inexistente_404(cliente):
    assert cliente.get("/api/libros/999").status_code == 404


# ---------- Servicio de autenticación ----------
def test_login_correcto_e_incorrecto(cliente):
    ok = cliente.post("/api/login", json={"usuario": "bibliotecario", "password": "demo1234"})
    assert ok.status_code == 200 and ok.get_json()["token"]
    mal = cliente.post("/api/login", json={"usuario": "bibliotecario", "password": "otra"})
    assert mal.status_code == 401


def test_escrituras_sin_token_401(cliente):
    assert cliente.post("/api/libros", json={"titulo": "X", "autor": "Y"}).status_code == 401
    assert cliente.put("/api/libros/1", json={"disponible": False}).status_code == 401
    assert cliente.delete("/api/libros/1").status_code == 401
    falso = {"Authorization": "Bearer token-inventado"}
    assert cliente.delete("/api/libros/1", headers=falso).status_code == 401


def test_token_caducado_401(tmp_path):
    app = crear_app({"DATABASE": str(tmp_path / "p.db"), "TOKEN_SEGUNDOS": -1})
    c = app.test_client()
    t = c.post("/api/login", json={"usuario": "bibliotecario", "password": "demo1234"}).get_json()["token"]
    r = c.get("/api/perfil", headers={"Authorization": "Bearer " + t})
    assert r.status_code == 401 and "caducó" in r.get_json()["error"]


def test_perfil_con_token(cliente, token):
    assert cliente.get("/api/perfil", headers=token).get_json()["usuario"] == "bibliotecario"


# ---------- CRUD con token ----------
def test_crear_y_consultar(cliente, token):
    nuevo = {"titulo": "Aura", "autor": "Carlos Fuentes", "anio": 1962, "isbn": "9789681900135"}
    r = cliente.post("/api/libros", json=nuevo, headers=token)
    assert r.status_code == 201
    libro = cliente.get(f"/api/libros/{r.get_json()['id']}").get_json()
    assert libro["titulo"] == "Aura" and libro["disponible"] is True


def test_validacion_400(cliente, token):
    assert cliente.post("/api/libros", json={"autor": "Sin título"}, headers=token).status_code == 400
    assert cliente.post("/api/libros", json={"titulo": "A", "autor": "B", "anio": "abc"}, headers=token).status_code == 400


def test_editar_y_prestar(cliente, token):
    r = cliente.put("/api/libros/1", json={"titulo": "Cien años de soledad (ed. RAE)", "disponible": False}, headers=token)
    assert r.status_code == 200
    assert r.get_json()["titulo"].endswith("(ed. RAE)") and r.get_json()["disponible"] is False
    assert cliente.put("/api/libros/999", json={"disponible": True}, headers=token).status_code == 404


def test_borrar(cliente, token):
    assert cliente.delete("/api/libros/2", headers=token).status_code == 204
    assert cliente.get("/api/libros/2").status_code == 404


# ---------- Servicio externo (Open Library), simulado para no depender de Internet ----------
class RespuestaFalsa:
    def raise_for_status(self):
        pass

    def json(self):
        return {"docs": [{"title": "Pedro Páramo", "author_name": ["Juan Rulfo"], "first_publish_year": 1955,
                          "isbn": ["0802133908", "9780802133908"], "cover_i": 123}]}


def test_externo_simplifica_open_library(cliente, monkeypatch):
    llamadas = {}

    def get_falso(url, params, headers, timeout):
        llamadas.update(params)
        return RespuestaFalsa()

    monkeypatch.setattr(externo.requests, "get", get_falso)
    r = cliente.get("/api/externo/buscar?q=978-0802133908")
    assert llamadas["isbn"] == "9780802133908"  # detecta que es un ISBN
    libro = r.get_json()["resultados"][0]
    assert libro == {"titulo": "Pedro Páramo", "autor": "Juan Rulfo", "anio": 1955, "isbn": "9780802133908",
                     "portada": "https://covers.openlibrary.org/b/id/123-M.jpg"}


def test_externo_errores(cliente, monkeypatch):
    assert cliente.get("/api/externo/buscar?q=").status_code == 400

    def falla(*a, **k):
        raise requests.ConnectionError("sin red")

    monkeypatch.setattr(externo.requests, "get", falla)
    assert cliente.get("/api/externo/buscar?q=rulfo").status_code == 502


# ---------- CORS ----------
def test_cors_solo_para_pages(cliente):
    ok = cliente.get("/api/libros", headers={"Origin": "https://jazyelae.github.io"})
    assert ok.headers.get("Access-Control-Allow-Origin") == "https://jazyelae.github.io"
    otro = cliente.get("/api/libros", headers={"Origin": "https://sitio-ajeno.example"})
    assert "Access-Control-Allow-Origin" not in otro.headers
