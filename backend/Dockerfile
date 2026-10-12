FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Usuario sin privilegios con el mismo UID que el usuario habitual del host,
# para que los archivos generados en el volumen montado (p. ej. migraciones)
# no queden a nombre de root.
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd -g ${APP_GID} app && useradd -u ${APP_UID} -g app -m app \
    && mkdir -p /data && chown app:app /data

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# El código se monta como volumen en docker-compose.yml; esta copia solo
# sirve para que la imagen funcione también sin el volumen.
COPY --chown=app:app . .

USER app

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
