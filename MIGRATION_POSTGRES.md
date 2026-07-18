# MIGRATION_POSTGRES.md

Ce fichier décrit les étapes pour migrer la base de données SQLite vers PostgreSQL sur le serveur.

Prérequis sur le serveur : accès SSH, Python venv activé (optionnel mais recommandé), PostgreSQL disponible et un rôle/BD créés.

1) Récupérer la dernière version du code

    git pull origin main

2) Mettre les identifiants Postgres dans `.env` (remplacer par les vraies valeurs)

    DB_ENGINE=django.db.backends.postgresql
    DB_NAME=nom_de_la_base
    DB_USER=utilisateur
    DB_PASSWORD=mot_de_passe
    DB_HOST=hote
    DB_PORT=5432

3) Installer les dépendances

    pip install -r requirements.txt

4) Créer les tables dans la nouvelle base

    python manage.py migrate

5) Importer les données exportées (fichier `data_export.json` présent dans le dépôt)

    python manage.py loaddata data_export.json

6) Vérifier les comptes et créer un superuser si nécessaire

    python manage.py shell -c "from django.contrib.auth import get_user_model; User=get_user_model(); print('USERS', User.objects.count()); print(list(User.objects.filter(is_superuser=True).values('username','email')) )"

    # Facultatif : créer un superuser
    python manage.py createsuperuser

7) Redémarrer le serveur applicatif (systemd / docker / supervision selon l'environnement)

    # Example systemd
    sudo systemctl restart bintou.service

    # Example Docker Compose
    docker compose down && docker compose up -d --build

Notes & conseils :
- `psycopg2-binary` est déjà listé dans `requirements.txt`.
- Si un signal métier déclenche des inserts durant l'import, désactivez temporairement le signal
  (ou utilisez une copie isolée de la base pour l'import) — un correctif a déjà été appliqué pour
  éviter la création de paiements fantômes.
- Sauvegardez toujours `db.sqlite3` avant d'écraser quoi que ce soit.

Si tu veux, je peux :
- appliquer la lecture des variables d'environnement (déjà faite),
- vérifier que `psycopg2-binary` est présent (oui),
- ou exécuter les étapes sur le serveur si tu me fournis l'accès (SSH/credentials).
