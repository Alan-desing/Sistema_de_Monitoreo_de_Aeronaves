# Prueba OpenSky - Proyecto Aviones

Esta carpeta contiene las primeras pruebas realizadas con OpenSky Network para el proyecto de monitoreo de aeronaves.

## Objetivo

El objetivo de esta prueba es comprobar que podemos conectarnos a la API de OpenSky, recibir información de aeronaves y utilizar esos datos desde un programa desarrollado con Node.js.

Esta prueba todavía no representa el sistema definitivo. Es una primera etapa para comprobar el acceso a los datos antes de desarrollar las funciones principales del proyecto.

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

Levanta una pequeña interfaz web de prueba.

La interfaz consulta OpenSky y muestra los datos recibidos en una tabla desde el navegador.

Actualmente la página obtiene los datos una vez cada vez que se carga o recarga.

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

## Requisitos

- Node.js
- Acceso a Internet

No es necesario instalar paquetes adicionales para esta prueba, ya que se utiliza `fetch`, disponible en las versiones actuales de Node.js.

## Ejecutar la prueba de consola

Desde pruebas/opensky:

cmd: node index.js (Datos aviones) o node server.js (Interfaz con datos aviones)