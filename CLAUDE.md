# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

French-language rental property management platform ("Plateforme de Gestion Locative") built as a Django + DRF monolith. Domain language (models, fields, URLs, statuses) is in French — keep it that way when adding new code so it stays consistent (e.g., `Contrat.Statut.EN_COURS`, `Paiement.Statut.RETARD_MINEUR`, `prix_mensuel`, `date_limite`).

## Common commands

All commands assume the venv is activated (`.\venv\Scripts\Activate.ps1` on PowerShell). The Django settings module is `immobilier_config.settings`.

```powershell
# Dev server
python manage.py runserver

# Migrations
python manage.py makemigrations
python manage.py migrate

# Superuser (scripted shortcut — creates admin/adminpass123)
python scripts/create_superuser.py
# or interactive
python manage.py createsuperuser

# Tests (Django test runner; per-app tests.py files exist but most are empty)
python manage.py test                       # all apps
python manage.py test facturation           # single app
python manage.py test facturation.tests.TestClass.test_method  # single test

# Celery (requires Redis running on localhost:6379)
celery -A immobilier_config worker -l info
celery -A immobilier_config beat -l info
```

`fix_migrations.py` at the repo root is broken (references the wrong settings module `config.settings`). Don't run it without fixing the path first.

## Architecture

### Django apps (each is a bounded domain)

- **utilisateurs** — Custom user model `Utilisateur` (extends `AbstractUser`) with a `role` enum: `proprietaire`, `gestionnaire`, `locataire`, `admin`. `AUTH_USER_MODEL = 'utilisateurs.Utilisateur'` is set in settings, so any new user FK must point to this model (not `auth.User`). Also defines `Company` (multi-tenant-ish entity with a JSON `types` list like `["location", "vente", "construction"]`), `ProprietaireProfile`, `LocataireProfile`.
- **biens** — Properties (`Bien`), photos, visits.
- **contrats** — Rental contracts and per-month `Paiement` rows. `Paiement` has a `unique_together = ['contrat', 'mois']` constraint and a `mettre_a_jour_statut()` method that transitions `EN_ATTENTE → RETARD_MINEUR → RETARD_MAJEUR → IMPAYE` based on days past `date_limite`.
- **facturation** — `Facture`, `Notification`, `RappelPaiement`. This is the core automated workflow.
- **recherche** — Saved searches, favorites, search history.
- **dashboard** — Per-role KPI views, monthly reports, audit logs.

### Two URL surfaces per app

Each domain app exposes both:
- A **REST API** under `/api/<app>/` (DRF `SimpleRouter` in `<app>/urls.py`)
- A **server-rendered UI** under `/<app>/` (Django templates via `<app>/urls_ui.py`)

When changing a model, both surfaces likely need updates. The root `home` view (`immobilier_config/urls.py`) renders a dashboard with live KPIs computed from `Utilisateur`, `Bien`, `Contrat`, `Paiement` — and redirects to onboarding when `request.user.company` or `request.user.company.types` is unset.

### Celery scheduled tasks (defined in `immobilier_config/celery.py`)

These three crons are the system's core automation — changing the contrat/paiement/facture schema means revisiting them:

| Task | Schedule | What it does |
| --- | --- | --- |
| `facturation.tasks.generer_factures_mensuelles` | 1st of month, 01:00 | For each active `Contrat`, creates a `Paiement` for the current month, a `Facture`, a `Notification`, and three `RappelPaiement` rows (J+2, J+7, J+15 from `date_limite`) |
| `facturation.tasks.envoyer_rappels_paiements` | Daily 08:00 | Sends any `RappelPaiement` whose `date_programmee <= now` and `est_envoye=False` |
| `contrats.tasks.mettre_a_jour_statut_paiements` | Every 6 hours | Recomputes payment overdue status |

**Known footgun in `facturation/tasks.py`**: the file defines `envoyer_rappels_paiements` and `creer_rappels_paiement` *twice* (the first definition has a duplicated/garbled `try/except` block leaking into module scope). Python's last-definition-wins, so the second versions are what Celery actually runs — but edits to the first copies are silently dead code. If you're touching this file, fix the duplication rather than working around it.

### REST defaults (`immobilier_config/settings.py`)

- Session auth only (no Token/JWT configured). Login at `/api-auth/login/`.
- `IsAuthenticated` is the global default permission — new viewsets are locked down unless overridden.
- Global pagination: `PageNumberPagination`, page size 10.
- Filter backends: `DjangoFilterBackend`, `SearchFilter`, `OrderingFilter`.

### Database

SQLite (`db.sqlite3`) is committed to the repo and used for both dev and currently anything else. `.env.example` describes a Postgres path for production but `settings.py` hardcodes SQLite — there is no `.env`-driven `DATABASES` switching wired up. Don't assume env vars take effect without checking.

### Settings caveats

`settings.py` has hardcoded values that the `.env.example` *claims* are configurable but aren't actually read: `SECRET_KEY`, `DEBUG=True`, `ALLOWED_HOSTS=[]`, `TIME_ZONE='UTC'` (not `Africa/Abidjan`), `LANGUAGE_CODE='en-us'` (not `fr-FR`), email backend, Celery URLs. Configuring via `.env` requires actually wiring `python-decouple` (already in `requirements.txt`) into `settings.py` first.

## Reference docs in the repo

The repo contains many overlapping markdown files (`ARCHITECTURE.md`, `GUIDE_DEMARRAGE.md`, `QUICK_REFERENCE.md`, `DEPLOYMENT.md`, `PROJECT_STATUS.md`, `SUMMARY.md`, `WELCOME.md`, `START_HERE.md`, `INDEX.md`, `FILE_MANIFEST.md`, `DONE.md`, `COMPLETION_REPORT.md`). `ARCHITECTURE.md` is the most useful for domain/flow context; the rest are largely status reports and duplicate each other. They were authored before the code stabilized — when they disagree with the code, trust the code.
