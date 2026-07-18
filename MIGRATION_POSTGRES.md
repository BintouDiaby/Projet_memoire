# Migrer les données vers PostgreSQL

Ce projet utilisait SQLite (un simple fichier `db.sqlite3`), ce qui pose
problème sur la plupart des hébergeurs cloud : le disque n'est pas
persistant, donc le fichier se réinitialise à chaque redéploiement.

Le code a été modifié pour lire la configuration de la base depuis `.env` —
il suffit de renseigner les identifiants PostgreSQL, sans toucher au code.

## 1. Récupérer les identifiants PostgreSQL

Depuis l'hébergeur (panneau d'administration), noter :
- Hôte (host)
- Port (généralement `5432`)
- Nom de la base
- Utilisateur
- Mot de passe

## 2. Configurer `.env`

Sur le serveur, dans le fichier `.env` à la racine du projet, ajouter (ou
décommenter) :

```
DB_ENGINE=django.db.backends.postgresql
DB_NAME=nom_de_la_base
DB_USER=utilisateur
DB_PASSWORD=mot_de_passe
DB_HOST=hote
DB_PORT=5432
```

## 3. Installer les dépendances et créer les tables

```bash
pip install -r requirements.txt
python manage.py migrate
```

## 4. Importer les données existantes

Le fichier `data_export.json` (à la racine du projet) contient toutes les
données actuelles : comptes, entreprises, biens, contrats, paiements, etc.
Il a été testé avec succès (import complet sans erreur, comptes vérifiés
fonctionnels).

```bash
python manage.py loaddata data_export.json
```

## 5. Vérifier

```bash
python manage.py shell -c "from utilisateurs.models import Utilisateur; print(Utilisateur.objects.count(), 'comptes')"
```

Si le nombre de comptes affiché correspond à ce qu'il y a en local (23 au
moment de la préparation de ce guide), la migration est réussie. Redémarrer
le serveur applicatif et tester une connexion avec un compte existant.

## Remarque

Sans configuration PostgreSQL dans `.env`, le projet continue de fonctionner
normalement avec SQLite (utile pour le développement local) — ce changement
n'affecte donc rien tant que ces variables ne sont pas définies.
