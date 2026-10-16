# Monitor de aeronaves

Sistema privado que muestra en un mapa, en tiempo real, las aeronaves con transponder (ADS-B / Mode S, y las que adsb.fi recibe por MLAT) alrededor de una zona de alerta, y avisa **por Telegram y en la web** cuando una aeronave **ingresa** a la zona.

- Solo pueden entrar usuarios registrados; no hay acceso anónimo.
- Se monitorean todas las aeronaves detectadas, sin filtros.
- No publica nada en Open Glider Network ni en ninguna otra red pública: solo **lee** datos de adsb.fi.
- No guarda historial: las posiciones viven en memoria mientras el sistema está encendido.

> Esta es la **versión de desarrollo** (servidor de desarrollo de Vite, `DEBUG=true`). Para exponerla a internet hace falta una configuración de producción que este proyecto no incluye (ver [Seguridad](#seguridad)).

---

## Índice

1. [Requisitos](#requisitos)
2. [Puesta en marcha](#puesta-en-marcha)
3. [Uso](#uso)
4. [Telegram](#telegram)
5. [Zona de alerta y archivos OpenAir](#zona-de-alerta-y-archivos-openair)
6. [Configuración inicial (.env)](#configuración-inicial-env)
7. [Comandos útiles](#comandos-útiles)
8. [Cómo funciona](#cómo-funciona)
9. [Fuente de datos: adsb.fi](#fuente-de-datos-adsbfi)
10. [Estructura del proyecto](#estructura-del-proyecto)
11. [API y WebSocket](#api-y-websocket)
12. [Solución de problemas](#solución-de-problemas)
13. [Seguridad](#seguridad)
14. [Atribuciones y condiciones de uso](#atribuciones-y-condiciones-de-uso)

---

## Requisitos

Solo **Docker** y **Docker Compose** (v2, el comando `docker compose`). No hace falta instalar Python ni Node en la máquina: todo corre en contenedores.

La máquina necesita acceso a internet para consultar adsb.fi, enviar mensajes a Telegram, bajar las teselas del mapa que acompaña cada alerta y que el navegador cargue los mapas.

## Puesta en marcha

1. **Crear el archivo `.env`** a partir del ejemplo:

   ```bash
   cp .env.example .env
   ```

   Editar `.env` y poner en `DJANGO_SECRET_KEY` una clave larga y aleatoria. Se puede generar con:

   ```bash
   docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```

   El resto de los valores ya vienen con la zona ALERTA CNA 10KM. El token y el chat id de Telegram se pueden cargar acá o, más tarde, desde la web ([Telegram](#telegram)).

2. **Levantar todo** con un solo comando:

   ```bash
   docker compose up --build
   ```

   La primera vez tarda unos minutos porque construye las imágenes. Al arrancar, el backend aplica las migraciones de la base de datos solo.

3. **Crear el primer administrador** (en otra terminal, con el sistema levantado):

   ```bash
   docker compose exec backend python manage.py createsuperuser
   ```

   Pide un nombre de usuario y una contraseña. El email se puede dejar vacío: el sistema no usa correo.

4. **Abrir** <http://localhost:5173> e ingresar con ese usuario.

Para dejarlo corriendo en segundo plano: `docker compose up --build -d`. Los contenedores se reinician solos (`restart: unless-stopped`), también después de reiniciar la máquina si Docker arranca con el sistema.

## Uso

### Roles

| Rol | Puede |
|---|---|
| **Usuario registrado** | Ver el mapa con las aeronaves y su información, y recibir los avisos en pantalla. |
| **Administrador** | Lo mismo, más gestionar usuarios y cambiar la configuración. |

El superusuario creado con `createsuperuser` es siempre administrador. Los roles se guardan como grupos de Django ("Administrador" y "Usuario registrado").

### Mapa

- Muestra el área de cobertura (círculo punteado) y la **zona de alerta en rojo**.
- El zoom mínimo se ajusta al **radio de la consulta**: solo se puede alejar hasta ver el área de cobertura con un margen de 15 %, y no se puede desplazar fuera de ella. El zoom va en saltos enteros, ya que con zoom fraccionario Leaflet deja líneas visibles entre teselas; por eso a veces la vista mínima es algo más grande que el área.
- Cada aeronave es un avión orientado según su rumbo:
  - **azul**: en vuelo, fuera de la zona;
  - **rojo**: dentro de la zona;
  - **gris**: en tierra;
  - **amarillo**: la seleccionada.

  Si no informa rumbo, se dibuja un punto.
- Al hacer clic en una aeronave, en el mapa o en la lista de la derecha, se ven su identificación, altitud, velocidad, rumbo y distancia al centro.
- Arriba a la derecha del mapa se elige el fondo: **Terreno** (OpenTopoMap) o **Calles** (OpenStreetMap).
- La barra superior indica si la conexión en tiempo real está activa (**Conectado** / **Reconectando…**), la hora de la última actualización y si adsb.fi no responde.

### Avisos de ingreso a la zona

Cuando una aeronave entra a la zona aparece un aviso en pantalla para todos los usuarios conectados, con identificación, altitud, velocidad y rumbo, y suena un aviso corto. El sonido se apaga o se prende con el icono de la campana. Al hacer clic en el aviso, el mapa se centra en esa aeronave. Los ingresos de la sesión se listan en el panel derecho; esa lista se pierde al recargar la página.

El aviso se genera **solo al entrar**: no se repite mientras la aeronave sigue adentro. Si sale y vuelve a entrar, avisa de nuevo.

> El navegador solo permite sonido después de que el usuario hizo clic en la página. Si se recarga la página con la sesión ya iniciada, el sonido empieza a funcionar después del primer clic.

### Usuarios (administrador)

Desde **Usuarios** se crean, editan y desactivan usuarios, y se cambia su rol o su contraseña.

- Los usuarios **no se borran**: se desactivan y dejan de poder ingresar.
- Al desactivar a alguien o cambiarle la contraseña, se le cierran la sesión y el mapa abiertos.
- Un administrador no puede desactivarse ni quitarse el rol a sí mismo, para que el sistema nunca quede sin administrador.
- Las contraseñas tienen que cumplir las reglas de Django: al menos 8 caracteres, no ser comunes, no ser solo números y no parecerse al nombre de usuario.

### Configuración (administrador)

Desde **Configuración** se cambian la zona, la frecuencia de consulta, el radio del mapa y Telegram. Al tocar **Guardar**:

- todos los mapas abiertos se actualizan sin recargar;
- el monitor hace una consulta enseguida con los valores nuevos;
- no hace falta reiniciar nada.

Los usuarios registrados no ven esta pantalla y la API rechaza sus pedidos.

| Ajuste | Reglas |
|---|---|
| Latitud / longitud del centro | Grados decimales; sur y oeste son negativos. Debajo se muestra en grados, minutos y segundos. |
| Radio de la zona | En NM, mayor que 0. |
| Altura inferior | En metros. **0 = superficie** (sin límite inferior). |
| Altura superior | En metros, mayor que la inferior. |
| Frecuencia de actualización | En segundos, mínimo 2. Con 5 s alcanza para aviones de línea; menos solo adelanta el aviso unos segundos y consulta más seguido a un servicio gratuito. |
| Radio de la consulta y del mapa | En NM, no menor que el radio de la zona y como máximo 250 (límite de adsb.fi). |
| Telegram | Token del bot y chat id del grupo; se configuran juntos. El token se muestra enmascarado. |

## Telegram

Las alertas se envían a **un grupo** de Telegram, no a mensajes privados. Para que alguien las reciba, el administrador lo agrega al grupo desde Telegram.

### Crear el bot y obtener los datos

1. En Telegram, hablar con **@BotFather**, enviar `/newbot` y seguir los pasos. Al final entrega el **token** (formato `123456789:AA…`).
2. Crear el grupo (o usar uno existente) y **agregar el bot** como miembro.
3. Para obtener el **chat id** del grupo: escribir en el grupo `/start@nombre_del_bot` y abrir en el navegador

   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```

   En la respuesta, `"chat":{"id":-…}` es el chat id. Es un número **negativo**.
4. Cargar el token y el chat id en **Configuración → Telegram** y tocar **Guardar**.
5. Tocar **Enviar mensaje de prueba**. Si llega al grupo, ya está.

También se puede probar desde la terminal:

```bash
docker compose exec backend python manage.py telegram_test
```

### Ejemplo de alerta

Cada alerta llega como una **imagen del mapa**, con el texto como leyenda. La imagen muestra el círculo de la zona y la aeronave en su posición, orientada según su rumbo y con su indicativo y altitud. El mensaje de prueba también incluye el mapa.

```
✈️ Ingreso a ALERTA CNA 10KM
ARG1309 · LV-KNP · B38M
Altitud: 2.375 ft (724 m)
Velocidad: 142 kt
Rumbo: 127°
Distancia al centro: 3,2 NM
Hora: 14:03:21
```

### Si algo falla

El monitor lee el token y el chat id guardados **en cada envío**: si se corrigen en Configuración, el próximo aviso ya usa los valores nuevos, sin reiniciar. Los errores quedan en el log del backend con una explicación:

- **token inválido**: el bot se borró o se regeneró el token en @BotFather.
- **revisar el chat id y que el bot sea miembro del grupo**: chat id equivocado o el bot fue quitado del grupo.
- **el grupo pasó a ser supergrupo; cambiar el chat id a …**: Telegram cambia el id cuando un grupo se convierte en supergrupo (por ejemplo, al hacerlo público o al activar ciertas opciones). El mensaje indica el id nuevo.

Para **reemplazar el bot o el grupo**, cargar el token o el chat id nuevos en Configuración. Para dejar de enviar alertas por Telegram, usar **Eliminar Telegram**.

Los envíos van por una cola con al menos 3 s entre mensajes (Telegram admite unos 20 mensajes por minuto en un grupo), y se reintentan si Telegram está saturado o caído. El monitor nunca se detiene esperando a Telegram.

### La imagen del mapa

La arma el backend ([monitor/mapimage.py](backend/monitor/mapimage.py)), sin navegador:

1. Baja las teselas de **OpenStreetMap** que cubren la zona (unas 12).
2. Dibuja la zona y la aeronave encima con Pillow.
3. La envía como JPEG de unos 60 KB.

Cumple la [política de uso de teselas de OpenStreetMap](https://operations.osmfoundation.org/policies/tiles/):

- `User-Agent` propio (`ADSBFI_USER_AGENT`);
- cada tesela se guarda **en memoria** 7 días, sin escribir nada en disco;
- la atribución «© colaboradores de OpenStreetMap» va en la imagen;
- solo se piden las teselas de esa imagen, de a dos por vez.

Como la zona es fija, después de la primera alerta las teselas salen de la memoria y armar la imagen tarda unos 50 ms.

**El mapa nunca frena una alerta.** Si las teselas no se pueden bajar, si la imagen tarda más de 20 s o si Telegram la rechaza, la alerta se envía **solo con el texto** y el motivo queda en el log. Al tocar «Enviar mensaje de prueba», la respuesta indica si salió con mapa o sin él.

## Zona de alerta y archivos OpenAir

### Cuándo una aeronave está "dentro"

La zona es un **cilindro vertical**. Una aeronave está dentro cuando se cumplen todas estas condiciones:

- su distancia al centro (`dst`, en NM) es **menor** que el radio;
- su altitud barométrica es **menor** que la altura superior;
- si la altura inferior es mayor que 0, su altitud es **mayor o igual** que la altura inferior. Con base en superficie no hay límite inferior y la altitud puede ser negativa.

Una aeronave que informa `"ground"` (en tierra) o que no informa altitud **nunca** está dentro.

Las alturas de la zona se configuran en **metros** y adsb.fi informa en **pies**: la comparación se hace en pies (1 ft = 0,3048 m). Por ejemplo, el techo de 4400 m equivale a 14.435,7 ft.

> **Sobre la altitud:** `alt_baro` es la altitud de presión que transmite el transponder, referida a 1013,25 hPa, no corregida por el QNH del día. Comparada con un techo AMSL, la diferencia es de unos 30 ft por cada hPa que el QNH se aparte de 1013. Por ejemplo, con QNH 1030 son unos 500 ft (≈ 150 m).

### Cargar la zona desde un archivo OpenAir

En **Configuración → Cargar archivo OpenAir…** se elige el archivo. El sistema lo lee, **completa el formulario** y muestra un aviso. Hay que revisar los valores y tocar **Guardar** para aplicarlos.

Se admite **una sola zona circular** por archivo, según la [especificación OpenAir de Naviter (v2.1.2)](https://github.com/naviter/seeyou_file_formats/blob/main/OpenAir_File_Format_Support.md):

| Comando | Uso |
|---|---|
| `AC` | Inicio de la zona (clase; se acepta cualquier valor). |
| `AY` | Tipo (opcional). |
| `AN` | Nombre. |
| `AL` | Altura inferior: `GND`, `SFC` o `PISO` (superficie), o una altura. |
| `AH` | Altura superior. |
| `V X=` | Centro, en `DD:MM:SS` o `DD:MM.mmm`, con `N`/`S` y `E`/`W`. |
| `DC` | Radio en NM, sin unidad. |

- Alturas: `4400m` o `4400 m` (metros), `14436ft` (pies), `FL145` (nivel de vuelo); con o sin `AMSL` / `MSL`. Un número sin unidad se toma en **pies**, que es la convención de OpenAir.
- **No se admiten**: alturas `AGL` (sobre el terreno) ni `UNL` (sin límite), porque no se pueden comparar con la altitud barométrica; tampoco polígonos ni arcos (`DP`, `DA`, `DB`, `DY`).
- Los comentarios empiezan con `*`. Se aceptan archivos en UTF-8 o Latin-1.
- Si hay un error, el aviso indica el número de línea.

Archivo de la zona actual:

```
* Alerta Cañuelas CNA
AC R
AY ALERT
AN ALERTA CNA 10KM
AL PISO
AH 4400m
V X=35:06:43 S 058:43:34 W
DC 5.4
*
```

## Configuración inicial (.env)

Docker Compose pasa el archivo `.env` al backend; **nunca se copia dentro de la imagen**. Contiene secretos (la clave de Django y el token del bot): no compartirlo ni subirlo a un repositorio (ya está en `.gitignore`).

| Variable | Para qué | Valor de ejemplo |
|---|---|---|
| `DJANGO_SECRET_KEY` | Clave secreta de Django (obligatoria). | — |
| `DJANGO_DEBUG` | Modo depuración. | `true` |
| `DJANGO_ALLOWED_HOSTS` | Nombres con los que se accede al sistema. | `localhost,127.0.0.1` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Direcciones desde donde se usa la web. | `http://localhost:5173,http://127.0.0.1:5173` |
| `TZ` | Zona horaria de los mensajes de alerta. | `America/Argentina/Buenos_Aires` |
| `LOG_LEVEL` | Nivel del log (`DEBUG`, `INFO`, `WARNING`…). | `INFO` |
| `MONITOR_ENABLED` | `false` levanta la web sin consultar adsb.fi (para depurar). | `true` |
| `ADSBFI_USER_AGENT` | Identificación que se envía a adsb.fi. | `avion-monitor/0.1 (monitor privado de aeronaves)` |
| `ZONE_NAME`, `ZONE_LAT`, `ZONE_LON`, `ZONE_RADIUS_NM`, `ZONE_FLOOR_M`, `ZONE_CEILING_M` | Zona de alerta inicial. | ALERTA CNA 10KM |
| `POLL_INTERVAL_S` | Frecuencia inicial de consulta (s, mínimo 2). | `5` |
| `QUERY_RADIUS_NM` | Radio inicial de consulta y mapa (NM, máximo 250). | `50` |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Telegram inicial; vacíos = sin Telegram. | — |

> **Importante:** las variables `ZONE_*`, `POLL_INTERVAL_S`, `QUERY_RADIUS_NM` y `TELEGRAM_*` se usan **solo la primera vez**, cuando la base de datos está vacía. Después mandan los valores guardados desde la web, y cambiar el `.env` ya no tiene efecto sobre ellos. Si un valor inicial es inválido, el backend no arranca y el log explica cuál.

Para que los cambios en el `.env` se apliquen hay que recrear el contenedor: `docker compose up -d --force-recreate backend`.

## Comandos útiles

| Qué | Comando |
|---|---|
| Levantar todo | `docker compose up --build` (agregar `-d` para segundo plano) |
| Detener | `docker compose down` (los datos se conservan) |
| Ver el log del backend | `docker compose logs -f backend` |
| Ver solo las alertas | `docker compose logs -f backend \| grep ALERTA` |
| Reiniciar el backend | `docker compose restart backend` |
| Crear un administrador | `docker compose exec backend python manage.py createsuperuser` |
| Cambiar una contraseña desde la terminal | `docker compose exec backend python manage.py changepassword <usuario>` |
| Probar Telegram | `docker compose exec backend python manage.py telegram_test` |
| Correr los tests | `docker compose exec backend python manage.py test` |
| Backup de la base | `docker compose cp backend:/data/db.sqlite3 ./backup-$(date +%F).sqlite3` |
| Restaurar un backup | `docker compose stop backend && docker compose cp ./backup.sqlite3 backend:/data/db.sqlite3 && docker compose start backend` |

### Al modificar el código

El código está montado como volumen en los contenedores:

- **Frontend**: los cambios se ven al instante en el navegador.
- **Backend**: no hay recarga automática, para que el monitor no arranque dos veces. Después de cambiar código Python hay que correr `docker compose restart backend`.
- Hay que **reconstruir** (`docker compose up --build`) solo si cambian `requirements.txt` o los `Dockerfile`.
- Si cambia `package.json` (dependencias del frontend), alcanza con `docker compose restart frontend`: al arrancar, el contenedor ejecuta `npm install` y sincroniza `node_modules`, que vive en un volumen propio.

### Dónde quedan los datos

La base SQLite está en el volumen de Docker `avion_backend-data`, en `/data/db.sqlite3` dentro del contenedor. Sobrevive a `docker compose down` y a las reconstrucciones. Guarda **solo** usuarios, roles, sesiones y configuración.

Para **empezar de cero** (borra usuarios y configuración): `docker compose down -v`. Al volver a levantar, la configuración se toma otra vez del `.env`.

## Cómo funciona

```
┌────────────────────────── docker compose ───────────────────────────┐
│                                                                     │
│  frontend (Vite, :5173)            backend (daphne, :8000)          │
│  ┌──────────────────┐   /api  ──▶  ┌─────────────────────────────┐  │
│  │ Vue 3 + Leaflet  │   /ws   ──▶  │ Django + DRF + Channels     │  │
│  └──────────────────┘   (proxy)    │                             │  │
│          ▲                         │  monitor (tarea asyncio) ───┼──┼──▶ adsb.fi
│          │ navegador               │   └─ cola de Telegram ──────┼──┼──▶ Telegram
│                                    │  SQLite (/data, volumen)    │  │
│                                    └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

- **Un solo proceso en el backend.** daphne (servidor ASGI) atiende la web, la API y los WebSocket. El monitor es una tarea asyncio que arranca con el servidor, en el mismo proceso y el mismo event loop. daphne no implementa el protocolo *lifespan* de ASGI, así que el monitor se engancha al arranque del reactor de Twisted ([config/asgi.py](backend/config/asgi.py)). No hay Redis, Celery, gunicorn ni nginx.
- **Ciclo del monitor** ([monitor/service.py](backend/monitor/service.py)), cada *N* segundos, medidos de inicio a inicio:
  1. Lee la configuración guardada, así los cambios se aplican sin reiniciar.
  2. Hace **una** consulta a adsb.fi centrada en el centro de la zona.
  3. Actualiza el estado en memoria y detecta los ingresos.
  4. Encola las alertas de Telegram y avisa a los navegadores.
  5. Envía a los navegadores la lista completa de aeronaves.
- **Estado en memoria** ([monitor/state.py](backend/monitor/state.py)): dos diccionarios.
  - `aircraft`: `hex` → última posición (indicativo, matrícula, tipo, lat, lon, altitud, velocidad, rumbo, distancia, hora).
  - `inside`: `hex` de las aeronaves que están dentro de la zona.

  Una aeronave se **purga** cuando su última posición tiene más de 60 s (calculado con `now − seen_pos` de la respuesta), no por faltar en una respuesta puntual. Si cambia el centro o el radio de la consulta, se descarta lo que no vino en la respuesta nueva.
- **Errores de adsb.fi:** reintenta con espera creciente (2×, 4×, 8×… la frecuencia, hasta 5 minutos), respeta el `Retry-After` de un 429 y nunca se cae. Mientras no hay respuesta, igual purga las aeronaves viejas.
- **Datos incompletos:** una aeronave sin `lat`, `lon`, `dst` o `seen_pos` no se usa y se registra en el log una sola vez, cuando empieza a faltarle. Si faltan en **todas** las aeronaves de una respuesta, se registra un error (posible cambio de formato de la API).
- **Tiempo real:** WebSocket con Django Channels y capa de canales en memoria. Exige sesión iniciada.

## Fuente de datos: adsb.fi

Se usa **únicamente** la [API abierta de adsb.fi](https://github.com/adsbfi/opendata), sin clave ni cuenta.

- Endpoint: `GET https://opendata.adsb.fi/api/v3/lat/{lat}/lon/{lon}/dist/{NM}`.
  - La especificación original pedía `v2`, pero la documentación de adsb.fi marca el `v2/lat/lon/dist` como **obsoleto** ("deprecated") y recomienda `v3`.
  - El formato es readsb `jv2`, compatible con ADSBexchange v2: aeronaves en `ac` y `now` en **milisegundos** ([definición de campos](https://github.com/wiedehopf/readsb/blob/dev/README-json.md)).
- Radio máximo: **250 NM** (verificado: 251 responde 400). `dst` está en NM, medido desde el punto consultado.
- Límite: 1 consulta por segundo. El sistema consulta como máximo cada 2 s (la frecuencia mínima configurable), deja al menos 2 s entre consultas aunque se pida un refresco inmediato, y envía un `User-Agent` identificable. El margen sobre el límite cubre demoras y reintentos, que de otro modo podrían dar un 429.
- adsb.fi bloquea temporalmente la IP si recibe muchos pedidos inválidos (400, 429, etc.). Por eso el sistema valida coordenadas y radio **antes** de consultar.
- Campos usados: `hex`, `flight` (sin los espacios finales), `r` (matrícula), `t` (tipo), `lat`, `lon`, `alt_baro` (pies o `"ground"`), `gs` (nudos), `track` (rumbo), `dst`, `seen_pos`. `true_heading` se usa solo para orientar el ícono cuando falta `track`, algo habitual en tierra.

## Estructura del proyecto

```
.
├── docker-compose.yml        Servicios backend y frontend
├── .env.example              Plantilla de configuración (copiar a .env)
├── backend/
│   ├── Dockerfile, entrypoint.sh, requirements.txt
│   ├── config/               Ajustes de Django, URLs, ASGI (arranque del monitor)
│   ├── accounts/             Login, roles (grupos) y gestión de usuarios
│   ├── configuration/        Modelo SystemConfig (fila única) y su API
│   └── monitor/
│       ├── adsbfi.py         Cliente y lectura de la respuesta de adsb.fi
│       ├── zone.py           Cilindro de la zona y conversión m ↔ ft
│       ├── openair.py        Lectura de archivos OpenAir
│       ├── state.py          Diccionarios en memoria, ingresos y purga
│       ├── service.py        Ciclo del monitor
│       ├── alerts.py         Contenido de la alerta
│       ├── telegram.py       Envío a Telegram (cola, reintentos, foto con leyenda)
│       ├── mapimage.py       Imagen del mapa para la alerta (teselas OSM + Pillow)
│       ├── broadcast.py      Mensajes a los navegadores
│       ├── consumers.py      WebSocket /ws/aircraft/
│       ├── management/       Comando telegram_test
│       └── tests/            Tests (incluye una respuesta real de adsb.fi)
└── frontend/
    ├── Dockerfile, package.json, vite.config.js (proxy /api y /ws)
    └── src/
        ├── api.js, session.js, live.js     API, sesión y WebSocket
        ├── confirm.js                      Diálogo de confirmación
        ├── components/AircraftMap.vue      Mapa Leaflet
        ├── components/AlertToasts.vue      Avisos en pantalla (toasts)
        ├── components/ConfirmDialog.vue    Modal de confirmación
        ├── components/FormField.vue        Campo de formulario con etiqueta, unidad y error
        ├── views/                          Login, Mapa, Usuarios, Configuración
        └── styles.css                      Los pocos estilos propios (el resto es Bootstrap)
```

### Interfaz

La interfaz usa **[Bootstrap 5](https://getbootstrap.com/)** (solo el CSS) y **[Bootstrap Icons](https://icons.getbootstrap.com/)**:

- Los componentes interactivos (modales, avisos) los maneja Vue, así que no se carga el JavaScript de Bootstrap.
- Los íconos se usan como clases (`<i class="bi bi-gear">`). Los marcadores del mapa usan los SVG `airplane-fill` y `circle-fill` del mismo paquete, para poder rotarlos según el rumbo y darles contorno.
- Los colores son los de Bootstrap: rojo `danger` para la zona y las alertas, azul `primary` para las aeronaves y amarillo `warning` para la seleccionada.

## API y WebSocket

Todas las rutas exigen sesión, salvo `csrf` y `login`. Sin sesión responden **401**; si el usuario no es administrador, **403**. Los pedidos que modifican algo llevan el encabezado `X-CSRFToken`.

| Método y ruta | Descripción | Rol |
|---|---|---|
| `GET /api/auth/csrf/` | Entrega la cookie CSRF. | — |
| `POST /api/auth/login/` | `{username, password}`. Máximo 10 intentos por minuto por usuario. | — |
| `POST /api/auth/logout/` | Cierra la sesión. | Con sesión |
| `GET /api/auth/me/` | Usuario actual y su rol. | Con sesión |
| `GET, POST /api/users/` | Listar y crear usuarios. | Admin |
| `GET, PATCH /api/users/{id}/` | Ver y editar (rol, contraseña, `is_active`). | Admin |
| `GET, PUT, PATCH /api/config/` | Configuración (el token se devuelve enmascarado). | Admin |
| `POST /api/config/openair/` | Archivo OpenAir (`multipart`, campo `file`): devuelve los campos de la zona **sin guardarlos**. | Admin |
| `POST /api/config/telegram-test/` | Envía un mensaje de prueba al grupo. | Admin |
| `GET /api/health/` | Estado del backend. | — |

**WebSocket** `ws://<host>/ws/aircraft/`: solo envía datos del servidor al navegador, en JSON con un campo `type`.

| `type` | Cuándo | Contenido |
|---|---|---|
| `snapshot` | Al conectarse. | `aircraft`, `config` (sin el token) y `status`. |
| `aircraft` | En cada ciclo. | Lista completa de aeronaves (cada una con `inside`) y `status`. |
| `alert` | Una aeronave ingresó a la zona. | `alert`: identificación, altitud, velocidad, rumbo, distancia y hora. |
| `config` | El administrador guardó cambios. | `config`. |

Conexiones rechazadas: sin sesión, usuario desactivado u origen no permitido. Al desactivar un usuario, su conexión se cierra con el código 4401.

## Solución de problemas

| Síntoma | Qué revisar |
|---|---|
| La web no abre | `docker compose ps`: los dos servicios deben estar `Up`. Ver `docker compose logs backend frontend`. |
| El backend no arranca | El log explica la causa: falta `DJANGO_SECRET_KEY`, o hay un valor inicial inválido en el `.env`. |
| `exec: "/app/entrypoint.sh": permission denied` | Versión vieja del `Dockerfile`: el script perdió el permiso de ejecución (pasa al copiarlo por git). Correr `chmod +x backend/entrypoint.sh`, o actualizar el `Dockerfile`, que ahora lo ejecuta con `sh` y no depende de ese permiso, y reconstruir con `docker compose up --build`. |
| `/bin/sh^M` o `entrypoint.sh: not found` | El script quedó con fin de línea de Windows (CRLF). El `.gitattributes` lo evita en clones nuevos; en uno existente, `sed -i 's/\r$//' backend/entrypoint.sh`. |
| "Reconectando…" permanente | Backend caído o reiniciándose: `docker compose logs -f backend`. |
| "adsb.fi sin respuesta" | Sin internet, adsb.fi caído o limitado (429). El monitor reintenta solo; el detalle está en el log. |
| No aparecen aeronaves | Puede que no haya tráfico en el área. Revisar el log por errores de adsb.fi y que `MONITOR_ENABLED=true`. |
| No llegan alertas a Telegram | **Enviar mensaje de prueba** en Configuración, o `manage.py telegram_test`. Ver [Telegram → Si algo falla](#si-algo-falla). |
| Cambié el `.env` y no pasa nada | Los valores de zona, frecuencia y Telegram del `.env` solo se usan con la base vacía: cambiarlos desde la web. Para el resto, `docker compose up -d --force-recreate backend`. |
| Cambié código Python y no se nota | `docker compose restart backend` (no hay recarga automática). |
| "Demasiados intentos" al ingresar | Límite de 10 intentos por minuto: esperar un minuto. |
| Olvidé la contraseña del administrador | `docker compose exec backend python manage.py changepassword <usuario>` |

## Seguridad

- Acceso solo con usuario y contraseña. Sesión de Django con cookie, protección CSRF y límite de intentos de login.
- El token del bot se guarda en la base SQLite **en texto plano** y nunca se envía a los navegadores ni aparece en el log. Quien tenga acceso a la máquina o al volumen de Docker puede leerlo. Si se filtra, generar uno nuevo en @BotFather (`/revoke`) y cargarlo en Configuración.
- `.env` contiene secretos: no compartirlo ni subirlo a un repositorio.
- **Esta es la versión de desarrollo.** Para exponerla a internet hacen falta, como mínimo:
  - `DJANGO_DEBUG=false`;
  - HTTPS;
  - servir el frontend compilado (`vite build`) en lugar del servidor de desarrollo;
  - no publicar el puerto 8000 del backend.

## Atribuciones y condiciones de uso

- **Datos de aeronaves: [adsb.fi](https://adsb.fi/).** Sus condiciones exigen citar a adsb.fi con un enlace a su página, y permiten **solo uso personal y no comercial**. El mapa muestra la atribución.
- **Mapas:** © [colaboradores de OpenStreetMap](https://www.openstreetmap.org/copyright). La capa de terreno es © [OpenTopoMap](https://opentopomap.org) (CC-BY-SA), con datos SRTM. Las atribuciones se muestran en el mapa web y en la imagen que se envía por Telegram, como exigen sus condiciones.
- Biblioteca de mapas: [Leaflet](https://leafletjs.com).
- Interfaz: [Bootstrap](https://getbootstrap.com/) y [Bootstrap Icons](https://icons.getbootstrap.com/) (licencia MIT).
