"""Servicio de autenticación: entrega tokens firmados y protege las rutas de escritura.

El token está FIRMADO con SECRET_KEY (itsdangerous, viene con Flask): el servidor no necesita
guardarlo en memoria; solo comprueba la firma y la fecha. Así sigue valiendo aunque el proceso reinicie."""
from functools import wraps
from flask import Blueprint, current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

autenticacion = Blueprint("autenticacion", __name__, url_prefix="/api")


def _firmador():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="biblioserv-token")


def _usuarios():
    # Usuario de demostración. La contraseña puede cambiarse con la variable de entorno DEMO_PASSWORD.
    return {"bibliotecario": current_app.config["DEMO_PASSWORD"]}


@autenticacion.post("/login")
def login():
    datos = request.get_json(silent=True) or {}
    usuario, password = datos.get("usuario"), datos.get("password")
    if not usuario or _usuarios().get(usuario) != password:
        return jsonify(error="Usuario o contraseña incorrectos"), 401
    token = _firmador().dumps({"usuario": usuario})
    return jsonify(usuario=usuario, token=token, expira_en_horas=current_app.config["TOKEN_SEGUNDOS"] // 3600)


def requiere_token(funcion):
    """Decorador: la ruta solo se ejecuta si llega 'Authorization: Bearer <token>' válido."""
    @wraps(funcion)
    def envoltura(*args, **kwargs):
        encabezado = request.headers.get("Authorization", "")
        token = encabezado.split(" ", 1)[1] if " " in encabezado else ""
        try:
            datos = _firmador().loads(token, max_age=current_app.config["TOKEN_SEGUNDOS"])
        except SignatureExpired:
            return jsonify(error="El token caducó; inicia sesión otra vez"), 401
        except BadSignature:
            return jsonify(error="Falta el token o no es válido"), 401
        g.usuario = datos["usuario"]
        return funcion(*args, **kwargs)
    return envoltura


@autenticacion.get("/perfil")
@requiere_token
def perfil():
    return jsonify(usuario=g.usuario, rol="Bibliotecario")
