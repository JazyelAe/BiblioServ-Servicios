// Dirección del servicio (API). Es el ÚNICO lugar que define a qué API se conecta el cliente.
// La API no está publicada en Internet: se ejecuta en la computadora con "python app.py" (puerto 5000).
// Para usar otra API se agrega ?api=URL a la dirección del cliente, por ejemplo:
//   https://jazyelae.github.io/BiblioServ-Servicios/?api=http://127.0.0.1:5000
const parametro = new URLSearchParams(location.search).get("api");
window.API_URL = (parametro || "http://127.0.0.1:5000").replace(/\/$/, "");
