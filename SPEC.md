# SPEC · BiblioServ — Subproducto No. 6 "Aplicación orientada a Servicios"

**Materia:** Aplicaciones Web Progresivas · Unidad I · Actividad Desarrollo
**Alumno:** Jahir Jaziel Serrano Arana · 10° D
**Repositorio:** `JazyelAe/service` → se propone renombrarlo a **`JazyelAe/BiblioServ-Servicios`** (requiere tu confirmación)
**Estado:** borrador para aprobación (Checkpoint A)

## 1. Objetivo
Convertir BiblioServ en una aplicación formada por **servicios independientes que se comunican por HTTP/JSON**:
- un **servicio de autenticación** (entrega tokens);
- un **servicio de catálogo** (API REST de libros con SQLite);
- un **servicio externo** (API pública de **Open Library**);
- un **cliente web** separado (GitHub Pages) que consume todo lo anterior.

## 2. Auditoría del repo actual
Hoy el repo tiene solo `app.py` (93 líneas), `index.html` y `requirements.txt` (solo Flask). Problemas:

| # | Hallazgo | Consecuencia |
|---|---|---|
| A-1 | `GET /api/libros/` exige token. | La lista no es pública, como pide la spec. |
| A-2 | `init_db()` solo corre en `if __name__ == "__main__"`. | Con gunicorn o en pruebas no existe la tabla y las peticiones dan error 500. |
| A-3 | `send_from_directory("static", …)`, pero la carpeta `static/` no existe. | `GET /` da 404. |
| A-4 | Los tokens se guardan en un diccionario en memoria. | Con varios procesos de gunicorn o tras un reinicio, el token deja de valer. |
| A-5 | `PUT` solo cambia `disponible`; no hay edición de título o autor. | El CRUD está incompleto. |
| A-6 | No valida datos (un `POST` sin título falla con 500), no tiene CORS, pruebas, README, Open Library ni documentación de la API. | — |
| A-7 | Pages publica `index.html` desde la raíz, que llama a `/api/...` en el mismo dominio. | En https://jazyelae.github.io/service/ el login **no funciona**, porque ahí no hay API. |
| A-8 | El usuario `bibliotecario`/`demo1234` está escrito en el código. | Se conserva como **usuario de demostración** (documentado), pero la contraseña se podrá cambiar con una variable de entorno. |

## 3. Requisitos funcionales
- **RF-1 Servicio de catálogo** (`catalogo.py`, blueprint Flask + SQLite).
  - `GET /api/libros` es pública y acepta búsqueda `?q=`.
  - `GET /api/libros/<id>`.
  - `POST`, `PUT` y `DELETE` requieren token.
  - Campos: título, autor, año, ISBN, portada y disponible.
  - Valida los datos: un campo faltante devuelve 400 con un mensaje en español; un id inexistente devuelve 404.
- **RF-2 Servicio de autenticación** (`autenticacion.py`, blueprint separado).
  - `POST /api/login` devuelve un **token firmado** (itsdangerous, incluido en Flask) que caduca en 8 horas.
  - `GET /api/perfil`.
  - Las escrituras sin token o con un token inválido devuelven **401**.
  - Al estar firmado, el token no depende de la memoria del proceso (corrige A-4).
- **RF-3 Servicio externo: Open Library.**
  - `GET /api/externo/buscar?q=` busca por título o ISBN en Open Library y responde con los datos ya simplificados.
  - El cliente los usa para **precargar** el formulario de alta (incluida la portada).
  - Si Open Library falla, responde 502 con un mensaje.
- **RF-4 Cliente web** (`cliente/`, HTML + JS, publicado en **GitHub Pages**).
  - Inicio de sesión y lista con búsqueda.
  - Alta, edición, préstamo y devolución, y borrado.
  - Búsqueda en Open Library con el botón «Usar estos datos».
  - La URL de la API se configura en un solo lugar (`cliente/config.js`).
- **RF-5 Documentación de la API.**
  - Tabla de endpoints en el README.
  - **Swagger UI** en `/docs`, a partir de un `openapi.yaml` escrito a mano. Se descarta `flasgger` porque tiene problemas con Flask 3.
- **RF-6 CORS** (`flask-cors`) solo para `https://jazyelae.github.io` y `localhost`.

## 4. Requisitos no funcionales
- **RNF-1** Código en español, comentado y en pocos archivos: `app.py`, `autenticacion.py`, `catalogo.py`, `externo.py`, `basedatos.py`.
- **RNF-2** La base se crea y se llena con 5 libros de ejemplo al arrancar (corrige A-2).
- **RNF-3** La configuración va en variables de entorno (`SECRET_KEY`, `DEMO_PASSWORD`, `ORIGENES_CORS`), sin secretos en el repo.
- **RNF-4** Pruebas `pytest` (mínimo 5; plan de ~12).

## 5. Tecnologías
| Capa | Tecnología |
|---|---|
| Servicios | Python 3.12 · Flask 3.1 (blueprints) · SQLite · itsdangerous (tokens firmados) · flask-cors |
| Servicio externo | API REST de Open Library (`openlibrary.org/search.json`), consultada desde el servidor con `requests` |
| Cliente | HTML + CSS + JavaScript (`fetch`) en GitHub Pages |
| Documentación | OpenAPI 3 + Swagger UI (CDN) en `/docs` |
| Pruebas | pytest (cliente de pruebas de Flask) + Playwright (cliente web) |
| Despliegue | **Render** (plan gratuito, `render.yaml` + gunicorn) para la API; **GitHub Pages** (Actions) para el cliente |

## 6. Criterios de aceptación
| # | Criterio | Cómo se verifica |
|---|---|---|
| CA-1 | La API pública responde `GET /api/libros` con JSON. | curl + captura |
| CA-2 | Las escrituras sin token devuelven 401. | pytest + curl |
| CA-3 | El cliente en Pages hace el CRUD completo contra la API pública. | Playwright + capturas |
| CA-4 | La búsqueda en Open Library funciona y precarga el formulario. | Playwright + captura |
| CA-5 | `pytest` pasa (en la PC y en GitHub Actions). | Actions |
| CA-6 | Swagger UI muestra todos los endpoints. | Captura de `/docs` |
| CA-7 | README con diagrama, tabla de endpoints y enlaces. | Revisar el repo |

## 7. Plan de despliegue
- **API en Render**, con `render.yaml` (Blueprint): runtime python, plan free, `pip install -r requirements.txt`, `gunicorn app:app` y `SECRET_KEY` generada por Render.
  - **🔐 Requiere tu cuenta:** creas la cuenta en Render, inicias sesión con GitHub y haces *New → Blueprint* con el repo. Yo dejo todo listo y te digo los clics exactos.
  - **Limitaciones del plan gratuito** (según la documentación de Render):
    - El servicio **se duerme tras 15 minutos** sin uso y tarda cerca de 1 minuto en despertar.
    - El disco es temporal: la base SQLite **vuelve a los 5 libros de ejemplo** cada vez que el servicio reinicia o se duerme.
    - Para una demostración escolar es aceptable, y se explica en el README y en el reporte.
- **Cliente en GitHub Pages** con un workflow que publica solo la carpeta `cliente/` (se reemplaza el Pages actual, que está roto).
- **Si no se puede usar Render:**
  - Pruebo todo en local y con la API corriendo dentro de GitHub Actions.
  - Las capturas siguen siendo reales.
  - El enlace público de la API quedaría pendiente, y te lo diría así.
- **Workflow `pruebas.yml`:** corre pytest en cada push.

## 8. Capturas (automáticas)
- **Cliente** (Playwright): `01_login.png`, `02_lista.png`, `03_alta.png`, `04_busqueda_openlibrary.png`, `05_editar.png`, `06_sin_token_401.png` (aviso en el cliente).
- **API:** `07_json_libros.png` (respuesta JSON de `GET /api/libros` en el navegador) y `08_swagger.png`.
- **Despliegue:** `09_render.png`.
  - **Esta te la pediría a ti,** porque el panel de Render requiere tu sesión: archivo `evidencias/SP6/09_render.png`, con el servicio en estado *Live*.
  - Si prefieres no hacerla, se omite.

## 9. Ejemplos reales propuestos (a verificar con fuente oficial antes del reporte)
| Ejemplo | Por qué es orientado a servicios | Fuente oficial a comprobar |
|---|---|---|
| Netflix | Arquitectura de microservicios en AWS | Caso de AWS o Netflix Tech Blog |
| Mercado Pago (API de pagos) | Servicio externo que otras apps consumen por HTTP/JSON | Documentación para desarrolladores de Mercado Pago |
| Google Maps Platform | Servicios de mapas, rutas y lugares consumidos mediante API | developers.google.com/maps |

## 10. Pruebas
_(Se llena después de implementar.)_
