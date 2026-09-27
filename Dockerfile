FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

# Build deps for psycopg2/wheels are not needed at runtime; Pillow ships wheels.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# collectstatic needs a SECRET_KEY only because settings refuse to boot without
# one when DEBUG=False. The value here is a build-time throwaway: it only signs
# static-file manifest entries, never a session, and is not present at runtime.
RUN DJANGO_SECRET_KEY=build-only-not-used-at-runtime \
    DJANGO_DEBUG=False \
    python manage.py collectstatic --noinput

# Run as a non-root user so a container escape cannot own the host.
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# migrate runs on every start so a fresh or wiped volume is always usable.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 4 --timeout 120"]
