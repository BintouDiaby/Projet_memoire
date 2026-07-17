# Architecture de la Plateforme de Gestion Locative

## 🎯 Vue d'ensemble

Cette plateforme web de gestion locative est conçue selon une architecture **modulaire à microservices** utilisant:
- **Backend**: Django + Django REST Framework
- **Scheduler**: Celery Beat
- **Queue**: Celery + Redis
- **Base de données**: PostgreSQL (production), SQLite (développement)
- **Frontend**: React + API REST

---

## 📐 Architecture Logique

### Sepéaration des couches

```
┌─────────────────────────────────────────┐
│         Frontend (React/Vue)            │
│       (Client Web et Mobile)            │
└──────────────────┬──────────────────────┘
                   │  API REST
                   ▼
┌─────────────────────────────────────────┐
│        Django REST Framework            │
│         (API Views/Viewsets)            │
├─────────────────────────────────────────┤
│  Utilisateurs │ Biens │ Contrats │...   │
│     (Apps)    │       │          │      │
├─────────────────────────────────────────┤
│         Couche Métier (Models)          │
│    Gestion des données et logique       │
├─────────────────────────────────────────┤
│      Django ORM + PostgreSQL            │
│         (Persistance des données)       │
└─────────────────────────────────────────┘
                   │
                   ├──▶ Celery Beat (Scheduler)
                   │    └─▶ Tâches programmées
                   │
                   └──▶ Celery Worker (Queue)
                        ├─▶ Génération factures
                        ├─▶ Envoi notifications
                        └─▶ Mise à jour stats
```

---

## 🧩 Structure des Applications

### 1. **utilisateurs** - Authentification et Gestion Utilisateurs
```
utilisateurs/
├── models.py
│   ├── Utilisateur (AbstractUser)
│   ├── ProprietaireProfile
│   └── LocataireProfile
├── serializers.py
│   ├── UtilisateurSerializer
│   ├── UtilisateurCreationSerializer
│   ├── ProprietaireProfileSerializer
│   └── LocataireProfileSerializer
├── views.py
│   ├── UtilisateurViewSet (CRUD + actions custom)
│   ├── ProprietaireProfileViewSet
│   └── LocataireProfileViewSet
└── urls.py (API endpoints)
```

**Rôles**: Propriétaire, Locataire, Gestionnaire, Admin
**Fonctionnalités**:
- Authentification par session
- Gestion des profils
- Changement de mot de passe
- Vérification email/documents

---

### 2. **biens** - Gestion des Propriétés
```
biens/
├── models.py
│   ├── Bien (propriété avec détails)
│   ├── PhotoBien (galerie)
│   └── Visite (réservations de visite)
├── serializers.py
│   ├── BienListSerializer (allégé)
│   ├── BienDetailSerializer (complet)
│   ├── BienCreateUpdateSerializer (création)
│   ├── PhotoBienSerializer
│   └── VisiteSerializer
├── views.py
│   ├── BienViewSet (recherche, filtres)
│   ├── PhotoBienViewSet
│   └── VisiteViewSet
└── urls.py
```

**Fonctionnalités**:
- CRUD complet sur les biens
- Gestion des photos
- Filtrage avancé (prix, type, ville, chambres)
- Recherche par texte

---

### 3. **contrats** - Gestion des Contrats et Paiements
```
contrats/
├── models.py
│   ├── Contrat (avec dates et conditions)
│   ├── Paiement (suivi mensuel)
│   └── DocumentContrat (contrats signés, etc.)
├── serializers.py
│   ├── ContratListSerializer
│   ├── ContratDetailSerializer
│   ├── ContratCreateUpdateSerializer
│   └── PaiementSerializer
├── views.py
│   ├── ContratViewSet (activation, résiliation)
│   └── PaiementViewSet (enregistrement)
├── tasks.py (mis à jour via Celery)
└── urls.py
```

**Fonctionnalités**:
- Création de contrats avec auto-génération de numéro
- Suivi des paiements mensuels
- Détection des retards (mineur, majeur, impayé)
- Documents associés au contrat

---

### 4. **facturation** - Génération Automatique des Factures
```
facturation/
├── models.py
│   ├── Facture (mensuelle automatis.)
│   ├── Notification (email/SMS/push)
│   └── RappelPaiement (3 niveaux)
├── serializers.py
│   ├── FactureSerializer
│   ├── NotificationSerializer
│   └── RappelPaiementSerializer
├── views.py
│   ├── FactureViewSet (marquage payée, envoi)
│   ├── NotificationViewSet (lecture)
│   └── RappelPaiementViewSet
├── tasks.py
│   ├── generer_factures_mensuelles() [Celery Beat]
│   ├── envoyer_rappels_paiements() [Celery Beat]
│   └── creer_rappels_paiement()
└── urls.py
```

**Fonctionnalités** ⭐:
- **Génération automatique**: 1er du mois à 1h00
- **Rappels programmés**:
  - Premier: 2 jours après échéance
  - Deuxième: 7 jours après
  - Avis final: 15 jours après
- **Notifications multi-canaux**

---

### 5. **recherche** - Moteur de Recherche Avancé
```
recherche/
├── models.py
│   ├── RechercheSauvegardee (critères)
│   ├── BienFavori (avec notes)
│   └── HistoriqueRecherche (tracking)
├── serializers.py
│   ├── RechercheSauvegardeeSerializer
│   ├── BienFavoriSerializer
│   └── HistoriqueRechercheSerializer
├── views.py
│   ├── RechercheSauvegardeeViewSet
│   ├── BienFavoriViewSet
│   ├── HistoriqueRechercheViewSet
│   └── recherche_avancee() [API endpoint]
└── urls.py
```

**Filtres disponibles**:
- Prix (min/max)
- Localisation (villes)
- Type de bien
- Nombre de chambres
- Surface
- Équipements
- Animaux autorisés

---

### 6. **dashboard** - Tableaux de Bord et Statistiques
```
dashboard/
├── models.py
│   ├── StatistiquesProprietaire (KPIs)
│   ├── TableauBordLocataire (widgets)
│   ├── AlerteSysteme (notifications)
│   ├── LogActivite (audit)
│   ├── RapportMensuel (revenu, collecte)
│   └── ConfigurationDashboard (prefs)
├── serializers.py
│   ├── StatistiquesProprietaireSerializer
│   ├── TableauBordLocataireSerializer
│   ├── AlerteSystemeSerializer
│   ├── LogActiviteSerializer
│   ├── RapportMensuelSerializer
│   └── ConfigurationDashboardSerializer
├── views.py
│   ├── dashboard_proprietaire() [KPIs en temps réel]
│   ├── dashboard_locataire()
│   ├── rapport_mensuel() [Financier]
│   └── ViewSets (alertes, logs, config)
├── tasks.py
│   ├── mettre_a_jour_statistiques() [Chaque heure]
│   └── generer_rapports_mensuels() [1er du mois 9h]
└── urls.py
```

**KPIs Propriétaire**:
- Nombre de propriétés
- Contrats actifs
- Revenus mensuels et annuels
- Taux de collecte (%)
- Montants impayés

---

## 🔄 Flux de Facturation Automatique (Core Feature)

### Timeline mensuelle

```
01 du mois à 01h00
    │
    └─▶ generer_factures_mensuelles()
        ├─ Récupère contrats actifs
        ├─ Crée Paiement (mois courant)
        ├─ Crée Facture (montant = loyer + charges)
        ├─ Crée Notification (env. en attente)
        └─ Crée 3 RappelPaiement programmés
             ├─ J+2 (Premier rappel)
             ├─ J+7 (Deuxième rappel)
             └─ J+15 (Avis final)

Chaque jour à 08h00
    │
    └─▶ envoyer_rappels_paiements()
        ├─ Récupère RappelPaiement.date_prog ≤ aujourd'hui
        ├─ Crée Notification
        └─ Marque RappelPaiement.est_envoye = True

Toutes les 6 heures
    │
    └─▶ mettre_a_jour_statut_paiements()
        └─ Analyse retards et met à jour statuts
             ├─ EN_ATTENTE → RETARD_MINEUR (1j après échéance)
             ├─ RETARD_MINEUR → RETARD_MAJEUR (7j de retard)
             └─ RETARD_MAJEUR → IMPAYE (30j de retard)

01 du mois à 09h00
    │
    └─▶ generer_rapports_mensuels()
        ├─ Résume stats du mois précédent
        ├─ Calcul taux de collecte
        └─ Génère PDF (optionnel)
```

---

## 🔐 Sécurité et Permissions

### Authentification
- Session-based (Django)
- Token-based (optionnel: JWT pour mobile)

### Permissions par Rôle

```python
# Propriétaire
- Créer/modifier/supprimer ses biens
- Voir contrats de ses biens
- Voir factures/paiements
- Accéder à son dashboard
- Générer rapports

# Locataire
- Chercher des biens
- Réserver des visites
- Voir ses contrats
- Voir ses paiements
- Recevoir notifications

# Gestionnaire
- Gestion administrative
- Accès multi-propriétaires
- Création factures manuelles

# Admin
- Accès total aux données
- Configuration système
- Audit logs
```

---

## 📊 Modèle de Données

### Entités Principales

```sql
-- Utilisateurs
Utilisateur (id, username, email, role, ...)
├─ ProprietaireProfile (siret, certification, ...)
└─ LocataireProfile (revenu, budget_max, ...)

-- Propriétés
Bien (id, titre, prix_mensuel, ...)
└─ PhotoBien (id, bien_id, photo, ...)

-- Contrats
Contrat (id, bien_id, locataire_id, prix_mensuel, ...)
├─ Paiement (id, contrat_id, mois, statut, ...)
│  └─ Facture (id, paiement_id, montant_total, ...)
│     └─ Notification (id, facture_id, statut, ...)
└─ DocumentContrat (id, type_document, fichier, ...)

-- Recherche
RechercheSauvegardee (id, utilisateur_id, critères, ...)
BienFavori (id, utilisateur_id, bien_id, note, ...)
HistoriqueRecherche (id, utilisateur_id, requete, ...)

-- Dashboard
StatistiquesProprietaire (id, proprietaire_id, kpis, ...)
RapportMensuel (id, proprietaire_id, mois, montants, ...)
```

---

## 🚀 Déploiement

### Architecture Production

```
┌─────────────────────────────────────────────────────────┐
│                    Nginx (Reverse Proxy)                │
└──────────────────────────┬──────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
    Gunicorn          Django Static       Certbot
    (Workers)         (CSS/JS/Images)     (SSL/HTTPS)
        │
        └──▶ PostgreSQL
        └──▶ Redis
        └──▶ Celery Beat + Workers
```

### Variables d'environnement production
- `SECRET_KEY`: Clé secrète Django
- `DATABASE_URL`: Connexion PostgreSQL
- `CELERY_BROKER_URL`: URL Redis
- `EMAIL_BACKEND`: Configuration SMTP
- `ALLOWED_HOSTS`: Domaines autorisés

---

## 📈 Performances

### Optimisations implémentées
1. **Pagination**: 10 items/page par défaut
2. **Caching**: Rédis pour le cache des requêtes
3. **Indexing**: Index base de données sur statut, dates
4. **Asynchrone**: Celery pour non-blocking operations
5. **Lazy loading**: Chargement des relations à la demande

### Scalabilité
- Stateless Django (peuvent être multiplé avec load-balancer)
- Redis comme session store
- Celery dispersé sur plusieurs workers
- PostgreSQL avec réplication

---

## 🧪 Testing

Structure des tests:
```
tests/
├── test_utilisateurs.py
├── test_biens.py
├── test_contrats.py
├── test_facturation.py
├── test_recherche.py
└── test_dashboard.py
```

Lancer les tests:
```bash
python manage.py test
python manage.py test --coverage  # avec coverage
```

---

## 📝 Adressage de la problématique du mémoire

### ✅ Automatisation facturation
- ✓ Génération mensuelle automatique
- ✓ Suivi paiements en temps réel
- ✓ Rappels programmés (3 niveaux)
- ✓ Détection automatique impayés

### ✅ Gestion administrative
- ✓ Dashboards avec KPIs
- ✓ Rapports détaillés
- ✓ Traces d'audit complètes

### ✅ Moteur de recherche intelligent
- ✓ Recherche multi-critères
- ✓ Filtres avancés
- ✓ Historique et favoris

### ✅ Sécurité et accès
- ✓ Authentification robuste
- ✓ Permissions par rôle
- ✓ Validation des données
