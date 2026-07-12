# ImmoGérer — REST API Reference (for Flutter client)

This document covers **only the DRF REST API surface** (`/api/...`), not the server-rendered Django template UI (`/biens/`, `/contrats/`, `/dashboard/...`, `/accounts/login/`, etc.). Base URL in dev: `http://127.0.0.1:8000`. All API routes are mounted under `/api/<app>/` (see table below); each app also registers a `SimpleRouter`, so most resources live at `/api/<app>/<resource>/`.

**Critical auth caveat: there is no token/JWT auth.** `REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']` is `SessionAuthentication` only, and `DEFAULT_PERMISSION_CLASSES` is `IsAuthenticated` globally (overridden per-viewset in a few places — noted below). This means the Flutter app must behave like a browser: obtain a `sessionid` cookie by logging in, persist a cookie jar across requests, and attach a CSRF token header on every unsafe (POST/PUT/PATCH/DELETE) request.

**Recommendation:** use `dio` with `dio_cookie_manager` (backed by `cookie_jar` / `PersistCookieJar`) so cookies survive across app restarts, and add an interceptor that reads the `csrftoken` cookie and sets it as the `X-CSRFToken` request header on unsafe methods.

Other relevant defaults:
- Pagination: `PageNumberPagination`, page size **10** (`?page=N`).
- Filter backends: `DjangoFilterBackend` (exact-match `filterset_fields`), `SearchFilter` (`?search=`), `OrderingFilter` (`?ordering=field` / `?ordering=-field`).
- `CORS_ALLOW_CREDENTIALS = True`, `CORS_ALLOWED_ORIGINS` only lists `localhost:3000/8000` and `127.0.0.1:3000/8000` — irrelevant for native Flutter (no browser CORS), but relevant if you ever run Flutter Web against this backend and will need the dev/prod host added.

---

## 1. Auth

There is **no dedicated JSON login endpoint**. Two things named "login" exist and only one is usable by an API client:

| URL | Purpose | Usable by Flutter? |
| --- | --- | --- |
| `POST /accounts/login/` | Server-rendered HTML login form (`utilisateurs.views.login_view`), sets session cookie, redirects | No — returns HTML, not JSON, tied to Django `messages`/redirect flow |
| `POST /api-auth/login/` | DRF browsable-API login (`rest_framework.urls`), standard Django `AuthenticationForm` | **Yes, this is the one to use** — but it's still an HTML form endpoint, not JSON |

### Login flow for Flutter
1. `GET /api-auth/login/` — reads the `csrftoken` cookie from the `Set-Cookie` header (DRF renders a login form here; the cookie is what matters, not the HTML body).
2. `POST /api-auth/login/` with `Content-Type: application/x-www-form-urlencoded`, body `username=...&password=...&csrfmiddlewaretoken=<value of csrftoken cookie>`, and header `X-CSRFToken: <csrftoken cookie value>` (or rely on the `csrfmiddlewaretoken` form field — DRF/Django accept either for form posts). On success, Django responds with a redirect (302) and a new `Set-Cookie: sessionid=...`. Configure your HTTP client to **not** follow the redirect blindly if you want to detect success from the 302 vs. a 200 (form re-rendered with errors).
3. From then on, every request must send the `sessionid` cookie (cookie jar handles this automatically) and, for POST/PUT/PATCH/DELETE, the `X-CSRFToken` header set to the current `csrftoken` cookie value.
4. **Logout**: `GET/POST /accounts/logout/` (`utilisateurs.views.logout_view`) — clears the Django session server-side. There is no `/api-auth/logout/` distinct behavior worth using instead.
5. There is no `/api/utilisateurs/me/` equivalent for "am I logged in" other than `GET /api/utilisateurs/utilisateurs/me/` (see below), which requires an existing valid session — 401/403 if not authenticated.

### CSRF details
- Django's CSRF cookie is `csrftoken` (readable by JS/mobile HTTP clients — not `HttpOnly`).
- Send it back as the `X-CSRFToken` header on every unsafe request (`SessionAuthentication` enforces Django's CSRF check because it's cookie/session based, unlike token auth).
- The cookie is refreshed by hitting almost any GET endpoint that renders/uses `django.middleware.csrf`; safest is to hit `GET /api-auth/login/` (or any page) once at app startup before the first POST.

### Registration
No API create-user flow is documented as "the" signup — `POST /api/utilisateurs/utilisateurs/` (see Utilisateurs section) is technically open (`AllowAny` on `create`) and works as a JSON registration endpoint, but it does **not** log the user in (no session is created) and does not create a `Company`. The real signup UX (`/accounts/signup/`, `/accounts/signup/company/`) is server-rendered HTML only and does more (creates `Company`, sends OTP email, calls `login()`). A Flutter client wanting full signup parity would need `POST /api/utilisateurs/utilisateurs/` followed by a separate login call, and has no way to create/attach a `Company` via API (see Gaps).

---

## 2. App → URL mount table

| App | Mount | Router prefix |
| --- | --- | --- |
| Utilisateurs | `/api/utilisateurs/` | `utilisateurs/`, `proprietaires/`, `locataires/` |
| Biens | `/api/biens/` | `biens/`, `photos/`, `visites/` |
| Contrats | `/api/contrats/` | `contrats/`, `paiements/` |
| Facturation | `/api/facturation/` | `factures/`, `notifications/`, `rappels/` |
| Recherche | `/api/recherche/` | `recherches/`, `favoris/`, `historique/` + 2 extra paths |
| Dashboard | `/api/dashboard/` | `alertes/`, `logs/`, `config/` + 3 extra paths |

All routers are DRF `SimpleRouter` — standard REST verbs apply: `GET list`, `POST create`, `GET {id}/ retrieve`, `PUT/PATCH {id}/`, `DELETE {id}/`, plus custom `@action` routes noted per app.

---

## 3. Utilisateurs (`/api/utilisateurs/`)

`Utilisateur.Role` choices: `proprietaire`, `gestionnaire`, `locataire`, `admin`.

### `/utilisateurs/` — `UtilisateurViewSet`
- Permission: `IsAuthenticated` for all actions **except `create`, which is `AllowAny`**.
- `queryset = Utilisateur.objects.all()` — **no scoping**: any authenticated user can `GET /api/utilisateurs/utilisateurs/{id}/` for any other user's public profile fields. No `filterset_fields`/`search_fields` configured.
- Serializer: `UtilisateurSerializer` for list/retrieve/update; `UtilisateurCreationSerializer` for `create`.

| Endpoint | Method | Notes |
| --- | --- | --- |
| `/utilisateurs/` | GET | List all users (paginated) |
| `/utilisateurs/` | POST | Create user. Fields: `username, email, password, password2, first_name, last_name, role, telephone, adresse, ville, code_postal`. `AllowAny`. Auto-creates `ProprietaireProfile`/`LocataireProfile` based on `role`. Does **not** log in or create a `Company`. |
| `/utilisateurs/{id}/` | GET/PUT/PATCH/DELETE | Standard CRUD, `IsAuthenticated` |
| `/utilisateurs/me/` | GET | Current user's own profile (uses `UtilisateurSerializer`) |
| `/utilisateurs/dashboard_preferences/` | GET/POST | GET returns `{dashboard_preferences}`; POST body `{"dashboard_preferences": {...}}` (arbitrary JSON blob) |
| `/utilisateurs/change_password/` | POST | Body `{old_password, new_password}` |
| `/utilisateurs/{id}/proprietaire_profile/` | GET | 400 if target user isn't role `proprietaire` |
| `/utilisateurs/{id}/locataire_profile/` | GET | 400 if target user isn't role `locataire` |

Response fields (`UtilisateurSerializer`): `id, username, email, first_name, last_name, role, role_display, telephone, adresse, ville, code_postal, photo_profil, bio, email_verifie, documents_verifies, dashboard_preferences, date_creation, date_modification`. Note: **no `company` field exposed** — the API never returns the user's `Company` (name, types, logo, etc.) anywhere.

### `/proprietaires/` — `ProprietaireProfileViewSet`
`IsAuthenticated`, no scoping (`ProprietaireProfile.objects.all()`), full CRUD. Fields: `id, utilisateur (nested read-only), utilisateur_id (write, must be role=proprietaire), numero_siret_siren, nom_entreprise, numero_licence, iban, nombre_proprietes, experience_annees, certification`.

### `/locataires/` — `LocataireProfileViewSet`
`IsAuthenticated`, no scoping, full CRUD. Fields: `id, utilisateur, utilisateur_id (must be role=locataire), numero_identite, revenu_mensuel, numero_reference_bancaire, avis_impot, preuve_emploi, garant_contact, localisation_preferee, budget_max_mensuel`.

---

## 4. Biens (`/api/biens/`)

`Bien.TypeBien` choices: `appartement, maison, maison_basse, studio, t1, t2, t3, t4, t5plus, duplex, immeuble, residence, terrain, bureau, magasin, boutique, local_commercial, entrepot`.
`Bien.Statut` choices: `disponible, loue, maintenance, archive`.
`Bien.TransactionType` choices: `location, vente, both`.

### `/biens/` — `BienViewSet`
- **Permission: `AllowAny` for all actions**, including create/update/delete — this is a real gap (see Gaps section): an anonymous request that hits `POST /api/biens/biens/` will 500 (tries `serializer.save(proprietaire=request.user)` with an `AnonymousUser`) rather than being rejected cleanly.
- `filterset_fields`: `statut, type_bien, transaction_type, ville, prix_mensuel`. `search_fields`: `titre, description, adresse, ville`. `ordering_fields`: `prix_mensuel, date_creation, date_publication`.
- `get_queryset`: returns all biens by default; if `?mes_biens=1` **and** the requester is authenticated with `role=proprietaire`, filters to `proprietaire=request.user`. (Not enforced for `gestionnaire`.)
- Serializer varies by action: `BienListSerializer` (list), `BienDetailSerializer` (retrieve), `BienCreateUpdateSerializer` (create/update/partial_update).
- `perform_create` force-sets `proprietaire = request.user`.

| Endpoint | Method | Notes |
| --- | --- | --- |
| `/biens/` | GET | List, paginated. Query params: `statut, type_bien, transaction_type, ville, prix_mensuel, search, ordering, mes_biens` |
| `/biens/` | POST | Create (see `BienCreateUpdateSerializer` fields below). No auth actually enforced (`AllowAny`) |
| `/biens/{id}/` | GET | `BienDetailSerializer` |
| `/biens/{id}/` | PUT/PATCH/DELETE | No ownership check in the viewset itself |
| `/biens/{id}/marquer_disponible/` | POST | Sets `statut=disponible` |
| `/biens/{id}/marquer_loue/` | POST | Sets `statut=loue` |

`BienListSerializer` fields: `id, titre, description, type_bien, type_bien_display, transaction_type, transaction_type_display, statut, statut_display, adresse, ville, code_postal, surface_m2, nombre_chambres, nombre_salles_bain, prix_mensuel, photo_principale, proprietaire (nested), date_publication`.

`BienDetailSerializer` adds: `pays, latitude, longitude, nombre_etages, prix_depot_garantie, charges_incluses, equipements, animaux_autorises, fumeurs_acceptes, photos (nested list), date_creation`. Note: **`prix_vente`, `quartier`, `commune`, `region` are model fields but are NOT exposed by either serializer** — Flutter cannot read/write sale price or commune/quartier via the API even though the UI (`biens/publier_bien.html`) uses them.

`BienCreateUpdateSerializer` (POST/PUT body) fields: `titre, description, type_bien, statut, adresse, transaction_type, ville, code_postal, pays, latitude, longitude, surface_m2, nombre_chambres, nombre_salles_bain, nombre_etages, prix_mensuel, prix_depot_garantie, charges_incluses, equipements, animaux_autorises, fumeurs_acceptes, photo_principale`. (Again, no `prix_vente`/`commune`/`quartier`.)

### `/photos/` — `PhotoBienViewSet`
`IsAuthenticated`, full CRUD, no filtering. Fields: `id, bien, photo, description, ordre, date_ajout`. `perform_create` checks `bien.proprietaire == request.user` but the failure path returns a `Response` from inside `perform_create` **without raising** — DRF will still attempt to proceed with the (unauthorized) save in that code path; treat this endpoint's ownership check as unreliable.

### `/visites/` — `VisiteViewSet`
`IsAuthenticated`. `filterset_fields`: `bien, interet`. `ordering_fields`: `date_visite, date_reservation`.
- `get_queryset`: `role=locataire` → own visits (`locataire=user`); `role=proprietaire` → visits on own biens (`bien__proprietaire=user`); anything else (including `gestionnaire`/`admin`) → **all visits**.
- `perform_create` sets `locataire=request.user`.
- Fields: `id, bien (nested BienListSerializer), locataire (nested), date_visite, notes, interet, date_reservation`.
- `Visite.Statut` choices (`en_attente, confirmee, refusee, annulee`) exist on the model but are **not exposed** in `VisiteSerializer` — Flutter can create/read visits but cannot see or change their status through this endpoint (status changes happen only through UI views like `annuler_visite`, which are not API routes).

`Reservation` model exists (bien reservations, `Statut: en_attente, confirmee, annulee`) but has **no ViewSet/serializer at all** — not reachable via API.

---

## 5. Contrats (`/api/contrats/`)

`Contrat.Statut` choices: `brouillon, en_cours, termine, suspendu, resilie`.
`Contrat.StatutCaution` choices: `non_traitee, retenue, remboursee`.
`Paiement.Statut` choices: `en_attente, recu, retard_mineur, retard_majeur, impaye`.

### `/contrats/` — `ContratViewSet`
`IsAuthenticated`. `filterset_fields`: `statut, bien, locataire, proprietaire`. `ordering_fields`: `date_debut, date_creation`.
- `get_queryset`: `role=proprietaire` → `proprietaire=user`; `role=locataire` → `locataire=user`; else (gestionnaire/admin) → all contracts.
- Serializer: `ContratListSerializer` (list), `ContratDetailSerializer` (retrieve), `ContratCreateUpdateSerializer` (create/update).
- `perform_create` auto-generates `numero_contrat` if not supplied.

| Endpoint | Method | Notes |
| --- | --- | --- |
| `/contrats/` | GET/POST | |
| `/contrats/{id}/` | GET/PUT/PATCH/DELETE | |
| `/contrats/{id}/activer/` | POST | Only from `brouillon` → `en_cours`, sets `date_signature=now()`. 400 otherwise |
| `/contrats/{id}/resilier/` | POST | → `resilie` |
| `/contrats/{id}/paiements/` | GET | All `Paiement`s for this contract |
| `/contrats/{id}/statistiques/` | GET | `{montant_total_du, montant_total_recu, montant_impaye, nombre_paiements, paiements_recus, paiements_en_retard}` |

`ContratListSerializer`: `id, numero_contrat, bien (nested list serializer), locataire (nested), date_debut, date_fin, statut, statut_display, prix_mensuel`.

`ContratDetailSerializer` adds: `proprietaire (nested), date_signature, is_actif (computed), prix_depot_garantie, charges_mensuelles, nombre_mois_minimum, jour_paiement, modalites_resilition, conditions_speciales, fichier_contrat, paiements (nested list), documents (nested list), date_creation`. Note: **`statut_caution`, `montant_caution_rembourse`, `motif_retenue_caution`, `date_remboursement_caution` are model fields not exposed by any serializer** — caution/deposit refund tracking is UI-only (`contrats.views.caution_traiter`).

`ContratCreateUpdateSerializer` fields: `numero_contrat, bien, proprietaire, locataire, date_debut, date_fin, date_signature, statut, prix_mensuel, prix_depot_garantie, charges_mensuelles, nombre_mois_minimum, jour_paiement, modalites_resilition, conditions_speciales, fichier_contrat`. Validates `date_debut < date_fin`.

### `/paiements/` — `PaiementViewSet`
`IsAuthenticated`. `filterset_fields`: `statut, contrat, mois`. `ordering_fields`: `mois, date_limite`.
- `get_queryset`: `role=proprietaire` → `contrat__proprietaire=user`; `role=locataire` → `contrat__locataire=user`; else all.

| Endpoint | Method | Notes |
| --- | --- | --- |
| `/paiements/` | GET/POST/... | Standard CRUD |
| `/paiements/{id}/enregistrer_paiement/` | POST | Body `{montant_recu}`. Sets `date_paiement=today`, calls `mettre_a_jour_statut()` |
| `/paiements/en_retard/` | GET | Filtered to `retard_mineur, retard_majeur, impaye` within the caller's scoped queryset |

Fields (`PaiementSerializer`): `id, contrat, mois, montant_du, montant_recu, date_limite, date_paiement, statut, statut_display, raison_retard, montant_penalites, date_creation`.

**Not exposed anywhere via API**: `DocumentContrat` (has a serializer `DocumentContratSerializer`, used nested read-only inside `ContratDetailSerializer`, but **no ViewSet/router entry** — cannot list/create documents directly), `Reclamation`, `EtatDesLieux` — both models exist with no serializer or ViewSet at all; reclamations and état-des-lieux are UI-only flows.

---

## 6. Facturation (`/api/facturation/`)

`Facture.Statut` choices: `brouillon, generee, envoyee, payee, annulee`.
`Facture.ModePaiement` choices: `wave, orange_money, mtn, carte, especes, virement`.
`Notification.Type` (facturation app) choices: `email, sms, push`. `Notification.Statut`: `en_attente, envoyee, lue, echec`.
`RappelPaiement.Type` choices: `premier_rappel, deuxieme_rappel, avis_final`.

### `/factures/` — `FactureViewSet`
`IsAuthenticated`. `filterset_fields`: `statut, contrat, date_echéance` (note the accented field name — same in query params: `?date_echéance=...`). `ordering_fields`: `date_echéance, date_generation, montant_total`.
- `get_queryset`: `role=proprietaire` → `contrat__proprietaire=user`; `role=locataire` → `contrat__locataire=user`; else all.

| Endpoint | Method | Notes |
| --- | --- | --- |
| `/factures/` | GET | |
| `/factures/{id}/` | GET/PUT/PATCH/DELETE | **Caveat**: `FactureSerializer`'s write field `contrat_id` is declared with `queryset=Facture.objects.none()` — a bug that makes it **impossible to ever pass validation on create/update** via this serializer as long as `contrat_id` is supplied. In practice, factures are only ever created server-side by the Celery task, not via this endpoint. |
| `/factures/{id}/marquer_payee/` | POST | Sets `statut=payee`, `date_paiement=today` |
| `/factures/{id}/envoyer/` | POST | Sets `statut=envoyee`, increments `tentatives_envoi` |
| `/factures/echues/` | GET | `statut in (generee, envoyee)` and `date_echéance < today` |
| `/factures/impayees/` | GET | `statut != payee` |

Fields: `id, id_unique, numero_facture, contrat (nested ContratListSerializer), contrat_id (write-only, broken as noted), date_generation, date_emission, date_echéance, date_paiement, montant_loyer, montant_charges, montant_autres, montant_taxe, montant_total, description, notes, statut, statut_display, fichier_pdf, tentatives_envoi, dernier_envoi`. Note: **`mode_paiement` and `reference_transaction` model fields are not exposed** by this serializer — Flutter can't read how a facture was paid via the API.

### `/notifications/` — `NotificationViewSet`
`IsAuthenticated`. `get_queryset` always filters to `utilisateur=request.user` (the `filterset_fields` includes `utilisateur` but it's redundant/inert since the base queryset is already scoped). `filterset_fields`: `statut, type_notification, utilisateur`. `ordering_fields`: `date_creation, date_envoi`.

| Endpoint | Method | Notes |
| --- | --- | --- |
| `/notifications/` | GET | Own notifications only |
| `/notifications/{id}/marquer_comme_lue/` | POST | |
| `/notifications/marquer_tout_comme_lu/` | POST | Returns `{count}` |

Fields: `id, facture (nested), facture_id (write), utilisateur, type_notification, type_display, titre, message, statut, statut_display, date_creation, date_envoi, date_lecture, message_erreur`.

**Important**: this is `facturation.Notification` (facture-related email/SMS/push notifications), which is **different from** `dashboard.Notification` (the unified in-app notification feed used by `dashboard_views.notifications_view` for messages/visites/devis/etc. — see Gaps, that one has no API at all).

### `/rappels/` — `RappelPaiementViewSet`
`IsAuthenticated`. No scoping by user (`RappelPaiement.objects.all()` — any authenticated user can see all reminders across all tenants). `filterset_fields`: `est_envoye, type_rappel`.

| Endpoint | Method | Notes |
| --- | --- | --- |
| `/rappels/` | GET/POST/... | |
| `/rappels/{id}/envoyer_rappel/` | POST | 400 if already sent |

Fields: `id, paiement (string repr only, via StringRelatedField), type_rappel, type_display, date_programmee, date_envoi_reel, est_envoye`.

---

## 7. Recherche (`/api/recherche/`)

### `/recherches/` — `RechercheSauvegardeeViewSet`
`IsAuthenticated`, scoped to `utilisateur=request.user`. No `filterset_fields` configured.

| Endpoint | Method | Notes |
| --- | --- | --- |
| `/recherches/` | GET/POST | |
| `/recherches/{id}/` | GET/PUT/PATCH/DELETE | |
| `/recherches/{id}/executer/` | POST | Re-runs the saved search against `Bien` (status=disponible), bumps `nombre_utilisations`/`date_derniere_recherche`, logs to `HistoriqueRecherche`. Returns `{search, results (BienListSerializer[]), count}` |

Fields: `id, utilisateur (nested), nom, villes, budget_min, budget_max, nombre_chambres_min, nombre_chambres_max, surface_min, types_bien, equipements, animaux_autorises, date_creation, date_derniere_recherche, nombre_utilisations`.

### `/favoris/` — `BienFavoriViewSet`
`IsAuthenticated`, scoped to `utilisateur=request.user`.

| Endpoint | Method | Notes |
| --- | --- | --- |
| `/favoris/` | GET/POST | POST body: `{bien_id: <id>}` |
| `/favoris/{id}/` | GET/PUT/PATCH/DELETE | |
| `/favoris/{id}/noter/` | POST | Body `{note: 0-5}` |

Fields: `id, utilisateur (nested), bien (nested BienListSerializer), bien_id (write), note, commentaire, date_ajout`.

### `/historique/` — `HistoriqueRechercheViewSet`
`ReadOnlyModelViewSet` (GET only), `IsAuthenticated`, scoped to own user. `ordering_fields`: `date_recherche`. Fields: `id, utilisateur, requete, nombre_resultats, date_recherche`.

### Extra function-based endpoints (registered directly, not via router)
- `GET /api/recherche/avancee/` (`recherche_avancee`) — **`AllowAny`**. Query params: `ville, budget_min, budget_max, chambres_min, type_bien` (comma-separated for multiple), `operation` (`location`|`vente`|`achat`). Returns `{count, results: BienListSerializer[]}`. Logs to `HistoriqueRecherche` only if authenticated.
- `mes-favoris/` and `favoris/toggle/<bien_id>/` under this same mount are **server-rendered HTML views** (`mes_favoris`, `favori_toggle`), not JSON API — don't use from Flutter (though `favori_toggle` does return `JsonResponse` when called with header `X-Requested-With: XMLHttpRequest`, so it's technically usable as a quasi-API POST if you set that header and handle CSRF, but it's undocumented/unofficial).

---

## 8. Dashboard (`/api/dashboard/`)

### Function-based endpoints
- `GET /api/dashboard/proprietaire/` (`dashboard_proprietaire`) — `IsAuthenticated`, 403 if `role != proprietaire`. Gets-or-creates + recomputes `StatistiquesProprietaire`, returns `StatistiquesProprietaireSerializer`: `id, proprietaire, nombre_proprietes, nombre_contrats_actifs, nombre_locataires, revenu_mensuel_total, revenu_annuel_estime, revenu_recu_ce_mois, montant_impaye, nombre_contrats_avec_impaye, taux_collecte_pourcentage, date_derniere_mise_a_jour`.
- `GET /api/dashboard/locataire/` (`dashboard_locataire`) — `IsAuthenticated`, 403 if `role != locataire`. Returns `TableauBordLocataireSerializer`: `id, locataire, nombre_contrats_actifs, nombre_recherches_sauvegardees, prochain_paiement_date, prochain_paiement_montant, paiements_en_retard, montant_en_retard, nombre_biens_favoris, nombre_visites_programmees, date_derniere_mise_a_jour`.
- `GET /api/dashboard/rapport-mensuel/` (`rapport_mensuel`) — `IsAuthenticated`, 403 if `role != proprietaire`. Query param `?mois=YYYY-MM-DD` (defaults to current month). Gets-or-creates + recomputes a `RapportMensuel`. Returns `RapportMensuelSerializer`: `id, proprietaire, mois, nombre_proprietes, nombre_contrats_actifs, nombre_locataires, revenu_attendu, revenu_recu, montant_impaye, taux_collecte, date_generation, fichier_pdf`.

Two more function views exist in `dashboard/views.py` (`dashboard_admin`, and a duplicate-named `dashboard_locataire` definition further down the file — Python's last-definition-wins applies the same footgun pattern documented in CLAUDE.md for `facturation/tasks.py`) but **neither is wired into `dashboard/urls.py`** — not reachable via any URL at all, dead code.

### `/alertes/` — `AlerteSystemeViewSet`
`IsAuthenticated`, full CRUD. `ordering_fields`: `date_creation, severite`.
- `get_queryset`: only `statut=active` alerts targeted at the user — `tout_le_monde=True` OR (`proprietaires=True` if role=proprietaire) OR (`locataires=True` if role=locataire) OR the user is in `utilisateurs_specifiques`.

`AlerteSysteme.Severite` choices: `info, warning, error, critical`. `AlerteSysteme.Statut` choices: `active, resolue, ignoree`.

Fields: `id, titre, message, severite, severite_display, statut, statut_display, tout_le_monde, proprietaires, locataires, utilisateurs_specifiques (nested list), date_creation, date_expiration, date_resolution`.

### `/logs/` — `LogActiviteViewSet`
`ReadOnlyModelViewSet`, `IsAuthenticated`, scoped to `utilisateur=request.user`. `ordering_fields`: `date_activite, type_activite`.

`LogActivite.Type` choices: `connexion, creation_bien, creation_contrat, facture_generee, paiement_recu, modification, suppression, export, import, autre`. **Caveat**: per a comment in `dashboard_company` view, "`LogActivite` existe mais n'est écrit nulle part" — the model is never populated anywhere in the codebase, so this endpoint will realistically always return an empty list.

Fields: `id, utilisateur, type_activite, type_display, description, details_json, adresse_ip, user_agent, date_activite`.

### `/config/` — `ConfigurationDashboardViewSet`
`IsAuthenticated`, scoped to `utilisateur=request.user`, full CRUD.

Fields: `id, utilisateur, afficher_revenus, afficher_contrats, afficher_alertes, afficher_historique, notifications_email_activees, notifier_paiement_recu, notifier_impaye, notifier_new_demande, langue (fr-FR|en-US), theme (light|dark), widgets_actifs, date_modification`.

---

## 9. Gaps / Not available via API

These are UI-only (server-rendered HTML, plain `JsonResponse`, or PDF/CSV downloads) and have **no DRF endpoint** — a Flutter client cannot use them as-is without new backend work:

- **Messagerie (chat)** — `messagerie/urls.py` has zero DRF routes; it's mounted only at `/chat/...` as Django template views (`mes_conversations`, `conversation_detail`, `nouvelle_conversation`, `gerer_visite`, `changer_phase`, `fiche_client`). One route, `chat/<conv_id>/messages/` (`api_nouveaux_messages`), returns `JsonResponse({'messages': [...]})` — a quasi-API polling endpoint for new messages, but it's session/CSRF-protected HTML-app style, not a documented/stable JSON contract, and there's no way to *send* a message except via an HTML form post. **Real-time chat has no proper API for Flutter today.**
- **Construction** — same situation: `construction/urls.py` is UI-only under `/construction/...` (`liste_entreprises`, `profil_entreprise`, `demande_devis`, `mes_projets`, `projet_detail`, `dashboard_construction`, `mettre_a_jour_etape`, `changer_statut_projet`, `gerer_rdv`, `confirmer_rdv`, `annuler_rdv`, `marquer_notifs_lues`). A couple of these (`changer_statut_projet`, `mettre_a_jour_etape`) return `JsonResponse` but are otherwise plain Django views, not DRF. **Construction/quotes domain has no proper API.**
- **`dashboard.Notification` (unified in-app notification feed)** — the model that actually powers the bell icon in `dashboard_views.notifications_view` (messages, visites, devis, réclamations, paiements) has **no serializer, no ViewSet, no API route**. Only `facturation.Notification` (a different, narrower model for facture email/SMS/push) is exposed via `/api/facturation/notifications/`. A Flutter notification center would need this gap filled.
- **Stripe checkout** (`dashboard_views.stripe_creer_session`, `stripe_paiement_reussi`) — mounted at `/dashboard/facturation/stripe/creer-session/` and `/stripe/succes/` in the root `urls.py`, both plain server-rendered views (redirect to Stripe Checkout, then handle the success redirect). **No API route to create a Stripe session from a mobile client.**
- **Mobile-money "payment" flow** (`dashboard_views.signaler_paiement`, `signaler_probleme_paiement`) — Wave/Orange Money/MTN "payment" is actually just a self-declared confirmation form (`/dashboard/facturation/signaler-paiement/`), UI-only, no API equivalent.
- **PDF/CSV exports** — `facture_pdf`, `factures_zip`, `rapport_mensuel_pdf`, `export_contrats_csv`, `export_paiements_csv`, `mes_contrats_zip` are all plain `HttpResponse`/file-download views under `/dashboard/...` and `/parametres/documents/...`, not JSON, not versioned as an API contract.
- **Caution (deposit) tracking** — `Contrat.statut_caution`, `montant_caution_rembourse`, `motif_retenue_caution`, `date_remboursement_caution` are model fields with a dedicated UI flow (`contrats.views.caution_traiter`) but are absent from every contrat serializer — unreachable via API.
- **`Reclamation`, `EtatDesLieux`, `Reservation`, `DocumentContrat`** — all have models (and `DocumentContrat` even has a serializer) but **no ViewSet/router registration** — none are listable/creatable via the API at all today, only through UI forms.
- **Company** (`utilisateurs.models.Company`: name, `types` JSON list, logo, cover, address, etc.) — no serializer/ViewSet anywhere, and `UtilisateurSerializer` doesn't even nest/reference it. A Flutter app cannot read or edit a proprietor's company profile via the API — onboarding (`/onboarding/`), company signup (`/accounts/signup/company/`), and company profile edit (`/dashboard/entreprise/modifier/`) are all HTML-only.
- **OTP email verification** (`confirmer_email`, `renvoyer_confirmation`) — HTML-only, POST to `/accounts/confirmer-email/` with a `code` field; no JSON endpoint.
- **Password reset** — `path('accounts/', include('django.contrib.auth.urls'))` wires up Django's default auth URLs (`password_reset/`, `password_reset/done/`, `reset/<uidb64>/<token>/`, `reset/done/`), all HTML-template based, no API/JSON equivalent.

### Known correctness quirks worth flagging to the Flutter team (not strictly "missing", but will bite)
- `BienViewSet` is `AllowAny` on **all** actions including write — no server-side ownership enforcement on create/update/delete beyond `perform_create` forcing `proprietaire=request.user` (which will error for anonymous callers rather than reject cleanly with 401/403).
- `FactureSerializer.contrat_id` has `queryset=Facture.objects.none()`, so any client-side attempt to create/update a `Facture` supplying `contrat_id` will always fail validation.
- `PhotoBienViewSet.perform_create`'s ownership check returns a `Response` instead of raising `PermissionDenied`, so the "error" response may not actually stop the save from happening as expected.
