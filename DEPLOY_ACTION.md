# GitHub Actions: Build & Deploy — instructions

Ce fichier explique comment configurer les secrets GitHub et lancer le déploiement automatique.

Required repository secrets (Repository Settings → Secrets → Actions):

- `SSH_PRIVATE_KEY` : clé privée SSH utilisée pour se connecter au VPS (utilisateur déployeur).
- `DEPLOY_HOST` : adresse IP ou hostname du VPS.
- `DEPLOY_USER` : utilisateur SSH sur le VPS (ex: `ubuntu`, `immobilier`).
- `SSH_PORT` : port SSH (par défaut `22`).
- `DEPLOY_PATH` : chemin sur le VPS où se situe le `docker-compose.yml` (ex: `/home/immobilier/immobilier`).

Notes de configuration sur le VPS:

1. Préparer le dossier de déploiement et le `docker-compose.yml` (ex: copier le `docker-compose.yml` de ce repo):

```sh
mkdir -p /home/immobilier/immobilier
cd /home/immobilier/immobilier
# Copier le docker-compose.yml du repo ou le cloner depuis GitHub
```

2. Ajouter l'utilisateur SSH déployeur (ou utiliser un existant) et ajouter la clé publique correspondante dans `~/.ssh/authorized_keys`.

3. S'assurer que Docker et Docker Compose sont installés sur le VPS.

4. Créer un fichier `.env` en production (copier depuis `.env.example` et configurer les variables). IMPORTANT: ne pas committer `.env`.

5. Si vous utilisez Traefik global, le `docker-compose.yml` présent dans ce repo se connecte au réseau Docker `traefik` (external). Assurez-vous que ce réseau existe et que Traefik écoute ce réseau.

6. Pour forcer un déploiement manuel (si nécessaire) :

```sh
# Sur la machine locale ou sur le VPS via SSH
docker pull ghcr.io/<OWNER>/projet_memoire:latest
cd /path/to/deploy
docker-compose up -d --no-deps --build bintou
```

7. Secrets GitHub: créez-les dans `Settings -> Secrets and variables -> Actions`.

8. Pusher sur la branche `main` (ou `master`) déclenchera le workflow.

Questions fréquentes
- Si vous préférez utiliser Docker Hub au lieu de GHCR, mettez à jour le workflow pour se logger sur Docker Hub et pousser l'image.
- Si votre composition remote doit référencer une image taggée par SHA, adaptez le `tags:` dans le workflow pour inclure `${{ github.sha }}`.
