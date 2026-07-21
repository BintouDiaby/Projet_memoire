# Image de l'application ImmoGérer (code Django uniquement — AUCUNE donnée, AUCUN secret).
# Les données (PostgreSQL, photos) vivent dans des volumes Docker sur la VM, pas ici.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dépendances système minimales (libpq pour PostgreSQL).
# psycopg2-binary et Pillow embarquent leurs bibliothèques via des wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installer les dépendances d'abord (cache Docker : ne réinstalle que si requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code du projet
COPY . .

EXPOSE 8000

# Commande par défaut (surchargée par docker-compose pour chaque service)
CMD ["gunicorn", "immobilier_config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
