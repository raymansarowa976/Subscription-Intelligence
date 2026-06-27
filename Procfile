web: python manage.py migrate && gunicorn config.wsgi --bind 0.0.0.0:$PORT
worker: python manage.py run_huey
