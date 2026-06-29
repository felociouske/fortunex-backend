#!/bin/sh

python manage.py migrate
python manage.py collectstatic --noinput

python manage.py run_price_engine &

exec daphne -b 0.0.0.0 -p $PORT fortunex_backend.asgi:application