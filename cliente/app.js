// Cliente web de BiblioServ: solo habla con los servicios por HTTP/JSON usando fetch.
const API = window.API_URL;
const $ = (selector) => document.querySelector(selector);
let token = sessionStorage.getItem("token");  // se borra al cerrar la pestaña
let editando = null;                            // id del libro que se edita (null = alta)
let resultadosExternos = [];
let titulos = {};                               // id → título, para confirmar el borrado

// Escapa el texto antes de ponerlo en HTML (los datos vienen de una API pública).
const seguro = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function avisar(texto, error = false) {
  const aviso = $("#aviso");
  aviso.textContent = texto;
  aviso.className = error ? "mal" : "";
  aviso.style.display = "block";
  clearTimeout(avisar.t);
  avisar.t = setTimeout(() => (aviso.style.display = "none"), 3000);
}

// Llamada genérica a la API. Agrega el token y convierte los errores en mensajes.
async function api(ruta, opciones = {}) {
  const encabezados = { "Content-Type": "application/json" };
  if (token) encabezados.Authorization = "Bearer " + token;
  const respuesta = await fetch(API + ruta, { ...opciones, headers: encabezados });
  const datos = respuesta.status === 204 ? null : await respuesta.json();
  if (respuesta.status === 401 && ruta !== "/api/login") {
    cerrarSesion();
    throw new Error("401 · " + datos.error + ". Inicia sesión otra vez.");
  }
  if (!respuesta.ok) throw new Error(datos.error || "Error " + respuesta.status);
  return datos;
}

// ---------- Servicio de autenticación ----------
function mostrarSesion(usuario) {
  document.body.classList.toggle("con-sesion", !!token);
  $("#panel-login").classList.toggle("oculto", !!token);
  $("#panel-sesion").classList.toggle("oculto", !token);
  $("#quien").textContent = usuario || "";
}

function cerrarSesion() {
  token = null;
  sessionStorage.removeItem("token");
  mostrarSesion();
  cargarLibros();
}

$("#form-login").onsubmit = async (e) => {
  e.preventDefault();
  $("#error-login").textContent = "";
  try {
    const datos = await api("/api/login", {
      method: "POST",
      body: JSON.stringify({ usuario: $("#usuario").value, password: $("#password").value }),
    });
    token = datos.token;
    sessionStorage.setItem("token", token);
    mostrarSesion(datos.usuario);
    avisar("Sesión iniciada");
    cargarLibros();
  } catch (err) {
    $("#error-login").textContent = err.message;
  }
};
$("#salir").onclick = cerrarSesion;

// ---------- Servicio de catálogo ----------
function portada(url) {
  return url ? `<img src="${seguro(url)}" alt="" loading="lazy">` : `<span class="sin-portada">📕</span>`;
}

async function cargarLibros() {
  const q = encodeURIComponent($("#buscar").value.trim());
  try {
    const libros = await api("/api/libros?q=" + q);
    titulos = Object.fromEntries(libros.map((l) => [l.id, l.titulo]));
    $("#total").textContent = `(${libros.length})`;
    $("#tabla").innerHTML = libros.map((l) => `
      <tr>
        <td>${portada(l.portada)}</td>
        <td>${seguro(l.titulo)}<br><small>${seguro(l.isbn)}</small></td>
        <td>${seguro(l.autor)}</td>
        <td>${seguro(l.anio)}</td>
        <td class="${l.disponible ? "disp" : "prest"}">${l.disponible ? "Disponible" : "Prestado"}</td>
        <td class="solo-sesion"><div class="acciones">
          <button class="chico secundario" onclick="alternar(${l.id}, ${l.disponible})">${l.disponible ? "Prestar" : "Devolver"}</button>
          <button class="chico secundario" onclick="editar(${l.id})">Editar</button>
          <button class="chico peligro" onclick="borrar(${l.id})">Borrar</button>
        </div></td>
      </tr>`).join("") || `<tr><td colspan="6">No hay libros que coincidan.</td></tr>`;
  } catch (err) {
    avisar(err.message, true);
  }
}

let espera;
$("#buscar").oninput = () => { clearTimeout(espera); espera = setTimeout(cargarLibros, 300); };

async function alternar(id, disponible) {
  try {
    await api(`/api/libros/${id}`, { method: "PUT", body: JSON.stringify({ disponible: !disponible }) });
    avisar(disponible ? "Libro prestado" : "Libro devuelto");
    cargarLibros();
  } catch (err) { avisar(err.message, true); }
}

async function borrar(id) {
  if (!confirm(`¿Borrar «${titulos[id]}»?`)) return;
  try {
    await api(`/api/libros/${id}`, { method: "DELETE" });
    avisar("Libro borrado");
    cargarLibros();
  } catch (err) { avisar(err.message, true); }
}

// ---------- Formulario de alta y edición ----------
const campos = ["titulo", "autor", "anio", "isbn", "portada"];

function llenarFormulario(libro) {
  campos.forEach((c) => ($("#f-" + c).value = libro[c] ?? ""));
}

async function editar(id) {
  const libro = await api(`/api/libros/${id}`);
  editando = id;
  llenarFormulario(libro);
  $("#titulo-form").textContent = "Editar libro #" + id;
  $("#guardar").textContent = "Guardar cambios";
  $("#cancelar").classList.remove("oculto");
  $("#panel-form").scrollIntoView({ behavior: "smooth" });
}

function limpiarFormulario() {
  editando = null;
  $("#form-libro").reset();
  $("#titulo-form").textContent = "Agregar libro";
  $("#guardar").textContent = "Agregar libro";
  $("#cancelar").classList.add("oculto");
}
$("#cancelar").onclick = limpiarFormulario;

$("#form-libro").onsubmit = async (e) => {
  e.preventDefault();
  const libro = Object.fromEntries(campos.map((c) => [c, $("#f-" + c).value.trim()]));
  try {
    if (editando) {
      await api(`/api/libros/${editando}`, { method: "PUT", body: JSON.stringify(libro) });
      avisar("Cambios guardados");
    } else {
      await api("/api/libros", { method: "POST", body: JSON.stringify(libro) });
      avisar("Libro agregado");
    }
    limpiarFormulario();
    $("#resultados-externo").innerHTML = "";
    cargarLibros();
  } catch (err) { avisar(err.message, true); }
};

// ---------- Servicio externo: Open Library (a través de nuestra API) ----------
$("#form-externo").onsubmit = async (e) => {
  e.preventDefault();
  const q = $("#q-externo").value.trim();
  if (!q) return;
  $("#resultados-externo").innerHTML = "<p class='nota'>Consultando Open Library…</p>";
  try {
    const datos = await api("/api/externo/buscar?q=" + encodeURIComponent(q));
    resultadosExternos = datos.resultados;
    $("#resultados-externo").innerHTML = resultadosExternos.map((r, i) => `
      <div class="resultado">
        ${portada(r.portada)}
        <div><b>${seguro(r.titulo)}</b><br>${seguro(r.autor)} · ${seguro(r.anio)} · ISBN ${seguro(r.isbn) || "—"}</div>
        <button class="chico" onclick="usarExterno(${i})">Usar estos datos</button>
      </div>`).join("") || "<p class='nota'>Sin resultados.</p>";
  } catch (err) {
    $("#resultados-externo").innerHTML = "";
    avisar(err.message, true);
  }
};

function usarExterno(i) {
  llenarFormulario(resultadosExternos[i]);
  avisar("Datos de Open Library copiados al formulario");
}

// ---------- Inicio ----------
async function comprobarApi() {
  const estado = $("#estado-api");
  // Render duerme el servicio gratuito tras 15 min sin uso: la primera respuesta puede tardar ~1 minuto.
  const lento = setTimeout(() => (estado.textContent = "Despertando el servicio (puede tardar un minuto)…"), 3000);
  try {
    const r = await fetch(API + "/");
    estado.textContent = r.ok ? "API en línea" : "La API respondió " + r.status;
    estado.className = "estado " + (r.ok ? "ok" : "mal");
  } catch {
    estado.textContent = "Sin conexión con la API";
    estado.className = "estado mal";
  } finally {
    clearTimeout(lento);
  }
}

$("#enlace-docs").href = API + "/docs";
mostrarSesion();
if (token) api("/api/perfil").then((p) => mostrarSesion(p.usuario)).catch((err) => avisar(err.message, true));
comprobarApi().then(cargarLibros);
