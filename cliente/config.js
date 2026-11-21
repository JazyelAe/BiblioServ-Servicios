// Dirección del servicio (API). Es el ÚNICO lugar que hay que cambiar si la API se mueve.
// En GitHub Pages usa la API publicada en Render; en la computadora, la API local (python app.py).
window.API_URL = location.hostname.endsWith("github.io")
  ? "https://biblioserv.onrender.com"
  : "http://127.0.0.1:5000";
