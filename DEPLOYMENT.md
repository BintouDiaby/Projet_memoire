# 🚀 Guide de Déploiement Production

**Plateforme de Gestion Locative**  
**Version**: 1.0.0  
**Date**: Avril 2026

---

## 📋 Table des matières

1. [Prérequis](#prérequis)
2. [Préparation Serveur](#préparation-serveur)
3. [Configuration Production](#configuration-production)
4. [Déploiement](#déploiement)
5. [Post-déploiement](#post-déploiement)
6. [Monitoring](#monitoring)
7. [Dépannage](#dépannage)

---

## 🔧 Prérequis

### Serveur (minimum recommandé)
```
- CPU: 2+ cores
- RAM: 4GB
- Disque: 50GB
- OS: Ubuntu 20.04+ (recommandé) ou CentOS 8+
- Bande passante: 10Mbps
```

### Logiciels requis
```bash
# Ubuntu
sudo apt update
sudo apt install -y python3.10 python3.10-venv python3-pip git nginx postgresql postgresql-contrib redis-server supervisor

# CentOS
sudo yum install -y python3.10 python3.10-devel git nginx postgresql postgresql-server redis supervisor
```

---

## 🔨 Préparation Serveur

### 1. Créer utilisateur non-root
```bash
sudo useradd -m -s /bin/bash immobilier
sudo usermod -aG sudo immobilier
su - immobilier
```

### 2. Configurer PostgreSQL
```bash
# Créer base de données
sudo -u postgres psql
```

```sql
CREATE DATABASE immobilier_prod;
CREATE USER immobilier_user WITH PASSWORD 'your_secure_password';
ALTER ROLE immobilier_user SET client_encoding TO 'utf8';
ALTER ROLE immobilier_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE immobilier_user SET default_transaction_deferrable TO on;
ALTER ROLE immobilier_user SET default_transaction_deferrable TO on;
ALTER ROLE immobilier_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE immobilier_prod TO immobilier_user;
\q
```

### 3. Configurer Redis
```bash
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Vérifier
redis-cli ping  # Réponse: PONG
```

### 4. Cloner le projet
```bash
cd /home/immobilier
git clone https://github.com/your-repo/immobilier.git
cd immobilier
```

### 5. Créer environnement virtuel
```bash
python3.10 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## ⚙️ Configuration Production

### 1. Fichier `.env` Production
```bash
cp .env.example .env

# Éditer avec vos valeurs production
nano .env
```

```env
# SÉCURITÉ
DEBUG=False
SECRET_KEY=generate-random-secret-key-here-64-chars
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# BASE DE DONNÉES
DB_ENGINE=django.db.backends.postgresql
DB_NAME=immobilier_prod
DB_USER=immobilier_user
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432

# REDIS & CELERY
REDIS_HOST=localhost
REDIS_PORT=6379
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# EMAIL (SendGrid recommandé)
EMAIL_BACKEND=sendgrid_backend.SendgridBackend
SENDGRID_API_KEY=SG.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# FRONTEND
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
FRONTEND_URL=https://yourdomain.com

# SÉCURITÉ HTTPS
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
```

### 2. Générer SECRET_KEY
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 3. Migrations base de données
```bash
source venv/bin/activate
cd immobilier
python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic --noinput
```

### 4. Créer superuser
```bash
python manage.py createsuperuser
```

---

## 📦 Déploiement

### 1. Configurer Gunicorn

**Fichier**: `/home/immobilier/immobilier/gunicorn_config.py`
```python
import multiprocessing

bind = "127.0.0.1:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 50
daemon = False
```

### 2. Configurer Systemd - Gunicorn

**Fichier**: `/etc/systemd/system/immobilier.service`
```ini
[Unit]
Description=Immobilier Gunicorn Service
After=network.target

[Service]
Type=notify
User=immobilier
Group=www-data
WorkingDirectory=/home/immobilier/immobilier
ExecStart=/home/immobilier/immobilier/venv/bin/gunicorn \
    -c gunicorn_config.py \
    immobilier_config.wsgi:application
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3. Configurer Systemd - Celery Worker

**Fichier**: `/etc/systemd/system/immobilier-celery.service`
```ini
[Unit]
Description=Immobilier Celery Worker
After=network.target

[Service]
Type=forking
User=immobilier
Group=www-data
WorkingDirectory=/home/immobilier/immobilier
ExecStart=/home/immobilier/immobilier/venv/bin/celery -A immobilier_config \
    worker -l info --logfile=/home/immobilier/immobilier/logs/celery.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 4. Configurer Systemd - Celery Beat

**Fichier**: `/etc/systemd/system/immobilier-beat.service`
```ini
[Unit]
Description=Immobilier Celery Beat Scheduler
After=network.target

[Service]
Type=simple
User=immobilier
Group=www-data
WorkingDirectory=/home/immobilier/immobilier
ExecStart=/home/immobilier/immobilier/venv/bin/celery -A immobilier_config \
    beat -l info --logfile=/home/immobilier/immobilier/logs/beat.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 5. Activer services
```bash
sudo systemctl daemon-reload
sudo systemctl enable immobilier
sudo systemctl enable immobilier-celery
sudo systemctl enable immobilier-beat
sudo systemctl start immobilier
sudo systemctl start immobilier-celery
sudo systemctl start immobilier-beat
```

### 6. Configurer Nginx

**Fichier**: `/etc/nginx/sites-available/immobilier`
```nginx
upstream immobilier {
    server 127.0.0.1:8000;
}

# Redirection HTTP vers HTTPS
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

# Configuration HTTPS
server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # Certificats SSL (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Configuration SSL sécurisée
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    client_max_body_size 10M;

    # Logs
    access_log /home/immobilier/immobilier/logs/nginx_access.log;
    error_log /home/immobilier/immobilier/logs/nginx_error.log;

    # Static files
    location /static/ {
        alias /home/immobilier/immobilier/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /home/immobilier/immobilier/media/;
        expires 7d;
    }

    # API
    location / {
        proxy_pass http://immobilier;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_buffering off;
        proxy_request_buffering off;
    }
}
```

### 7. Activer Nginx
```bash
sudo ln -s /etc/nginx/sites-available/immobilier /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx
```

### 8. Configurer SSL Let's Encrypt
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot certonly --nginx -d yourdomain.com -d www.yourdomain.com
sudo certbot renew --dry-run  # Test auto-renouvellement
```

---

## ✅ Post-déploiement

### 1. Vérifier services
```bash
sudo systemctl status immobilier
sudo systemctl status immobilier-celery
sudo systemctl status immobilier-beat
sudo systemctl status nginx
```

### 2. Vérifier logs
```bash
tail -f /home/immobilier/immobilier/logs/django.log
tail -f /home/immobilier/immobilier/logs/celery.log
tail -f /home/immobilier/immobilier/logs/beat.log
```

### 3. Tester l'API
```bash
curl https://yourdomain.com/api/utilisateurs/utilisateurs/
curl https://yourdomain.com/api/biens/biens/
curl https://yourdomain.com/admin/
```

### 4. Configurer cron backup
```bash
crontab -e
```

```cron
# Backup quotidien (3h du matin)
0 3 * * * pg_dump immobilier_prod | gzip > /backups/db_$(date +\%Y\%m\%d).sql.gz
```

---

## 📊 Monitoring

### 1. Health Check
```bash
# Créer endpoint de santé (optionnel)
curl https://yourdomain.com/health/
```

### 2. Metrics (Prometheus)
```bash
pip install django-prometheus
# Configurer dans settings.py
```

### 3. Logging centralisé
```bash
# Installer ELK ou Sentry
pip install sentry-sdk
# Configurer SENTRY_DSN dans .env
```

---

## 🔧 Dépannage

### Problem: Celery tasks ne s'exécutent pas

```bash
# Vérifier que Celery Beat tourne
ps aux | grep celery

# Vérifier Redis
redis-cli ping

# Redémarrer services
sudo systemctl restart immobilier-celery
sudo systemctl restart immobilier-beat

# Vérifier logs
tail -f /home/immobilier/immobilier/logs/beat.log
```

### Problem: Emails ne s'envoient pas

```bash
# Vérifier config SMTP
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Test message', 'from@example.com', ['to@example.com'])

# Vérifier SENDGRID_API_KEY
echo $SENDGRID_API_KEY
```

### Problem: Erreurs 500

```bash
# Vérifier logs Django
tail -f /home/immobilier/immobilier/logs/django.log

# Vérifier config DATABASE
python manage.py dbshell

# Vérifier permissions fichiers
chmod 755 /home/immobilier/immobilier
chmod 755 /home/immobilier/immobilier/logs
```

### Problem: Base de données non accessible

```bash
# Vérifier PostgreSQL
sudo systemctl status postgresql

# Vérifier connexion
psql -U immobilier_user -d immobilier_prod -h localhost -W

# Vérifier variables d'environnement
source /home/immobilier/immobilier/.env
echo $DB_HOST $DB_NAME
```

---

## 📈 Performance Optimization

### 1. Caching
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}
```

### 2. Database Optimization
```bash
# Analyser requêtes lentes
django-extensions + debug_toolbar
```

### 3. Static Files CDN
```bash
# Uploader staticfiles vers S3/CloudFront
```

---

## 🔒 Sécurité Production

### Checklist
- [x] DEBUG=False
- [x] SECRET_KEY aléatoire
- [x] ALLOWED_HOSTS configuré
- [x] HTTPS/SSL activé
- [x] CORS restreint
- [x] Authentification POST/token
- [x] Rate limiting activé
- [x] Firewall configuré
- [x] Backups quotidiens
- [x] Monitoring activé

---

## 🎉 Conclusion

Votre plateforme est maintenant **en production**! 

Pour le monitoring continu:
```bash
# Dashboard Celery
celery -A immobilier_config events

# Statistiques PostgreSQL
SELECT * FROM pg_stat_statements;
```

**Bon déploiement!** 🚀
