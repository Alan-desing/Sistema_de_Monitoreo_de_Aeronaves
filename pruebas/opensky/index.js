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

// Obtiene un token de acceso usando las credenciales
async function obtenerToken() {
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
    throw new Error(`Error al autenticar con OpenSky: HTTP ${respuesta.status}`);
  }

  const datos = await respuesta.json();

  return datos.access_token;
}

// Consulta las aeronaves utilizando el token
async function obtenerAeronaves() {
  try {
    console.log("Autenticando con OpenSky...\n");

    const token = await obtenerToken();

    console.log("Autenticación correcta.");
    console.log("Consultando aeronaves...\n");

    const respuesta = await fetch(API_URL, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    if (!respuesta.ok) {
      throw new Error(`Error HTTP: ${respuesta.status}`);
    }

    const datos = await respuesta.json();

    console.log(
      "Hora de los datos:",
      new Date(datos.time * 1000).toLocaleString()
    );

    console.log("Aeronaves detectadas:", datos.states?.length ?? 0);
    console.log("----------------------------------------");

    for (const aeronave of datos.states ?? []) {
      console.log({
        icao24: aeronave[0],
        callsign: aeronave[1]?.trim() || "Sin callsign",
        pais: aeronave[2],
        longitud: aeronave[5],
        latitud: aeronave[6],
        altitud: aeronave[7],
        velocidad: aeronave[9],
        rumbo: aeronave[10],
        enTierra: aeronave[8]
      });
    }
  } catch (error) {
    console.error("No se pudieron obtener los datos:");
    console.error(error.message);
  }
}

obtenerAeronaves();