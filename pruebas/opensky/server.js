import http from "http";
import fs from "fs";

// URL para obtener el token de autenticación de OpenSky
const TOKEN_URL =
  "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token";

// Zona geográfica que estamos consultando
const API_URL =
  "https://opensky-network.org/api/states/all?lamin=-35.5&lomin=-59.5&lamax=-34.0&lomax=-57.5";

// Lee las credenciales del archivo credentials.json
const credentials = JSON.parse(
  fs.readFileSync("./credentials.json", "utf8")
);

let accessToken = null;
let tokenExpiration = 0;

// Obtiene un token de acceso usando las credenciales
async function obtenerToken() {
  if (accessToken && Date.now() < tokenExpiration) {
    return accessToken;
  }

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

  // Dejamos un minuto de margen antes de que expire
  const duracion = (datos.expires_in ?? 1800) - 60;
  tokenExpiration = Date.now() + duracion * 1000;

  return accessToken;
}

// Obtiene las aeronaves desde OpenSky
async function obtenerAeronaves() {
  let token = await obtenerToken();

  let respuesta = await fetch(API_URL, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });

  // Si el token expiró, lo renovamos y hacemos otro intento
  if (respuesta.status === 401) {
    accessToken = null;
    tokenExpiration = 0;

    token = await obtenerToken();

    respuesta = await fetch(API_URL, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
  }

  if (!respuesta.ok) {
    throw new Error(`Error HTTP: ${respuesta.status}`);
  }

  const datos = await respuesta.json();

  const aeronaves = (datos.states ?? [])
    .map((aeronave) => ({
      icao24: aeronave[0],
      callsign: aeronave[1]?.trim() || "Sin callsign",
      pais: aeronave[2],
      longitud: aeronave[5],
      latitud: aeronave[6],
      altitud: aeronave[7],
      velocidad: aeronave[9],
      rumbo: aeronave[10],
      enTierra: aeronave[8]
    }))
    .filter(
      (aeronave) =>
        aeronave.latitud !== null &&
        aeronave.longitud !== null
    );

  return {
    time: datos.time,
    aeronaves
  };
}

// HTML principal
function generarHTML() {
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
      background: #101418;
      color: #e8edf2;
    }

    header {
      background: #171c21;
      border-bottom: 1px solid #2c333a;
      padding: 18px 24px;
    }

    header h1 {
      margin: 0 0 5px;
      font-size: 24px;
      font-weight: 600;
    }

    header p {
      margin: 0;
      color: #929ba5;
      font-size: 14px;
    }

    .panel {
      padding: 14px 20px;
      background: #14191e;
      border-bottom: 1px solid #2c333a;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 20px;
      flex-wrap: wrap;
    }

    .estado {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 14px;
    }

    .estado-indicador {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: #43d17a;
      box-shadow: 0 0 8px rgba(67, 209, 122, 0.6);
    }

    .estado-indicador.error {
      background: #e65b5b;
      box-shadow: 0 0 8px rgba(230, 91, 91, 0.5);
    }

    .datos {
      display: flex;
      gap: 25px;
      color: #aab3bc;
      font-size: 14px;
    }

    .datos strong {
      color: #ffffff;
    }

    #map {
      width: 100%;
      height: 620px;
      background: #20262b;
    }

    .contenedor-tabla {
      padding: 20px;
      background: #101418;
    }

    .contenedor-tabla h2 {
      margin: 0 0 14px;
      font-size: 18px;
      font-weight: 500;
    }

    .tabla-wrapper {
      overflow-x: auto;
      border: 1px solid #2c333a;
      border-radius: 6px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 900px;
      background: #151a1f;
    }

    th,
    td {
      padding: 11px 13px;
      text-align: left;
      border-bottom: 1px solid #292f35;
      font-size: 13px;
    }

    th {
      background: #1b2127;
      color: #aeb7c0;
      font-weight: 500;
    }

    td {
      color: #dce2e7;
    }

    tr:last-child td {
      border-bottom: none;
    }

    .sin-datos {
      padding: 30px;
      text-align: center;
      color: #858e97;
    }

    /* Icono de aeronave */
    .aircraft-marker {
      width: 28px;
      height: 28px;
      display: flex;
      align-items: center;
      justify-content: center;
      transform-origin: center center;
      filter: drop-shadow(0 1px 3px rgba(0, 0, 0, 0.8));
    }

    .aircraft-marker svg {
      width: 25px;
      height: 25px;
      fill: #f1f5f8;
      stroke: #11161a;
      stroke-width: 1.5;
    }

    /* Nombre/callsign junto al avión */
    .callsign-label {
      background: rgba(17, 22, 26, 0.88);
      border: 1px solid rgba(100, 110, 120, 0.5);
      color: #e9eef2;
      border-radius: 3px;
      padding: 2px 5px;
      font-size: 11px;
      font-weight: 500;
      box-shadow: none;
    }

    .callsign-label::before {
      display: none;
    }

    .leaflet-popup-content-wrapper,
    .leaflet-popup-tip {
      background: #171c21;
      color: #e8edf2;
    }

    .leaflet-popup-content {
      margin: 13px;
    }

    .popup-titulo {
      font-size: 15px;
      font-weight: 600;
      margin-bottom: 9px;
    }

    .popup-dato {
      margin: 4px 0;
      font-size: 13px;
      color: #b7c0c8;
    }

    .popup-dato strong {
      color: #ffffff;
    }

    .leaflet-control-zoom a {
      background: #171c21 !important;
      color: #dce2e7 !important;
      border-color: #30373e !important;
    }

    .leaflet-control-attribution {
      background: rgba(15, 19, 23, 0.8) !important;
      color: #7d8790 !important;
    }

    .leaflet-control-attribution a {
      color: #aeb8c1 !important;
    }

    @media (max-width: 700px) {
      #map {
        height: 500px;
      }

      .panel {
        align-items: flex-start;
        flex-direction: column;
      }

      .datos {
        flex-wrap: wrap;
      }
    }
  </style>
</head>

<body>

  <header>
    <h1>Monitoreo de Aeronaves</h1>
    <p>Datos obtenidos mediante OpenSky Network</p>
  </header>

  <div class="panel">
    <div class="estado">
      <span id="estadoIndicador" class="estado-indicador"></span>
      <span id="estadoTexto">Conectado con OpenSky</span>
    </div>

    <div class="datos">
      <span>
        Aeronaves:
        <strong id="cantidadAeronaves">0</strong>
      </span>

      <span>
        Última actualización:
        <strong id="ultimaActualizacion">--</strong>
      </span>
    </div>
  </div>

  <div id="map"></div>

  <div class="contenedor-tabla">
    <h2>Aeronaves detectadas</h2>

    <div class="tabla-wrapper">
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
            <th>Estado</th>
          </tr>
        </thead>

        <tbody id="tablaAeronaves">
          <tr>
            <td colspan="9" class="sin-datos">
              Cargando aeronaves...
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

  <script>
    // Crear el mapa
    const mapa = L.map("map", {
      zoomControl: true
    }).setView([-34.6, -58.45], 9);

    // Mapa 
    L.tileLayer(
      "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        attribution: "&copy; OpenStreetMap contributors",
        maxZoom: 19
      }
    ).addTo(mapa);

    // Guardamos los marcadores por ICAO24
    const marcadores = new Map();

    // SVG de avión apuntando hacia arriba
    function crearIconoAeronave(rumbo) {
      const direccion =
        typeof rumbo === "number" ? rumbo : 0;

      return L.divIcon({
        className: "",
        html: \`
          <div
            class="aircraft-marker"
            style="transform: rotate(\${direccion}deg);"
          >
            <svg viewBox="0 0 24 24">
              <path d="
                M12 2
                L14.5 9
                L21 12
                L21 14
                L14.5 13
                L13.5 21
                L10.5 21
                L9.5 13
                L3 14
                L3 12
                L9.5 9
                Z
              "/>
            </svg>
          </div>
        \`,
        iconSize: [28, 28],
        iconAnchor: [14, 14]
      });
    }

    // Formatea valores numéricos
    function formatearNumero(valor, decimales = 1) {
      if (valor === null || valor === undefined) {
        return "Sin datos";
      }

      return Number(valor).toFixed(decimales);
    }

    // Convierte metros por segundo a kilómetros por hora
    function convertirVelocidad(velocidad) {
      if (velocidad === null || velocidad === undefined) {
        return "Sin datos";
      }

      return (velocidad * 3.6).toFixed(1) + " km/h";
    }

    // Convierte metros a pies
    function convertirAltitud(altitud) {
      if (altitud === null || altitud === undefined) {
        return "Sin datos";
      }

      return Math.round(altitud * 3.28084) + " ft";
    }

    // Actualiza los aviones del mapa
    function actualizarMapa(aeronaves) {
      const aeronavesActuales = new Set();

      for (const aeronave of aeronaves) {
        aeronavesActuales.add(aeronave.icao24);

        const posicion = [
          aeronave.latitud,
          aeronave.longitud
        ];

        const popup = \`
          <div class="popup-titulo">
            \${aeronave.callsign}
          </div>

          <div class="popup-dato">
            <strong>ICAO24:</strong>
            \${aeronave.icao24}
          </div>

          <div class="popup-dato">
            <strong>País:</strong>
            \${aeronave.pais}
          </div>

          <div class="popup-dato">
            <strong>Altitud:</strong>
            \${convertirAltitud(aeronave.altitud)}
          </div>

          <div class="popup-dato">
            <strong>Velocidad:</strong>
            \${convertirVelocidad(aeronave.velocidad)}
          </div>

          <div class="popup-dato">
            <strong>Rumbo:</strong>
            \${formatearNumero(aeronave.rumbo, 0)}°
          </div>

          <div class="popup-dato">
            <strong>Estado:</strong>
            \${aeronave.enTierra ? "En tierra" : "En vuelo"}
          </div>
        \`;

        if (marcadores.has(aeronave.icao24)) {
          const marcador = marcadores.get(aeronave.icao24);

          marcador.setLatLng(posicion);
          marcador.setIcon(
            crearIconoAeronave(aeronave.rumbo)
          );

          marcador.setTooltipContent(
            aeronave.callsign
          );

          marcador.setPopupContent(popup);
        } else {
          const marcador = L.marker(
            posicion,
            {
              icon: crearIconoAeronave(aeronave.rumbo)
            }
          ).addTo(mapa);

          marcador.bindPopup(popup);

          marcador.bindTooltip(
            aeronave.callsign,
            {
              permanent: true,
              direction: "right",
              offset: [13, 0],
              className: "callsign-label"
            }
          );

          marcadores.set(
            aeronave.icao24,
            marcador
          );
        }
      }

      // Eliminar del mapa aeronaves que ya no aparecen en OpenSky
      for (const [icao24, marcador] of marcadores) {
        if (!aeronavesActuales.has(icao24)) {
          mapa.removeLayer(marcador);
          marcadores.delete(icao24);
        }
      }
    }

    // Actualiza la tabla
    function actualizarTabla(aeronaves) {
      const tabla = document.getElementById(
        "tablaAeronaves"
      );

      if (aeronaves.length === 0) {
        tabla.innerHTML = \`
          <tr>
            <td colspan="9" class="sin-datos">
              No se detectaron aeronaves.
            </td>
          </tr>
        \`;

        return;
      }

      tabla.innerHTML = aeronaves
        .map((aeronave) => \`
          <tr>
            <td>\${aeronave.callsign}</td>

            <td>\${aeronave.icao24}</td>

            <td>\${aeronave.pais}</td>

            <td>
              \${formatearNumero(aeronave.latitud, 4)}
            </td>

            <td>
              \${formatearNumero(aeronave.longitud, 4)}
            </td>

            <td>
              \${convertirAltitud(aeronave.altitud)}
            </td>

            <td>
              \${convertirVelocidad(aeronave.velocidad)}
            </td>

            <td>
              \${formatearNumero(aeronave.rumbo, 0)}°
            </td>

            <td>
              \${aeronave.enTierra ? "En tierra" : "En vuelo"}
            </td>
          </tr>
        \`)
        .join("");
    }

    // Consulta los datos del servidor
    async function actualizarDatos() {
      const indicador =
        document.getElementById("estadoIndicador");

      const estadoTexto =
        document.getElementById("estadoTexto");

      try {
        const respuesta = await fetch("/api/aeronaves");

        if (!respuesta.ok) {
          throw new Error(
            "Error HTTP " + respuesta.status
          );
        }

        const datos = await respuesta.json();

        actualizarMapa(datos.aeronaves);
        actualizarTabla(datos.aeronaves);

        document.getElementById(
          "cantidadAeronaves"
        ).textContent = datos.aeronaves.length;

        document.getElementById(
          "ultimaActualizacion"
        ).textContent =
          new Date(
            datos.time * 1000
          ).toLocaleTimeString();

        indicador.classList.remove("error");

        estadoTexto.textContent =
          "Conectado con OpenSky";
      } catch (error) {
        console.error(error);

        indicador.classList.add("error");

        estadoTexto.textContent =
          "Error al obtener datos";
      }
    }

    // Primera consulta
    actualizarDatos();

    // Actualizar automáticamente cada 15 segundos
    setInterval(actualizarDatos, 15000);
  </script>

</body>
</html>
`;
}

// Crear servidor
const servidor = http.createServer(
  async (solicitud, respuesta) => {
    try {
      // API para obtener aeronaves
      if (
        solicitud.url === "/api/aeronaves" &&
        solicitud.method === "GET"
      ) {
        const datos = await obtenerAeronaves();

        respuesta.writeHead(200, {
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "no-store"
        });

        respuesta.end(
          JSON.stringify(datos)
        );

        return;
      }

      // Página principal
      if (
        solicitud.url === "/" &&
        solicitud.method === "GET"
      ) {
        respuesta.writeHead(200, {
          "Content-Type": "text/html; charset=utf-8"
        });

        respuesta.end(generarHTML());

        return;
      }

      // Ruta inexistente
      respuesta.writeHead(404, {
        "Content-Type": "text/plain; charset=utf-8"
      });

      respuesta.end("Página no encontrada.");
    } catch (error) {
      console.error("Error del servidor:");
      console.error(error.message);

      respuesta.writeHead(500, {
        "Content-Type": "application/json; charset=utf-8"
      });

      respuesta.end(
        JSON.stringify({
          error: "No se pudieron obtener los datos de OpenSky."
        })
      );
    }
  }
);

servidor.listen(3000, () => {
  console.log("Servidor iniciado.");
  console.log("Abrí http://localhost:3000");
});