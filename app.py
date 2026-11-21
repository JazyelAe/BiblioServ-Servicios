"""BiblioServ · aplicación orientada a servicios.
Une los servicios (autenticación, catálogo y consumo de Open Library) en una sola API Flask.
Local:      python app.py          → http://127.0.0.1:5000
Producción: gunicorn app:app       (Render, ver render.yaml)"""
import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

import basedatos
from autenticacion import autenticacion
from catalogo import catalogo
from externo import externo

CARPETA = os.path.dirname(os.path.abspath(__file__))


def crear_app(config=None):
    app = Flask(__name__)
    app.config.update(
        # En Render, SECRET_KEY la genera la plataforma (render.yaml). El valor por defecto es solo para desarrollo.
        SECRET_KEY=os.environ.get("SECRET_KEY", "solo-para-desarrollo"),
        DEMO_PASSWORD=os.environ.get("DEMO_PASSWORD", "demo1234"),
        DATABASE=os.environ.get("BIBLIO_DB", os.path.join(CARPETA, "biblioteca.db")),
        TOKEN_SEGUNDOS=8 * 3600,
        ORIGENES_CORS=os.environ.get(
            "ORIGENES_CORS", "https://jazyelae.github.io,http://localhost:8000,http://127.0.0.1:8000").split(","),
    )
    if config:
        app.config.update(config)
    app.url_map.strict_slashes = False  # /api/libros y /api/libros/ funcionan igual
    app.json.ensure_ascii = False       # acentos legibles en el JSON ("Páramo", no "Páramo")
    app.json.sort_keys = False          # los campos salen en el orden de la tabla

    # CORS: solo el cliente publicado en GitHub Pages (y el local) puede llamar a la API desde el navegador.
    CORS(app, origins=app.config["ORIGENES_CORS"])

    basedatos.inicializar(app.config["DATABASE"])
    app.teardown_appcontext(basedatos.cerrar)
    for servicio in (autenticacion, catalogo, externo):
        app.register_blueprint(servicio)

    @app.get("/")
    def inicio():
        return jsonify(
            servicio="BiblioServ",
            descripcion="API REST de una biblioteca escolar orientada a servicios",
            documentacion="/docs",
            servicios={
                "autenticacion": ["POST /api/login", "GET /api/perfil"],
                "catalogo": ["GET /api/libros", "GET /api/libros/<id>", "POST /api/libros",
                             "PUT /api/libros/<id>", "DELETE /api/libros/<id>"],
                "externo": ["GET /api/externo/buscar?q="],
            },
        )

    # Documentación de la API: Swagger UI lee openapi.yaml
    @app.get("/docs")
    def docs():
        return send_from_directory(os.path.join(CARPETA, "docs"), "swagger.html")

    @app.get("/openapi.yaml")
    def openapi():
        return send_from_directory(os.path.join(CARPETA, "docs"), "openapi.yaml", mimetype="text/yaml")

    @app.errorhandler(404)
    def no_encontrado(_):
        return jsonify(error="Ruta no encontrada"), 404

    @app.errorhandler(405)
    def metodo_no_permitido(_):
        return jsonify(error="Método no permitido en esta ruta"), 405

    return app


app = crear_app()

if __name__ == "__main__":
    app.run(port=5000, debug=False)
