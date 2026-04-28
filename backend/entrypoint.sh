#!/bin/sh
set -e

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Seeding badges..."
python manage.py seed_badges

echo "Starting Daphne on port 8080..."
exec daphne -b 0.0.0.0 -p 8080 chore_sync.asgi:application
