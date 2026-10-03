# Prueba OpenSky - Proyecto Aviones

Esta carpeta contiene las primeras pruebas realizadas con OpenSky Network para el proyecto de monitoreo de aeronaves.

## Objetivo

El objetivo de esta prueba es comprobar que podemos conectarnos a la API de OpenSky, recibir información de aeronaves y utilizar esos datos desde un programa desarrollado con Node.js.

Esta prueba todavía no representa el sistema definitivo. Es una primera etapa para comprobar el acceso a los datos y comenzar a desarrollar la interfaz que se utilizará posteriormente en el proyecto.

## Archivos

### `index.js`

Realiza una consulta a la API de OpenSky y muestra en la terminal las aeronaves recibidas.

Para cada aeronave se muestran algunos de los datos proporcionados por la API:

- ICAO24
- Callsign
- País de origen
- Latitud
- Longitud
- Altitud
- Velocidad
- Rumbo
- Estado en tierra

### `server.js`

Levanta una interfaz web de prueba para visualizar la información obtenida desde OpenSky.

Actualmente la interfaz cuenta con:

- Mapa para visualizar la ubicación de las aeronaves.
- Iconos de aviones en lugar de marcadores de posición comunes.
- Rotación del avión según su rumbo.
- Callsign visible junto a cada aeronave.
- Tabla con los datos de las aeronaves detectadas.
- Actualización automática de los datos cada 15 segundos sin recargar la página.
- Indicador de conexión y hora de la última actualización.

El servidor también administra el token de autenticación de OpenSky. El token es temporal y se renueva automáticamente cuando es necesario.

## API utilizada

Se utiliza el endpoint:

`/api/states/all`

Este endpoint proporciona los estados actuales de las aeronaves disponibles para la zona consultada.

La consulta utilizada en esta prueba está limitada a una zona geográfica mediante:

- Latitud mínima
- Longitud mínima
- Latitud máxima
- Longitud máxima

Esto permite evitar consultar información de todo el mundo y concentrarnos en la zona de interés.

## Autenticación

Para acceder a la API autenticada de OpenSky se utilizan las credenciales almacenadas en `credentials.json`.

Este archivo contiene las credenciales necesarias para obtener un token temporal de acceso y no debe compartirse ni subirse al repositorio.

## Requisitos

- Node.js
- Acceso a Internet
- Una cuenta y credenciales de OpenSky Network

No es necesario instalar paquetes adicionales para esta prueba, ya que se utiliza `fetch`, disponible en las versiones actuales de Node.js.

## Ejecutar la prueba

Desde la carpeta `pruebas/opensky`:

cmd:
node index.js(datos aviones) o node server.js(interfaz web con datos)