"""Prueba y captura BiblioServ: el cliente web contra la API (local o pública en Render).
Comprueba CA-1 (GET público), CA-2 (401 sin token), CA-3 (CRUD desde el cliente), CA-4 (Open Library) y CA-6 (Swagger).
Uso: python scripts/prueba_cliente.py <url_cliente> <url_api> [carpeta_capturas]"""
import json
import os
import sys
import urllib.error
import urllib.request
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
CLIENTE, API = sys.argv[1], sys.argv[2].rstrip("/")
SALIDA = sys.argv[3] if len(sys.argv) > 3 else "."
os.makedirs(SALIDA, exist_ok=True)
resultados = []


def ok(cond, texto, extra=""):
    resultados.append(bool(cond))
    print("✅" if cond else "❌", texto, extra)


def http(metodo, ruta, cuerpo=None, token=None):
    """Petición directa a la API (sin navegador), para comprobar códigos de estado."""
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(API + ruta, data=datos, method=metodo, headers={"Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


# ---------- La API sola (curl equivalente) ----------
estado, cuerpo = http("GET", "/api/libros")
ok(estado == 200 and isinstance(json.loads(cuerpo), list), "CA-1 GET /api/libros es público", f"({estado}, {len(json.loads(cuerpo))} libros)")
estado, _ = http("POST", "/api/libros", {"titulo": "X", "autor": "Y"})
ok(estado == 401, "CA-2 POST sin token → 401", f"({estado})")
estado, _ = http("DELETE", "/api/libros/1", token="token-falso")
ok(estado == 401, "CA-2 DELETE con token falso → 401", f"({estado})")

with sync_playwright() as p:
    nav = p.chromium.launch(channel="chrome")
    ctx = nav.new_context(viewport={"width": 1180, "height": 900}, locale="es-MX")
    # Un sitio público (GitHub Pages) que llama a la API en 127.0.0.1 necesita el permiso de «red local»
    # de Chrome; una persona lo concede en el aviso que muestra el navegador. Aquí se concede igual.
    origen = "/".join(CLIENTE.split("/")[:3])
    ctx.grant_permissions(["local-network-access"], origin=origen)
    pg = ctx.new_page()
    errores = []
    pg.on("pageerror", lambda e: errores.append(str(e)))
    pg.on("console", lambda m: errores.append(m.text) if m.type == "error" and "401" not in m.text else None)
    pg.on("dialog", lambda d: d.accept())
    cap = lambda n, **k: pg.screenshot(path=os.path.join(SALIDA, n), **k)

    pg.goto(CLIENTE, wait_until="load")
    pg.get_by_text("API en línea").wait_for(timeout=120000)  # Render puede tardar en despertar
    pg.locator("#tabla tr").first.wait_for()
    ok(pg.locator("#tabla tr").count() >= 5, "La lista se ve sin iniciar sesión")
    cap("01_login.png")

    # --- Autenticación ---
    pg.get_by_role("button", name="Iniciar sesión").click()
    pg.get_by_text("Sesión iniciada como").wait_for()
    ok(pg.locator("#quien").inner_text() == "bibliotecario", "Login con el servicio de autenticación")
    pg.wait_for_timeout(3200)
    cap("02_lista.png")

    # --- Servicio externo: Open Library ---
    pg.get_by_label("Buscar en Open Library").fill("aura carlos fuentes")
    pg.get_by_role("button", name="Buscar", exact=True).click()
    pg.locator(".resultado").first.wait_for(timeout=30000)
    n = pg.locator(".resultado").count()
    ok(n >= 1, "CA-4 Open Library devuelve resultados", f"({n})")
    pg.locator("#panel-form").scroll_into_view_if_needed()
    pg.wait_for_timeout(1500)  # portadas
    cap("04_busqueda_openlibrary.png", full_page=True)
    pg.get_by_role("button", name="Usar estos datos").first.click()
    titulo = pg.locator("#f-titulo").input_value()
    ok(titulo != "" and pg.locator("#f-autor").input_value() != "", "CA-4 «Usar estos datos» precarga el formulario", f"({titulo})")

    # --- CRUD desde el cliente ---
    pg.get_by_role("button", name="Agregar libro").click()
    pg.get_by_text("Libro agregado").wait_for()
    fila = pg.locator("#tabla tr", has_text=titulo).last
    ok(fila.count() == 1, "CA-3 Alta: el libro aparece en la lista")
    pg.wait_for_timeout(800)
    cap("03_alta.png", full_page=True)

    fila.get_by_role("button", name="Editar").click()
    pg.get_by_text("Editar libro #").wait_for()
    pg.locator("#f-titulo").fill(titulo + " (edición escolar)")
    cap("05_editar.png", full_page=True)
    pg.get_by_role("button", name="Guardar cambios").click()
    pg.get_by_text("Cambios guardados").wait_for()
    fila = pg.locator("#tabla tr", has_text="(edición escolar)")
    ok(fila.count() == 1, "CA-3 Edición guardada")

    fila.get_by_role("button", name="Prestar").click()
    pg.get_by_text("Libro prestado").wait_for()
    ok("Prestado" in pg.locator("#tabla tr", has_text="(edición escolar)").inner_text(), "CA-3 Préstamo (PUT disponible)")

    pg.locator("#tabla tr", has_text="(edición escolar)").get_by_role("button", name="Borrar").click()
    pg.get_by_text("Libro borrado").wait_for()
    pg.wait_for_timeout(500)
    ok(pg.locator("#tabla tr", has_text="(edición escolar)").count() == 0, "CA-3 Borrado")

    # --- Token inválido en el cliente: el servicio responde 401 ---
    pg.evaluate("sessionStorage.setItem('token', 'token-falsificado')")
    pg.reload(wait_until="load")
    pg.locator("#aviso.mal").wait_for(timeout=30000)
    aviso = pg.locator("#aviso").inner_text()
    ok(aviso.startswith("401"), "CA-2 El cliente con token falso recibe 401 y pide iniciar sesión", f"({aviso})")
    cap("06_sin_token_401.png")
    ok(not errores, "Consola sin errores (aparte de los 401 esperados)", errores[:3])

    # --- Vista de teléfono ---
    movil = nav.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, locale="es-MX")
    movil.grant_permissions(["local-network-access"], origin=origen)
    pm = movil.new_page()
    pm.goto(CLIENTE, wait_until="load")
    pm.get_by_text("API en línea").wait_for(timeout=60000)
    pm.locator("#tabla tr").first.wait_for()
    pm.wait_for_timeout(800)
    pm.screenshot(path=os.path.join(SALIDA, "10_movil.png"))
    ok(not pm.evaluate("document.documentElement.scrollWidth > window.innerWidth"), "Sin desbordamiento horizontal en 390 px")

    # --- La API vista directamente: JSON y Swagger ---
    pj = ctx.new_page()
    pj.goto(API + "/api/libros", wait_until="load")
    pj.wait_for_timeout(500)
    pj.screenshot(path=os.path.join(SALIDA, "07_json_libros.png"))
    pj.goto(API + "/docs", wait_until="networkidle")
    pj.locator(".opblock").first.wait_for(timeout=30000)
    n = pj.locator(".opblock").count()
    ok(n == 8, "CA-6 Swagger UI muestra los 8 endpoints", f"({n})")
    pj.wait_for_timeout(500)
    pj.screenshot(path=os.path.join(SALIDA, "08_swagger.png"), full_page=True)
    nav.close()

print(f"\n{sum(resultados)}/{len(resultados)} comprobaciones correctas")
sys.exit(0 if all(resultados) else 1)
