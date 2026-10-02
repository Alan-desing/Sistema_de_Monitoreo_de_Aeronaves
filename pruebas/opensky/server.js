import http from "http";
import fs from "fs";

// Puerto donde funcionará la página web
const PORT = 3000;

// URL para obtener el token de OpenSky
const TOKEN_URL =
  "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token";

// API de OpenSky con la zona geográfica que estamos utilizando
const API_URL =
  "https://opensky-network.org/api/states/all?lamin=-35.5&lomin=-59.5&lamax=-34.0&lomax=-57.5";

// Leer las credenciales desde credentials.json
const credentials = JSON.parse(
  fs.readFileSync("./credentials.json", "utf8")
);

// Token actual y momento de vencimiento
let accessToken = null;
let tokenExpiration = 0;

// Obtiene un token nuevo cuando no tenemos uno o cuando está por vencer
async function obtenerToken() {
  const ahora = Date.now();

  // Si ya tenemos un token válido, lo reutilizamos
  if (accessToken && ahora < tokenExpiration) {
    return accessToken;
  }

  console.log("Obteniendo nuevo token de OpenSky...");

  const parametros = new URLSearchParams();

  parametros.append("grant_type", "client_credentials");
  parametros.append("client_id", credentials.clientId);
  parametros.append("client_secret", credentials.clientSecret);

  const respuesta = await fetch(TOKEN_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded"
    },
    body: parametros
  });

  if (!respuesta.ok) {
    throw new Error(
      `Error al autenticar con OpenSky: HTTP ${respuesta.status}`
    );
  }

  const datos = await respuesta.json();

  accessToken = datos.access_token;

  // El token normalmente dura 30 minutos.
  // Dejamos un margen de un minuto para renovarlo antes.
  const segundosValidez = datos.expires_in ?? 1800;

  tokenExpiration =
    Date.now() + (segundosValidez - 60) * 1000;

  console.log("Autenticación correcta.");

  return accessToken;
}

// Obtiene las aeronaves desde OpenSky
async function obtenerAeronaves() {
  const token = await obtenerToken();

  let respuesta = await fetch(API_URL, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });

  // Si el token venció antes de lo esperado, pedimos uno nuevo
  if (respuesta.status === 401) {
    accessToken = null;
    tokenExpiration = 0;

    const nuevoToken = await obtenerToken();

    respuesta = await fetch(API_URL, {
      headers: {
        Authorization: `Bearer ${nuevoToken}`
      }
    });
  }

  if (!respuesta.ok) {
    throw new Error(`Error al consultar OpenSky: HTTP ${respuesta.status}`);
  }

  const datos = await respuesta.json();

  // Convertimos los datos de OpenSky a objetos más fáciles de utilizar
  return {
    hora: datos.time,
    aeronaves: (datos.states ?? [])
      .filter((aeronave) => aeronave[5] !== null && aeronave[6] !== null)
      .map((aeronave) => ({
        icao24: aeronave[0],
        callsign: aeronave[1]?.trim() || "Sin callsign",
        pais: aeronave[2] || "Desconocido",
        longitud: aeronave[5],
        latitud: aeronave[6],
        altitud: aeronave[7],
        velocidad: aeronave[9],
        rumbo: aeronave[10],
        enTierra: aeronave[8]
      }))
  };
}

// Genera la página HTML
function generarHTML(datos) {
  const aeronavesJSON = JSON.stringify(datos.aeronaves);

  const filas = datos.aeronaves
    .map((aeronave) => {
      const altitud =
        aeronave.altitud !== null
          ? `${Math.round(aeronave.altitud)} m`
          : "Sin datos";

      const velocidad =
        aeronave.velocidad !== null
          ? `${Math.round(aeronave.velocidad * 3.6)} km/h`
          : "Sin datos";

      const rumbo =
        aeronave.rumbo !== null
          ? `${Math.round(aeronave.rumbo)}°`
          : "Sin datos";

      return `
        <tr>
          <td>${aeronave.callsign}</td>
          <td>${aeronave.icao24}</td>
          <td>${aeronave.pais}</td>
          <td>${aeronave.latitud.toFixed(4)}</td>
          <td>${aeronave.longitud.toFixed(4)}</td>
          <td>${altitud}</td>
          <td>${velocidad}</td>
          <td>${rumbo}</td>
          <td>${aeronave.enTierra ? "Sí" : "No"}</td>
        </tr>
      `;
    })
    .join("");

  return `
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">

  <title>Monitoreo de Aeronaves</title>

  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
  />

  <style>
    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      font-family: Arial, sans-serif;
      background: #f4f6f8;
      color: #222;
    }

    header {
      padding: 20px 30px;
      background: #1f2937;
      color: white;
    }

    header h1 {
      margin: 0 0 6px;
      font-size: 24px;
    }

    header p {
      margin: 0;
      color: #d1d5db;
    }

    main {
      padding: 25px;
    }

    .info {
      margin-bottom: 15px;
      font-size: 15px;
    }

    #map {
      width: 100%;
      height: 550px;
      border-radius: 10px;
      overflow: hidden;
      margin-bottom: 25px;
      border: 1px solid #d1d5db;
    }

    .tabla-container {
      background: white;
      border-radius: 10px;
      overflow-x: auto;
      border: 1px solid #d1d5db;
    }

    table {
      width: 100%;
      border-collapse: collapse;
    }

    th,
    td {
      padding: 10px 12px;
      text-align: left;
      border-bottom: 1px solid #e5e7eb;
      white-space: nowrap;
    }

    th {
      background: #f3f4f6;
    }

    tr:hover {
      background: #f9fafb;
    }

    .popup-title {
      font-weight: bold;
      margin-bottom: 8px;
    }
  </style>
</head>

<body>

  <header>
    <h1>Monitoreo de Aeronaves</h1>
    <p>Datos obtenidos mediante OpenSky Network</p>
  </header>

  <main>

    <div class="info">
      <strong>Aeronaves detectadas:</strong>
      ${datos.aeronaves.length}
    </div>

    <div class="info">
      <strong>Última actualización:</strong>
      ${new Date(datos.hora * 1000).toLocaleString("es-AR")}
    </div>

    <div id="map"></div>

    <div class="tabla-container">
      <table>
        <thead>
          <tr>
            <th>Callsign</th>
            <th>ICAO24</th>
            <th>País</th>
            <th>Latitud</th>
            <th>Longitud</th>
            <th>Altitud</th>
            <th>Velocidad</th>
            <th>Rumbo</th>
            <th>En tierra</th>
          </tr>
        </thead>

        <tbody>
          ${filas}
        </tbody>
      </table>
    </div>

  </main>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

  <script>
    const aeronaves = ${aeronavesJSON};

    // Crear mapa centrado en Buenos Aires
    const map = L.map("map").setView([-34.6, -58.45], 9);

    // Mapa base de OpenStreetMap
    L.tileLayer(
      "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors"
      }
    ).addTo(map);

    // Agregar una marca por cada aeronave
    for (const aeronave of aeronaves) {

      const popup = [
        "<div class='popup-title'>",
        aeronave.callsign,
        "</div>",
        "<strong>ICAO24:</strong> ",
        aeronave.icao24,
        "<br>",
        "<strong>País:</strong> ",
        aeronave.pais,
        "<br>",
        "<strong>Altitud:</strong> ",
        aeronave.altitud !== null
          ? Math.round(aeronave.altitud) + " m"
          : "Sin datos",
        "<br>",
        "<strong>Velocidad:</strong> ",
        aeronave.velocidad !== null
          ? Math.round(aeronave.velocidad * 3.6) + " km/h"
          : "Sin datos",
        "<br>",
        "<strong>Rumbo:</strong> ",
        aeronave.rumbo !== null
          ? Math.round(aeronave.rumbo) + "°"
          : "Sin datos"
      ].join("");

      L.marker([
        aeronave.latitud,
        aeronave.longitud
      ])
        .addTo(map)
        .bindPopup(popup);
    }
  </script>

</body>
</html>
  `;
}

// Crear servidor web
const server = http.createServer(async (req, res) => {

  if (req.url === "/") {

    try {
      const datos = await obtenerAeronaves();

      res.writeHead(200, {
        "Content-Type": "text/html; charset=utf-8"
      });

      res.end(generarHTML(datos));

    } catch (error) {

      console.error(error);

      res.writeHead(500, {
        "Content-Type": "text/plain; charset=utf-8"
      });

      res.end(
        `No se pudieron obtener los datos de OpenSky.\n\n${error.message}`
      );
    }

    return;
  }

  res.writeHead(404, {
    "Content-Type": "text/plain; charset=utf-8"
  });

  res.end("Página no encontrada.");
});

server.listen(PORT, () => {
  console.log(`Servidor iniciado en http://localhost:${PORT}`);
});