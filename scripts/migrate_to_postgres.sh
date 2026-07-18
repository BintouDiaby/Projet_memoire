#!/usr/bin/env bash
set -euo pipefail

# Script d'aide pour migrer le projet vers PostgreSQL depuis la racine du projet.
# Usage: source .env && ./scripts/migrate_to_postgres.sh

echo "1/ Ensure python deps"
pip install -r requirements.txt

echo "2/ Apply migrations"
python manage.py migrate --noinput

echo "3/ Load fixtures (data_export.json)"
if [ -f data_export.json ]; then
  python manage.py loaddata data_export.json
else
  echo "data_export.json not found; skipping loaddata"
fi

echo "4/ Collect static files"
python manage.py collectstatic --noinput

echo "Migration steps completed. Restart your app server and verify." 
