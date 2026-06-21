# ⚡ Référence Rapide - Commandes Utiles

**Plateforme de Gestion Locative**

---

## 🚀 Démarrage Rapide

### 1. Démarrer le projet (Développement)

**Terminal 1 - Serveur Django**
```bash
cd C:\Users\victu\Desktop\Immobilier
.\venv\Scripts\Activate.ps1
python manage.py runserver
# Accès: http://localhost:8000
```

**Terminal 2 - Redis**
```bash
redis-server
```

**Terminal 3 - Celery Worker**
```bash
celery -A immobilier_config worker -l info
```

**Terminal 4 - Celery Beat**
```bash
celery -A immobilier_config beat -l info
```

---

## 📦 Gestion des Packages

### Installer dépendances
```bash
pip install -r requirements.txt
```

### Ajouter nouveau package
```bash
pip install package_name
pip freeze > requirements.txt
```

### Vérifier versions
```bash
pip list
pip show django
```

---

## 🗄️ Gestion de la Base de Données

### Créer migrations
```bash
python manage.py makemigrations
python manage.py makemigrations utilisateurs
```

### Appliquer migrations
```bash
python manage.py migrate
python manage.py migrate utilisateurs
```

### Revert migration
```bash
python manage.py migrate utilisateurs 0001  # Revert à spécifique
```

### Voir statut migrations
```bash
python manage.py showmigrations
```

### Shell interactif
```bash
python manage.py shell
```

**Exemples dans shell**:
```python
from utilisateurs.models import Utilisateur
user = Utilisateur.objects.create_user(
    username='test',
    password='test123',
    role='propriétaire'
)

from biens.models import Bien
bien = Bien.objects.create(titre='T4', prix_mensuel=350000)

from contrats.models import Contrat
contrat = Contrat.objects.all().first()
```

---

## 👤 Gestion Admin

### Créer superuser
```bash
python manage.py createsuperuser
# Username: admin
# Email: admin@example.com
# Password: ****
```

### Admin interface
```
http://localhost:8000/admin
```

### Modifier superuser
```bash
python manage.py changepassword admin
```

### Créer user via shell
```bash
python manage.py shell
```

```python
from utilisateurs.models import Utilisateur
u = Utilisateur.objects.create_user(
    username='jean',
    email='jean@example.com',
    password='pass123',
    role='locataire'
)
```

---

## 🔍 Tests API

### Endpoints principaux

**Utilisateurs**
```bash
# Créer compte
curl -X POST http://localhost:8000/api/utilisateurs/utilisateurs/ \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"pass123","password2":"pass123","role":"locataire"}'

# Mon profil
curl http://localhost:8000/api/utilisateurs/utilisateurs/me/
```

**Biens**
```bash
# Lister propriétés
curl http://localhost:8000/api/biens/biens/

# Recherche
curl "http://localhost:8000/api/biens/biens/?search=abidjan"

# Créer bien
curl -X POST http://localhost:8000/api/biens/biens/ \
  -H "Content-Type: application/json" \
  -d '{"titre":"T3","prix_mensuel":250000}'
```

**Recherche Avancée**
```bash
curl "http://localhost:8000/api/recherche/avancee/?ville=Abidjan&budget_max=500000&chambres_min=2"
```

**Dashboard**
```bash
# Propriétaire
curl http://localhost:8000/api/dashboard/proprietaire/

# Locataire
curl http://localhost:8000/api/dashboard/locataire/

# Rapports
curl "http://localhost:8000/api/dashboard/rapport-mensuel/?mois=2026-04-01"
```

**Facturation**
```bash
# Factures
curl http://localhost:8000/api/facturation/factures/

# Factures impayées
curl http://localhost:8000/api/facturation/factures/impayees/

# Rappels
curl http://localhost:8000/api/facturation/rappels/
```

---

## 🔧 Gestion Celery

### Voir les tâches enregistrées
```bash
python manage.py shell
from immobilier_config import celery_app
celery_app.tasks
```

### Exécuter manuelle tâche
```python
from facturation.tasks import generer_factures_mensuelles
generer_factures_mensuelles.delay()
# ou
generer_factures_mensuelles()  # Syncrone
```

### Monitoring Celery
```bash
celery -A immobilier_config events
```

### Purger queue
```bash
celery -A immobilier_config purge
```

---

## 📊 Debug

### Django Debug Toolbar
```bash
# Activer dans settings.py (si développement)
INSTALLED_APPS += ['debug_toolbar']
```

### Print statements
```python
print("Variable:", variable)  # Affiche en console
```

### Django shell logging
```python
import logging
logger = logging.getLogger(__name__)
logger.info("Message info")
logger.warning("Message warning")
logger.error("Message erreur")
```

### Vérifier variables d'environnement
```python
import os
print(os.getenv('DEBUG'))
print(os.getenv('DATABASE_URL'))
```

---

## 📈 Stats & Performance

### Voir toutes les routes
```bash
python manage.py show_urls
```

### Compter modèles
```bash
python manage.py shell
from django.apps import apps
for model in apps.get_models():
    print(model.__name__, model.objects.count())
```

### Voir queries SQL
```python
from django.db import connection
from django.test.utils import CaptureQueriesContext

with CaptureQueriesContext(connection) as context:
    # Votre code ici
    pass

print(context.captured_queries)
```

---

## 🔒 Sécurité

### Générer SECRET_KEY
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Tests sécurité Django
```bash
python manage.py check --deploy
```

### Vérifier permissions fichiers
```bash
# Linux/Mac
ls -la
chmod 755 manage.py

# Windows
icacls manage.py /grant Everyone:F
```

---

## 📝 Logging

### Configurer fichier log
```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/django.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

### Vérifier logs
```bash
tail -f logs/django.log
tail -f logs/celery.log
```

---

## 🌍 Environnement

### Activer venv
```bash
# Windows
.\venv\Scripts\Activate.ps1

# Linux/Mac
source venv/bin/activate
```

### Désactiver venv
```bash
deactivate
```

### Voir Python utilisé
```bash
where python     # Windows
which python     # Linux
```

### Créer nouveau venv
```bash
python -m venv venv_new
```

---

## 🧹 Nettoyage

### Supprimer fichiers temporaires
```bash
rm -rf __pycache__
rm -rf .pytest_cache
rm -rf htmlcov
```

### Réinitialiser base de données (DANGER!)
```bash
python manage.py flush  # Supprime tout
py manage.py migrate    # Réappliquer migrations
```

### Effacer fichiers médias
```bash
rm -rf media/*
```

---

## 📚 Fichiers Importants

| Fichier | Fonction |
|---------|----------|
| `settings.py` | Configuration Django |
| `urls.py` | Routage URLs |
| `manage.py` | Gestion Django |
| `requirements.txt` | Dépendances |
| `.env` | Variables d'environnement |
| `celery.py` | Configuration Celery |
| `tasks.py` | Tâches Celery |

---

## 🔑 Variables Clés

```python
# Accès dans code
from django.conf import settings
settings.DEBUG
settings.DATABASE_NAME
settings.ALLOWED_HOSTS
```

---

## 💡 Tips & Tricks

### Rechercher dans le code
```bash
grep -r "TODO" .
grep -r "FIXME" .
grep -r "fonction_name" .
```

### Voir structure apps
```bash
python manage.py startapp app_name
ls -la app_name/
```

### Générer diagramme modèles
```bash
pip install django-extensions
python manage.py graph_models -a -o models.png
```

### Voir tous les tests
```bash
python manage.py test --list-labels
```

### Générer documentation
```bash
pip install sphinx
sphinx-quickstart docs
make html  # dans le dossier docs
```

---

## 🚨 Erreurs Courantes

### ModuleNotFoundError
```bash
# Solution: Vérifier import et chemin
python -c "import module_name"
pip list | grep module
```

### Database error
```bash
# Solution: Vérifier migrations
python manage.py migrate
python manage.py migrate --list
```

### Port 8000 déjà utilisé
```bash
# Solution: Utiliser autre port
python manage.py runserver 8001

# Linux: Tuer processus
lsof -i :8000
kill -9 PID
```

### Redis not running
```bash
# Solution: Démarrer Redis
redis-server

# ou
sudo systemctl start redis-server
```

---

## 📞 Ressources

- [Documentation Django](https://docs.djangoproject.com/)
- [Django REST Framework Docs](https://www.django-rest-framework.org/)
- [Celery Documentation](https://docs.celeryproject.io/)
- [PostgreSQL Docs](https://www.postgresql.org/docs/)
- [Redis Docs](https://redis.io/documentation)

---

## ✨ Raccourcis Utiles

```bash
# Alias Windows PowerShell - créer alias permanent
function drun { python manage.py runserver }
function dmigrate { python manage.py migrate }
function dmakeauto { python manage.py makemigrations }
function dshell { python manage.py shell }
function dcelery { celery -A immobilier_config worker -l info }
function dbeat { celery -A immobilier_config beat -l info }

# Ajouter à $PROFILE
New-Item -Path $PROFILE -ItemType File -Force
Add-Content $PROFILE 'function drun { python manage.py runserver }'
```

---

**Besoin d'aide?** Consultez la [documentation complète](GUIDE_DEMARRAGE.md)

**Bonne chance!** 🚀
