# Guide de Démarrage - Plateforme de Gestion Locative

## 📋 Table des matières
1. [Installation](#installation)
2. [Configuration](#configuration)
3. [Démarrage](#démarrage)
4. [Utilisation](#utilisation)
5. [API Endpoints](#api-endpoints)
6. [Architecture](#architecture)

---

## 🔧 Installation

### Prérequis
- Python 3.10+
- PostgreSQL (recommandé pour la production)
- Redis (pour Celery)
- Node.js/npm (pour le frontend optionnel)

### Étapes d'installation

#### 1. Cloner et configurer l'environnement
```bash
cd C:\Users\victu\Desktop\Immobilier
python -m venv venv
.\venv\Scripts\Activate.ps1
```

#### 2. Installer les dépendances
```bash
pip install -r requirements.txt
```

#### 3. Configurer l'environnement
Créer un fichier `.env`:
```env
DEBUG=True
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

#### 4. Effectuer les migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

#### 5. Créer un superuser (administrateur)
```bash
python manage.py createsuperuser
```

---

## ⚙️ Configuration

### Configuration la base de données

#### SQLite (Développement)
Déjà configuré par défaut dans `settings.py`

#### PostgreSQL (Production)
Remplacer dans `settings.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'immobilier_db',
        'USER': 'postgres',
        'PASSWORD': 'votre_mot_de_passe',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### Configuration Redis/Celery
Assurez-vous que Redis est en cours d'exécution:
```bash
redis-server
```

---

## 🚀 Démarrage

### Mode développement

#### Terminal 1 - Serveur Django
```bash
python manage.py runserver
```
Accédez à: http://localhost:8000

#### Terminal 2 - Celery Worker
```bash
celery -A immobilier_config worker -l info
```

#### Terminal 3 - Celery Beat (Scheduler)
```bash
celery -A immobilier_config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Mode production
```bash
# Avec Gunicorn
gunicorn immobilier_config.wsgi:application

# Avec supervisord ou systemd pour gérer les processus
```

---

## 💻 Utilisation

### Accès à l'administration
- URL: http://localhost:8000/admin
- Username: (créé avec createsuperuser)
- Password: (créé avec createsuperuser)

### API REST
Base URL: `http://localhost:8000/api/`

### Inscription et Authentification

#### Créer un compte
```bash
POST /api/utilisateurs/utilisateurs/
Content-Type: application/json

{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "SecurePassword123!",
  "password2": "SecurePassword123!",
  "first_name": "John",
  "last_name": "Doe",
  "role": "locataire",  # ou "proprietaire", "gestionnaire", "admin"
  "telephone": "+225XXXXXXXXXX"
}
```

#### Se connecter
```bash
POST /api-auth/login/
# Utiliser le session cookie pour authenticated requests
```

---

## 📡 API Endpoints

### Utilisateurs
- `GET/POST` `/api/utilisateurs/utilisateurs/` - Lister/créer utilisateurs
- `GET/PUT` `/api/utilisateurs/utilisateurs/{id}/` - Détails/modifier utilisateur
- `GET` `/api/utilisateurs/utilisateurs/me/` - Profil utilisateur connecté
- `POST` `/api/utilisateurs/utilisateurs/change_password/` - Changer mot de passe

### Biens
- `GET/POST` `/api/biens/biens/` - Lister/créer biens
- `GET/PUT` `/api/biens/biens/{id}/` - Détails/modifier bien
- `POST` `/api/biens/biens/{id}/marquer_disponible/` - Marquer comme disponible
- `POST` `/api/biens/biens/{id}/marquer_loue/` - Marquer comme loué

### Contrats
- `GET/POST` `/api/contrats/contrats/` - Lister/créer contrats
- `GET/PUT` `/api/contrats/contrats/{id}/` - Détails/modifier contrat
- `POST` `/api/contrats/contrats/{id}/activer/` - Activer contrat
- `POST` `/api/contrats/contrats/{id}/resilier/` - Résilier contrat
- `GET` `/api/contrats/contrats/{id}/paiements/` - Paiements du contrat
- `GET` `/api/contrats/contrats/{id}/statistiques/` - Statistiques contrat

### Factures
- `GET/POST` `/api/facturation/factures/` - Lister/créer factures
- `GET/PUT` `/api/facturation/factures/{id}/` - Détails/modifier facture
- `POST` `/api/facturation/factures/{id}/marquer_payee/` - Marquer comme payée
- `POST` `/api/facturation/factures/{id}/envoyer/` - Envoyer facture
- `GET` `/api/facturation/factures/echues/` - Factures échues
- `GET` `/api/facturation/factures/impayees/` - Factures impayées

### Recherche
- `GET` `/api/recherche/avancee/?ville=Abidjan&budget_min=100000&budget_max=500000` - Recherche avancée
- `POST` `/api/recherche/recherches/` - Créer recherche sauvegardée
- `POST` `/api/recherche/favoris/` - Ajouter aux favoris

### Dashboard
- `GET` `/api/dashboard/proprietaire/` - Dashboard propriétaire
- `GET` `/api/dashboard/locataire/` - Dashboard locataire
- `GET` `/api/dashboard/rapport-mensuel/?mois=2024-04-01` - Rapport mensuel

---

## 🏗️ Architecture

### Structure des apps

```
immobilier/
├── utilisateurs/          # Gestion des utilisateurs (auth, profiles)
├── biens/                  # Gestion des propriétés
├── contrats/              # Contrats de location + paiements
├── facturation/           # Factures + notifications + rappels
├── recherche/             # Moteur de recherche + favoris
├── dashboard/             # Tableaux de bord + statistiques
└── immobilier_config/     # Configuration Django + Celery
```

### Flux de facturation automatique

```
1. Chaque mois (1er à 1h00)
   └─> Génération automatique des factures
       ├─> Création des paiements
       ├─> Création des factures
       ├─> Création des notifications
       └─> Création des rappels de paiement

2. Tous les jours (8h00)
   └─> Envoi des rappels de paiement
       ├─> Premier rappel (2 jours après)
       ├─> Deuxième rappel (7 jours après)
       └─> Avis final (15 jours après)

3. Toutes les heures
   └─> Mise à jour des statistiques propriétaires
       └─> Recalcul des KPIs

4. 1er du mois (9h00)
   └─> Génération des rapports mensuels
```

### Modèles de données

#### Utilisateur
- Rôles: Propriétaire, Locataire, Gestionnaire, Admin
- Profils étendus: ProprietaireProfile, LocataireProfile

#### Bien (Propriété)
- Types: Appartement, Maison, Studio, T1-T4, T5+
- Statuts: Disponible, Loué, Maintenance, Archivé
- Photos et caractéristiques

#### Contrat
- Dates début/fin, prix, conditions
- Documents associés
- Paiements liés

#### Facturation
- Factures mensuelles automatiques
- Notifications (email, SMS, push)
- Rappels programmés 3 niveaux

---

## 📊 Fonctionnalités clés adressant le mémoire

### ✅ Module de Gestion Locative (Chapitre 6.2.1)
- Création/modification de contrats
- Suivi automatisé des paiements
- Génération mensuelle des factures
- Notifications et rappels automatiques
- Historique complet des transactions

### ✅ Module de Gestion Entreprises (Chapitre 6.2.2)
- Dashboard propriétaires avec KPIs
- Rapports mensuels détaillés
- Statistiques en temps réel
- Gestion multi-propriétés

### ✅ Module de Construction de Logements (Chapitre 6.2.3)
- Gestion des propriétés
- Photos et caractéristiques
- Équipements et aménités

### ✅ Moteur de Recherche (Objectif 4)
- Filtres multi-critères
- Géolocalisation
- Recherches sauvegardées
- Historique de recherche

### ✅ Sécurité (Chapitre 6.3)
- Authentification par session/token
- Permissions par rôle
- Validation des données
- Filtrage des accès

---

## 🐛 Dépannage

### Erreur: `app.autodiscover_tasks()` ne trouve pas les tasks
```bash
# Corriger: Créer des fichiers tasks.py dans chaque app
touch facturation/tasks.py
touch dashboard/tasks.py
```

### Erreur de migration
```bash
python manage.py makemigrations --empty utilisateurs --name fix
python manage.py migrate
```

### Redis ne disponible
```bash
# Installer et lancer Redis
# Sur Windows, télécharger depuis: https://github.com/microsoftarchive/redis/releases
redis-server
```

---

## 📚 Ressources

- Django Docs: https://docs.djangoproject.com
- DRF Docs: https://www.django-rest-framework.org
- Celery Docs: https://docs.celeryproject.io
- PostgreSQL Docs: https://www.postgresql.org/docs

---

## 📝 Notes

- Les factures sont générées automatiquement le 1er du mois
- Les rappels de paiement sont envoyés via Celery Beat
- Les statistiques se mettent à jour toutes les heures
- Utiliser PostgreSQL pour la production
- Configurer un service SMTP pour les emails
- Utiliser Gunicorn + Nginx pour la production

