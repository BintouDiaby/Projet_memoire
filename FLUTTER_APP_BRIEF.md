# ImmoGérer Mobile — Brief pour Claude (projet Flutter)

Instructions à suivre pour construire l'app mobile Flutter d'ImmoGérer (plateforme de gestion locative, Côte d'Ivoire, domaine en français) et la connecter au backend Django déjà en production de développement. Ce document réunit : (1) la direction artistique (DA) réellement implémentée côté web cette session, (2) l'inventaire des écrans à créer avec noms de fichiers/classes/routes, (3) les endpoints backend à connecter pour chacun, (4) les instructions d'exécution.

**Référence complémentaire obligatoire** : `API_REFERENCE_FLUTTER.md` (même dépôt) documente en détail chaque endpoint REST (méthodes, permissions, champs, filtres). Ce brief-ci s'appuie dessus — ne pas dupliquer, s'y référer.

---

## 0. Instructions d'exécution (à suivre dans l'ordre)

1. Lire `API_REFERENCE_FLUTTER.md` en entier avant de coder quoi que ce soit — il documente l'auth (session + CSRF, **pas de JWT**), le scoping par rôle, et les champs exacts de chaque endpoint.
2. Mettre en place la couche réseau (section 2 ci-dessous) et valider le login contre le vrai backend (`http://<host>:8000` en dev) avant de construire le moindre écran.
3. Construire les écrans dans cet ordre de priorité : Auth → Espace locataire (accueil, contrats, factures) → Explorer/recherche → Messagerie → Espace entreprise. Ne pas paralléliser tous les écrans d'un coup : valider le flux auth + un écran de bout en bout (vrai appel réseau, vrai rendu) avant d'enchaîner.
4. Respecter strictement le vocabulaire métier français listé en section 4 (noms d'écrans, statuts, libellés) — ce sont les mêmes termes que le backend et l'UI web, ne pas traduire ni renommer.
5. Pour chaque écran construit, noter dans ce fichier (ou un fichier `PROGRESS.md` à créer) ce qui est fait/manquant — les gaps listés en section 6 de `API_REFERENCE_FLUTTER.md` (messagerie, construction, notifications dashboard) n'ont **aucune API** actuellement : soit les exclure du MVP mobile, soit remonter la demande pour que le backend Django les expose d'abord.
6. Ne pas inventer de champs ou d'endpoints. Si quelque chose manque côté backend, le signaler explicitement plutôt que de mocker silencieusement.

---

## 1. Direction artistique (DA)

Extraite directement des templates web réellement livrés cette session (pas une interprétation) — deux univers visuels distincts selon le rôle connecté.

### 1.1 Palette — Espace **Locataire** (bleu)
```
primary       #185FA5
primary-dark  #1A3E6A
primary-soft  #E7F0F9   (fonds de badges/hover)
primary-text  #0C447C   (texte sur fond soft)
accent (or)   #C9A84C   (logo, CTA premium)
```

### 1.2 Palette — Espace **Entreprise/Propriétaire** (vert)
```
green         #3B6D11  (ou #1F7A4E selon écran — les deux existent, utiliser #1F7A4E pour "gestion d'un bien", #3B6D11 pour "dashboard company")
green-dark    #2C520C / #155A38
green-soft    #EAF3DE / #E5F3EA
green-text    #27500A / #155A38
```

### 1.3 Couleurs communes (statuts, tous rôles)
```
ink (titres)      #16202B
text (corps)      #39414A
muted             #6B7280
muted-2           #9AA0A6
line (bordures)   #E7EAEE
bg (fond page)    #F4F6F9
card (fond carte) #FFFFFF

amber (attente/avertissement)  #B45309   soft #FEF3C7
red (erreur/retard grave)      #B4441F  ou  #B91C1C   soft #FBEAE4 / #FEE2E2
purple (tag "SAV")             #6D4AAE   soft #EFE8FA
```

### 1.4 Typographie
- **Titres / display** (`h1`, montants, chiffres KPI) : **Plus Jakarta Sans**, graisses 600/700/800.
- **Corps de texte** : **Inter**, graisses 400/500/600.
- En Flutter : charger les deux polices via `google_fonts` (`GoogleFonts.plusJakartaSans()` / `GoogleFonts.inter()`), pas de fichiers de police locaux nécessaires.

### 1.5 Composants récurrents à répliquer
- **Cartes** : fond blanc, bordure `1px solid #E7EAEE`, `border-radius: 14–16px`, ombre légère (`0 1px 2px rgba(16,32,48,.05)`).
- **Badges de statut** (pilule, texte 11–12px, gras 700) : vert=payé/confirmé, ambre=en attente, rouge=retard/refusé, bleu=info.
- **KPI cards** : label majuscule petit gris (11px, letter-spacing), valeur en Plus Jakarta Sans gras 800 taille 20-24px, sous-texte gris 11.5px. Grille 3 ou 4 colonnes selon écran.
- **Boutons** : `primary` (fond couleur pleine, texte blanc), `ghost` (fond blanc, bordure grise), `amber`/`danger` (bordure colorée, fond blanc) — coins arrondis 9-10px, padding ~9x15px.
- **Bannière d'alerte** (ex. retard de paiement, email non confirmé) : fond pastel de la couleur concernée, bordure assortie, icône + texte + action.
- **Bottom sheet / modal** pour actions rapides (payer une facture, signaler un problème) plutôt que navigation complète — sur mobile, utiliser `showModalBottomSheet`.

---

## 2. Connexion au backend

### 2.1 Client HTTP
Utiliser `dio` + `dio_cookie_manager` (`PersistCookieJar`) — **obligatoire**, pas de token/JWT disponible, tout repose sur le cookie de session Django + CSRF. Voir `API_REFERENCE_FLUTTER.md` section 1 pour le détail exact du flux.

Résumé :
1. `GET /api-auth/login/` une fois au démarrage pour obtenir le cookie `csrftoken`.
2. `POST /api-auth/login/` (form-urlencoded) avec `username`, `password`, `csrfmiddlewaretoken` → cookie `sessionid` posé automatiquement par le cookie jar.
3. Chaque requête POST/PUT/PATCH/DELETE doit inclure le header `X-CSRFToken` = valeur courante du cookie `csrftoken` (intercepteur Dio à écrire une fois, réutilisé partout).
4. Logout : `POST /accounts/logout/`.

### 2.2 Base URL
Configurer via variable d'environnement / flavor (`--dart-define=API_BASE_URL=http://10.0.2.2:8000` pour l'émulateur Android qui ne voit pas `127.0.0.1` de la machine hôte ; `http://127.0.0.1:8000` pour iOS simulator/web).

### 2.3 Pagination
Toutes les listes sont paginées (`PageNumberPagination`, 10/page, `?page=N`). Prévoir un widget de liste avec scroll infini ou pagination classique, pas un simple `ListView` chargé d'un coup.

---

## 3. Structure de projet suggérée

```
lib/
  core/
    api/
      dio_client.dart          # config Dio + cookie jar + intercepteur CSRF
      endpoints.dart           # constantes des chemins /api/...
    theme/
      app_colors.dart          # tokens de la section 1
      app_text_styles.dart
      app_theme_locataire.dart # ThemeData bleu
      app_theme_entreprise.dart# ThemeData vert
  features/
    auth/
      login_screen.dart
      signup_screen.dart
      otp_confirm_screen.dart
    locataire/
      home/mon_espace_screen.dart
      explorer/explorer_screen.dart
      biens/bien_detail_screen.dart
      contrats/mes_contrats_screen.dart
      contrats/contrat_suivi_screen.dart
      factures/factures_screen.dart
      factures/facture_detail_screen.dart
      profil/mon_profil_screen.dart
      parametres/parametres_screen.dart
    entreprise/
      dashboard/dashboard_entreprise_screen.dart
      biens/mes_biens_screen.dart
      biens/gerer_bien_screen.dart
      biens/publier_bien_screen.dart
      clients/clients_screen.dart
      clients/client_detail_screen.dart
    messagerie/
      conversations_screen.dart
      conversation_detail_screen.dart
    partage/
      widgets/kpi_card.dart
      widgets/status_badge.dart
      widgets/facture_row.dart
```

---

## 4. Inventaire des écrans

Format : **NomClasse** (`chemin/fichier.dart`) — route — objectif — endpoint(s) backend — éléments clés.

### 4.1 Authentification (commun)

| Écran | Route | Endpoint(s) | Détails |
| --- | --- | --- | --- |
| **LoginScreen** (`auth/login_screen.dart`) | `/login` | `POST /api-auth/login/` puis `GET /api/utilisateurs/utilisateurs/me/` pour récupérer le profil connecté | Champs username/password, redirige selon `role` (`locataire` → accueil locataire, `proprietaire`/`gestionnaire` → dashboard entreprise) |
| **SignupScreen** (`auth/signup_screen.dart`) | `/signup` | `POST /api/utilisateurs/utilisateurs/` (crée le compte, **ne connecte pas** — enchaîner avec le login) | Champs : `username, email, password, password2, first_name, last_name, role, telephone`. Pas de création de `Company` possible via API (gap backend) |
| **OtpConfirmScreen** (`auth/otp_confirm_screen.dart`) | `/confirmer-email` | Aucun endpoint API — la vérification OTP est **UI Django uniquement** (`/accounts/confirmer-email/`) actuellement | **Gap** : demander l'ajout d'un endpoint API `POST /api/utilisateurs/confirmer-otp/` côté backend avant de construire cet écran proprement ; en attendant, on peut ouvrir la page web dans une `WebView` en solution de repli |

### 4.2 Espace Locataire (thème bleu)

| Écran | Route | Endpoint(s) principal(aux) | Détails / éléments UI |
| --- | --- | --- | --- |
| **MonEspaceScreen** (`locataire/home/mon_espace_screen.dart`) | `/` (accueil locataire) | `GET /api/contrats/contrats/?locataire=me` (scoping auto par le backend selon l'utilisateur connecté — pas besoin de filtrer manuellement), `GET /api/contrats/paiements/`, `GET /api/facturation/factures/` | Salutation avec prénom, KPI (loyer mensuel total, statut du mois, prochain paiement, favoris), une carte par contrat actif (photo du bien, badge statut paiement du mois, bouton "Voir le contrat"/"Contacter"), historique des paiements (mois passés uniquement, ordre chronologique), carte de localisation (si le bien a lat/lng) |
| **ExplorerScreen** (`locataire/explorer/explorer_screen.dart`) | `/explorer` | `GET /api/biens/biens/?transaction_type=location&search=...&ordering=...` | Liste + filtres (ville, commune, budget max, chambres), tabs par catégorie (locations/vente/terrains/magasins/bureaux/construction), option carte (packages `flutter_map` + `latlong2` en remplacement de Leaflet), géolocalisation "Autour de moi" via `geolocator` (permission position, tri par distance côté client si le backend ne le fait pas encore) |
| **BienDetailScreen** (`locataire/biens/bien_detail_screen.dart`) | `/biens/:id` | `GET /api/biens/biens/{id}/`, `POST /api/biens/visites/` (demander visite), `POST /api/recherche/favoris/toggle/{id}/` | Photo, prix, caractéristiques, bouton favoris, formulaire demande de visite, infos propriétaire/entreprise |
| **MesContratsScreen** (`locataire/contrats/mes_contrats_screen.dart`) | `/mes-contrats` | `GET /api/contrats/contrats/` | Liste des contrats (en cours/terminés), badge retard |
| **ContratSuiviScreen** (`locataire/contrats/contrat_suivi_screen.dart`) | `/contrats/:id/suivi` | `GET /api/contrats/contrats/{id}/`, `GET /api/contrats/paiements/?contrat={id}`, `GET /api/facturation/factures/?contrat={id}` | Onglets : Aperçu / Facture actuelle / Paiements / Réclamations / Visites (le back-end n'expose pas les messages ni un endpoint "journal" combiné — recomposer côté client à partir des appels séparés, ou traiter comme gap) |
| **FacturesScreen** (`locataire/factures/factures_screen.dart`) | `/factures` | `GET /api/facturation/factures/` | Liste avec filtres (toutes/en attente/en retard/payées), bannière si retard, montant total dû |
| **FactureDetailScreen** (`locataire/factures/facture_detail_screen.dart`) | `/factures/:id` | `GET /api/facturation/factures/{id}/`, action de paiement — **voir gap Stripe/mobile money ci-dessous** | Détail montant, statut, bouton "Payer" |
| **MonProfilScreen** (`locataire/profil/mon_profil_screen.dart`) | `/profil` | `GET/PUT /api/utilisateurs/utilisateurs/{id}/` | Édition infos perso, photo de profil |
| **ParametresScreen** (`locataire/parametres/parametres_screen.dart`) | `/parametres` | `PUT /api/utilisateurs/utilisateurs/{id}/` (mot de passe, confidentialité `afficher_telephone`/`afficher_email`), pas d'endpoint API dédié pour suppression de compte/sessions — **gap**, à vérifier avant de construire ces sous-onglets | Onglets simplifiés : Général, Mot de passe, Confidentialité (MVP) |

### 4.3 Espace Entreprise / Propriétaire (thème vert)

| Écran | Route | Endpoint(s) principal(aux) | Détails |
| --- | --- | --- | --- |
| **DashboardEntrepriseScreen** (`entreprise/dashboard/dashboard_entreprise_screen.dart`) | `/dashboard` | `GET /api/biens/biens/?proprietaire=me`, `GET /api/contrats/contrats/`, `GET /api/facturation/factures/` | KPI globaux (nb biens, revenus, paiements en retard) — **pas d'endpoint dashboard agrégé dédié**, calculer côté client à partir des listes ou demander l'ajout d'un endpoint résumé côté backend |
| **MesBiensScreen** (`entreprise/biens/mes_biens_screen.dart`) | `/mes-biens` | `GET /api/biens/biens/?proprietaire=me` | Grille de biens avec statut (disponible/loué/archivé), filtre par statut |
| **GererBienScreen** (`entreprise/biens/gerer_bien_screen.dart`) | `/biens/:id/gerer` | `GET /api/biens/biens/{id}/`, `GET /api/biens/visites/?bien={id}&statut=en_attente`, action confirmer/refuser visite — **vérifier si ces actions sont exposées en `@action` sur `VisiteViewSet`, sinon gap** | KPI (demandes de visite, réservations, favoris), liste des demandes de visite avec boutons Accepter/Refuser, bouton publier/dépublier (**vérifier si le champ `statut` du bien est modifiable via `PATCH /api/biens/biens/{id}/` — probablement oui, standard DRF update**) |
| **PublierBienScreen** (`entreprise/biens/publier_bien_screen.dart`) | `/biens/publier` | `POST /api/biens/biens/` | Formulaire multi-étapes par opération (location/vente/terrain/construction), upload photo (`POST /api/biens/photos/` ou `multipart/form-data` sur le champ `photo_principale`) |
| **ClientsScreen** (`entreprise/clients/clients_screen.dart`) | `/clients` | Pas d'endpoint CRM dédié identifié dans `API_REFERENCE_FLUTTER.md` — dériver la liste des locataires à partir de `GET /api/contrats/contrats/?proprietaire=me` (distinct des `locataire`) — **gap à confirmer** | Liste des locataires actuels/passés |

### 4.4 Messagerie — **gap backend majeur**

`messagerie` n'a **aucune route DRF** (confirmé dans `API_REFERENCE_FLUTTER.md` section 9). **Ne pas construire ConversationsScreen/ConversationDetailScreen tant que le backend n'expose pas** :
- `GET/POST /api/messagerie/conversations/`
- `GET/POST /api/messagerie/conversations/{id}/messages/`

Deux options : (a) demander cet ajout côté backend avant de construire cette fonctionnalité mobile, (b) MVP sans messagerie native, avec un lien "Ouvrir dans le navigateur" vers `/chat/` en attendant.

---

## 5. Statuts et énumérations à répliquer exactement (pas de traduction/renommage)

```
Utilisateur.role        : proprietaire | gestionnaire | locataire | admin
Bien.statut              : disponible | loue | maintenance | archive
Bien.transaction_type    : location | vente | both
Contrat.statut           : (voir models.py — inclut au moins en_cours, termine, resilie)
Paiement.statut          : en_attente | recu | retard_mineur | retard_majeur | impaye
Facture.statut           : brouillon | generee | envoyee | payee | annulee
Facture.mode_paiement    : wave | orange_money | mtn | carte | especes | virement
```
Badges couleur associés (déjà utilisés côté web, à reprendre à l'identique) :
- `recu` / `payee` → vert
- `en_attente` / `generee` / `envoyee` → ambre
- `retard_mineur` → orange
- `retard_majeur` / `impaye` → rouge

---

## 6. Paiement par carte (Stripe) — statut mobile

Le paiement carte passe par **Stripe Checkout hébergé** (redirection navigateur), pas par le SDK Stripe natif — il n'y a pas de `PaymentIntent`/`client_secret` exposé par l'API pour un flux natif `flutter_stripe`. Sur mobile, la solution la plus simple sans nouveau travail backend : ouvrir l'URL de session Checkout (obtenue en appelant l'équivalent mobile de `POST /dashboard/facturation/stripe/creer-session/` — **vérifier si cette route a un pendant `/api/...` ou si c'est une vue Django classique à appeler en form-post**, probablement cette dernière) dans une `WebView` (`webview_flutter`), et détecter le retour sur l'URL de succès pour rafraîchir l'écran facture. Wave/Orange Money/MTN restent en auto-déclaration (formulaire "j'ai payé via ce moyen").

---

## 7. Ce qu'il ne faut PAS construire tant que le backend n'est pas étendu

Cette liste vient de `API_REFERENCE_FLUTTER.md` section 9 — la respecter évite de construire des écrans mobile sans données réelles :
- Messagerie native (voir 4.4)
- Suivi de construction (`construction` app — UI-only)
- Notifications in-app temps réel (`dashboard.Notification` n'a pas d'API — seule `facturation.Notification`, plus étroite, en a une)
- Réclamations, états des lieux, réservations : modèles existants mais sans `ViewSet` enregistré — vérifier avant de coder l'écran correspondant

---

## 8. Bugs backend connus à contourner ou signaler

1. `BienViewSet` accepte des écritures anonymes (`AllowAny`) sur des actions qui devraient être protégées — jusqu'à correction côté Django, ne pas supposer qu'un 401/403 propre reviendra sur une requête non authentifiée : tester le comportement réel avant de coder la gestion d'erreur.
2. `FactureSerializer.contrat_id` a une queryset vide côté validation — un `POST`/`PATCH` qui tente de définir ce champ échouera systématiquement ; ne pas l'exposer en édition côté mobile.
3. Le contrôle de propriété sur `PhotoBienViewSet` peut ne pas bloquer réellement l'upload — ne pas se fier uniquement à la réponse HTTP pour la sécurité perçue côté UI.
