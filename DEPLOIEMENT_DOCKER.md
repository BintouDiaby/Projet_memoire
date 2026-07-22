# Déploiement ImmoGérer avec Docker (VM Google Cloud)

Guide pas-à-pas pour déployer l'API sur la VM `34.77.243.188` via Docker Hub.

**Principe :** l'image Docker contient **le code uniquement**. Les données
(PostgreSQL, photos) vivent dans des **volumes** sur la VM → elles survivent à
chaque mise à jour de l'image. **Aucune donnée, aucun secret dans l'image.**

```
Ton Mac                          Docker Hub (privé)            VM Google Cloud
───────                          ─────────────────            ───────────────
docker build   ──push──▶  toncompte/immogerer:latest  ──pull──▶  docker compose up
(code)                          (code)                         + volumes = DONNÉES
```

---

## A. Une seule fois — sur ton Mac : construire et pousser l'image

1. **Se connecter à Docker Hub**
   ```bash
   docker login
   ```

2. **Créer le dépôt privé** sur https://hub.docker.com → *Create Repository* →
   nom `immogerer`, visibilité **Private**.

3. **Construire et pousser l'image** (remplace `toncompte` par ton identifiant Docker Hub) :
   ```bash
   cd /Users/fadel/Projet_memoire-1
   docker build -t toncompte/immogerer:latest .
   docker push toncompte/immogerer:latest
   ```

> À chaque nouvelle version du code : refais `git push`, puis `docker build` +
> `docker push`, puis sur la VM `docker compose pull && docker compose up -d`.

---

## B. Une seule fois — sur la VM : installer Docker

Connecté en SSH sur la VM :

```bash
# Docker + plugin compose
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# se déconnecter/reconnecter pour appliquer le groupe docker
exit
```
Reconnecte-toi en SSH, puis vérifie :
```bash
docker --version && docker compose version
```

---

## C. Sur la VM : récupérer la config et lancer

Le code vient de l'image, mais la VM a besoin des fichiers de **config**
(`docker-compose.yml`, `docker/nginx.conf`, `.env`).

1. **Cloner le dépôt** (pour la config) :
   ```bash
   cd ~
   git clone https://github.com/BintouDiaby/Projet_memoire.git
   cd Projet_memoire
   ```

2. **Créer le `.env`** à partir du modèle et le remplir :
   ```bash
   cp .env.docker.example .env
   nano .env
   ```
   À renseigner impérativement :
   - `IMAGE_NAME=toncompte/immogerer`
   - `SECRET_KEY=` → générer une clé unique :
     ```bash
     docker run --rm toncompte/immogerer:latest \
       python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
     ```
   - `DEBUG=False`
   - `ALLOWED_HOSTS=34.77.243.188,127.0.0.1,localhost`
   - `DB_PASSWORD=` → un mot de passe solide

3. **Se connecter à Docker Hub** (dépôt privé) et **démarrer** :
   ```bash
   docker login
   docker compose pull      # récupère ton image + postgres/redis/nginx
   docker compose up -d      # démarre tout
   ```

4. **Vérifier** :
   ```bash
   docker compose ps          # tous les services "Up"
   docker compose logs -f web # voir migrate + gunicorn démarrer
   ```
   L'API répond alors sur `http://34.77.243.188/`.

---

## D. Une seule fois — charger les données de démo

⚠️ À faire **une seule fois** (recharger écraserait les données créées depuis).

```bash
docker compose run --rm web python manage.py loaddata data_export.json
```

Si erreur de type « duplicate key » sur les contenttypes, recharger en excluant :
```bash
docker compose run --rm web python manage.py loaddata data_export.json --exclude contenttypes --exclude auth.permission
```

Créer (ou recréer) un compte admin si besoin :
```bash
docker compose run --rm web python manage.py createsuperuser
```

---

## D bis. Une seule fois — copier les photos dans le volume média

⚠️ **Sans cette étape, les images des biens ne s'affichent pas** (base de données OK,
mais fichiers absents). Les photos sont dans le dossier `media/` (ramené par le
`git clone`), mais l'image Docker ne les contient pas et le volume démarre vide.
On verse donc les fichiers dans le volume (ils y persistent ensuite) :

```bash
docker compose cp ./media/. web:/app/media/
```

Vérifier que les fichiers sont bien dans le volume :
```bash
docker compose exec web ls /app/media/biens/principales | head
```

---

## E. Vérifier depuis l'extérieur / l'app mobile

- Swagger : `http://34.77.243.188/api/docs/`
- Login JWT (mobile) :
  ```bash
  curl -X POST http://34.77.243.188/api/token/ \
    -H "Content-Type: application/json" \
    -d '{"username":"<user>","password":"<mdp>"}'
  ```
  → renvoie `{"access": "...", "refresh": "..."}`.

Dans l'app Flutter, mettre `baseUrl = "http://34.77.243.188"`.

---

## F. Pare-feu Google Cloud

Le port **80** doit être ouvert (déjà fait d'après ton install). Pour vérifier,
dans la console GCP → *VPC network* → *Firewall*, une règle `default-allow-http`
doit autoriser `tcp:80` sur la VM.

---

## G. Domaine + HTTPS (pour la soutenance — optionnel mais recommandé)

Avec un nom de domaine pointant vers `34.77.243.188`, on ajoute un conteneur
`certbot` (Let's Encrypt) et on écoute en 443. À faire dans un second temps —
demande-moi la version HTTPS du `docker-compose.yml` quand tu auras le domaine.
Il faudra alors ajouter dans le `.env` :
```
ALLOWED_HOSTS=mon-domaine.com,34.77.243.188
CSRF_TRUSTED_ORIGINS=https://mon-domaine.com
```

---

## Commandes utiles

| Action | Commande |
|---|---|
| Voir l'état | `docker compose ps` |
| Logs d'un service | `docker compose logs -f web` (ou `celery_worker`, `nginx`…) |
| Mettre à jour le code | `docker compose pull && docker compose up -d` |
| Redémarrer | `docker compose restart` |
| Arrêter (garde les données) | `docker compose down` |
| ⚠️ Tout supprimer Y COMPRIS LES DONNÉES | `docker compose down -v` |
| Sauvegarder la base | `docker compose exec db pg_dump -U immogerer_user immogerer > backup.sql` |

> **`docker compose down -v` efface les volumes = perte de la base.** Ne jamais
> l'utiliser en production. `docker compose down` (sans `-v`) est sûr.
