#!/bin/sh
set -e

python manage.py migrate --noinput

# Un único proceso daphne, sin autorreload: el monitor de aeronaves vive
# dentro de este proceso y no debe arrancar dos veces.
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
