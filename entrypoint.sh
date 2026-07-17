#!/bin/sh
set -e

# Apply database migrations, collectstatic, then start the server
if [ "$DATABASE_URL" != "" ] || [ -f ".env" ]; then
  echo "Applying migrations..."
  python manage.py migrate --noinput || true
  echo "Collecting static files..."
  python manage.py collectstatic --noinput || true
fi

exec "$@"
