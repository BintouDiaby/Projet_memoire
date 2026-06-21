# 🏢 Plateforme Web et Mobile de Gestion Locative

[![Django](https://img.shields.io/badge/Django-6.0-green?logo=django)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.14-red?logo=python)](https://www.django-rest-framework.org/)
[![Celery](https://img.shields.io/badge/Celery-Async-37B24D?logo=celery)](https://docs.celeryproject.io)

**Plateforme complète de gestion locative** conçue pour automatiser la gestion des propriétés, des contrats et de la facturation mensuelle.

## ⭐ Fonctionnalités principales

### 💰 Facturation Automatique (Core Feature)
- **Génération mensuelle**: Le 1er du mois à 1h00
- **3 niveaux de rappels**: J+2, J+7, J+15 après échéance
- **Détection retards**: Mineur, majeur, impayé
- **Notifications**: Email, SMS (prêt pour Twilio)

### 🔍 Moteur de Recherche
- Filtres multi-critères (prix, localisation, type, chambres)
- Recherches sauvegardées
- Favoris avec notes
- Historique personnalisé

### 📋 Gestion des Contrats
- CRUD complet
- Documents associés
- Suivi paiements mensuels
- Statuts automatisés

### 📊 Tableaux de Bord
- **Propriétaire**: KPIs, revenus, taux collecte, impayés
- **Locataire**: Paiements, contrats, visites
- Rapports mensuels financiers
- Alertes système

### 👥 Gestion Utilisateurs
- 4 rôles: Propriétaire, Locataire, Gestionnaire, Admin
- Profils étendus
- Authentification sécurisée
- Audit logs complets

## 📋 Table des matières

- [Installation](#installation)
- [Configuration](#configuration)
- [Structure du Projet](#structure-du-projet)
- [Utilisateurs et Rôles](#utilisateurs-et-rôles)
- [Fonctionnalités](#fonctionnalités)
- [API](#api)
- [Tâches Programmées](#tâches-programmées)
- [Déploiement](#déploiement)

## 🚀 Installation

### Prérequis

- Python 3.10+
- PostgreSQL (recommandé) ou MySQL
- Redis (pour Celery)
- pip

### Étapes d'installation

1. **Cloner ou accéder au projet**
   ```bash
   cd C:/Users/victu/Desktop/Immobilier
   ```

2. **Créer et activer l'environnement virtuel**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

4. **Créer le fichier `.env`**
   ```bash
   Copy-Item .env.example .env
   ```

5. **Exécuter les migrations**
   ```bash
   python manage.py migrate
   ```

6. **Créer un superutilisateur (administrateur)**
   ```bash
   python manage.py createsuperuser
   ```

7. **Lancer le serveur de développement**
   ```bash
   python manage.py runserver
   ```

Le serveur sera disponible sur : `http://localhost:8000/`

## ⚙️ Configuration

### Base de données

Par défaut, le projet utilise SQLite. Pour la production, utilisez PostgreSQL :

```py
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

### Email (pour les factures automatiques)

Configurez votre provider SMTP dans `.env` :

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=votre_email@gmail.com
EMAIL_HOST_PASSWORD=votre_mot_de_passe_app
```

### Celery et Redis

Pour la facturation automatique et les rappels :

```bash
# Lancer le worker Celery
celery -A immobilier_config worker -l info

# Lancer le beat scheduler
celery -A immobilier_config beat -l info
```

## 📁 Structure du Projet

```
Immobilier/
├── immobilier_config/      # Configuration Django
│   ├── settings.py         # Paramètres
│   ├── urls.py            # URLs principales
│   └── wsgi.py            # Production
├── utilisateurs/           # Gestion des utilisateurs
│   ├── models.py          # Utilisateur, ProprietaireProfile, LocataireProfile
│   ├── views.py           # APIs utilisateurs
│   └── admin.py           # Interface admin
├── biens/                  # Gestion des biens immobiliers
│   ├── models.py          # Bien, PhotoBien, Visite
│   └── views.py           # APIs biens
├── contrats/              # Gestion des contrats
│   ├── models.py          # Contrat, Paiement, DocumentContrat
│   └── views.py           # APIs contrats
├── facturation/           # Facturation automatique
│   ├── models.py          # Facture, Notification, RappelPaiement
│   ├── signals.py         # Génération automatique de paiements
│   └── tasks.py           # Tâches Celery (facturation)
├── recherche/             # Moteur de recherche
│   ├── models.py          # RechercheSauvegardee, BienFavori, HistoriqueRecherche
│   └── views.py           # Recherche avancée
├── dashboard/             # Tableaux de bord
│   └── views.py           # Dashboards proprietaire, locataire, admin
├── manage.py              # CLI Django
├── requirements.txt       # Dépendances
├── .env.example           # Fichier d'env exemple
└── README.md              # Ce fichier
```

## 👥 Utilisateurs et Rôles

### Rôles disponibles

1. **Propriétaire**
   - Créer et gérer les biens
   - Gérer les contrats de location
   - Voir les paiements et factures
   - Tableaud de bord propriétaire

2. **Gestionnaire**
   - Gérer le parc pour les propriétaires
   - Suivi des paiements
   - Génération de rapports

3. **Locataire**
   - Rechercher des biens
   - Consulter ses factures
   - Tracker les paiements
   - Historique des locations

4. **Administrateur**
   - Accès complet au site
   - Modération
   - Statistiques globales

## ✨ Fonctionnalités

### Gestion Immobilière
- ✅ Création et gestion des biens
- ✅ Photos multiples par bien
- ✅ Visite programmées
- ✅ Équipements et caractéristiques

### Contrats et Locations
- ✅ Génération automatique de contrats
- ✅ Signature électronique (préparée)
- ✅ Suivi des dates de début/fin
- ✅ Documents associés (avenants, etc.)

### Facturation Automatique
- ✅ Génération automatique de factures
- ✅ Envoi par email
- ✅ Rappels de paiement programmés
- ✅ Suivi des impayés
- ✅ Génération de PDF (prête)

### Recherche de Biens
- ✅ Filtres multi-critères
- ✅ Budget, localisation, nombre de chambres
- ✅ Historique de recherche
- ✅ Biens favoris

### Dashboards
- ✅ Propriétaire : Chiffre d'affaires, paiements
- ✅ Locataire : Paiements à venir, factures
- ✅ Admin : Statistiques globales

## 🔌 API

### Endpoints principaux

#### Utilisateurs
```
GET/POST /api/utilisateurs/
GET /api/utilisateurs/me/  # Profil connecté
```

#### Biens
```
GET/POST /api/biens/biens/
GET /api/biens/biens/?ville=Abidjan&budget_max=500000
GET/POST /api/biens/visites/
```

#### Contrats
```
GET/POST /api/contrats/contrats/
GET /api/contrats/paiements/
```

#### Facturation
```
GET /api/facturation/factures/
GET /api/facturation/notifications/
```

#### Recherche
```
GET /api/recherche/search/?ville=Abidjan&budget_max=500000
GET/POST /api/recherche/favoris/
```

#### Dashboard
```
GET /api/dashboard/proprietaire/
GET /api/dashboard/locataire/
GET /api/dashboard/admin/
```

Authentification : `/api-auth/login/`

## ⏰ Tâches Programmées

### Facturation mensuelle
À 1h du matin le 1er jour de chaque mois :
- Génération des factures
- Envoi par email
- Création des rappels

### Rappels de paiement
- 2 jours après l'échéance : premier rappel
- 7 jours après : deuxième rappel
- 15 jours après : avis final

## 🚀 Déploiement

### Production (avec Gunicorn + Nginx)

1. **Installer Gunicorn**
   ```bash
   pip install gunicorn
   ```

2. **Lancer Gunicorn**
   ```bash
   gunicorn immobilier_config.wsgi --bind 0.0.0.0:8000
   ```

3. **Configurer Nginx**
   ```nginx
   server {
       listen 80;
       server_name immobilier.com;
       
       location / {
           proxy_pass http://127.0.0.1:8000;
       }
       
       location /static/ {
           alias /path/to/static/;
       }
   }
   ```

### Variables de production
```
DEBUG=False
ALLOWED_HOSTS=immobilier.com,www.immobilier.com
SECRET_KEY=votre_clé_secrète_très_longue
DATABASE_URL=postgres://user:pass@host/db
```

## 📖 Documentation

- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Celery Documentation](https://docs.celeryproject.org/)

## 🤝 Support

Pour toute question ou problème, contactez :
- Email: support@immobilier.local
- GitHub Issues: [lien vers le repo]

---

**Développé en 2025 pour l'Institut Ivoirien de Technologie**
