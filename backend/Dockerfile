FROM python:3.11-slim

WORKDIR /app

# libpq-dev: psycopg2 build dep; gcc: compiling C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static files at build time — no DB needed, but SECRET_KEY must exist.
# The value here is build-only; the real key is injected at runtime via env.
RUN SECRET_KEY=build-only-placeholder \
    DEBUG=False \
    ALLOWED_HOSTS=* \
    DATABASE_URL=sqlite:///dev-null \
    FIELD_ENCRYPTION_KEY=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa= \
    EMAIL_HOST_USER=placeholder@example.com \
    EMAIL_HOST_PASSWORD=placeholder \
    FRONTEND_VERIFY_EMAIL_URL=http://localhost \
    FRONTEND_RESET_PASSWORD_URL=http://localhost \
    python manage.py collectstatic --noinput

# OpenShift runs containers with a random UID assigned to group 0 (root group).
# Setting group ownership to 0 and group-writable lets that arbitrary UID write
# to directories it needs (media uploads, tmp files).
COPY entrypoint.sh /entrypoint.sh
RUN chown -R 1001:0 /app /entrypoint.sh && chmod -R g=u /app && chmod +x /entrypoint.sh

# Non-root user; OpenShift may override the UID but will keep group 0.
USER 1001

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
