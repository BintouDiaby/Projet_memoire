# ImmoGérer — Fonctions de l'application web intégrables dans l'app mobile

Inventaire complet des fonctionnalités actuellement présentes dans la plateforme web ImmoGérer (Django + DRF), organisé par domaine, avec pour chacune son état d'exposition API :

- ✅ **API REST disponible** — un client mobile (Flutter ou autre) peut l'utiliser dès maintenant via `/api/...`.
- ⚠️ **Web only (à exposer)** — la fonctionnalité existe et fonctionne sur le web, mais uniquement via des vues Django server-rendered (HTML) ou de simples `JsonResponse` non documentées — il faut construire un vrai endpoint DRF avant de pouvoir l'intégrer côté mobile.
- 🆕 marque les fonctionnalités ajoutées récemment (donc absentes de l'ancien `API_REFERENCE_FLUTTER.md`).

> Référence technique complémentaire : `API_REFERENCE_FLUTTER.md` (détail des endpoints existants, permissions, champs) et `FLUTTER_APP_BRIEF.md` (direction artistique, écrans, priorités). Ce fichier-ci est la liste fonctionnelle ; les deux autres sont la doc d'implémentation.

---

## 1. Comptes & authentification

| Fonction | État |
|---|---|
| Connexion (session + CSRF) | ✅ |
| Inscription particulier (locataire) | ✅ |
| Inscription entreprise (propriétaire/gestionnaire) + création `Company` | ⚠️ Web only |
| Vérification d'email par code OTP | ⚠️ Web only |
| Réinitialisation de mot de passe | ⚠️ Web only (Django auth views HTML) |
| Modifier mon profil (nom, téléphone, photo) | ✅ (`UtilisateurViewSet`) |
| Préférences de confidentialité (afficher téléphone/email, accepter les appels) | ✅ (champs sur `Utilisateur`) |
| Profil propriétaire / locataire étendu | ✅ (`ProprietaireProfileViewSet`, `LocataireProfileViewSet`) |
| Profil entreprise (`Company` : nom, logo, adresse, RCCM, NCC, régime TVA) | ⚠️ Web only — aucun serializer/ViewSet |
| 🆕 Statut de disponibilité entreprise (en ligne/pause/fermé) + délai de réponse | ⚠️ Web only |
| 🆕 Horaires d'ouverture par jour | ⚠️ Web only |
| Vérification de documents entreprise (badge "vérifié") | ⚠️ Web only (admin) |

## 2. Recherche & découverte de biens

| Fonction | État |
|---|---|
| Liste des biens avec filtres (ville, type, prix, chambres) | ✅ (`BienViewSet`, `DjangoFilterBackend`) |
| Détail d'un bien | ✅ |
| Recherche avancée (quartier, budget, entreprise vérifiée) | ⚠️ Web only (`explorer_view`, filtres HTML) |
| Recherche géolocalisée "autour de moi" (distance à vol d'oiseau) | ⚠️ Web only |
| Recherches sauvegardées | ✅ (`RechercheSauvegardeeViewSet`) |
| Historique de recherche | ✅ (`HistoriqueRechercheViewSet`) |
| Favoris (ajouter/retirer un bien) | ✅ (`BienFavoriViewSet`) |
| Page "Mes favoris" | ⚠️ Web only (vue HTML séparée du ViewSet) |
| 🆕 Avis/notes sur un bien (1-5 étoiles + commentaire, réservé aux anciens locataires) | ⚠️ Web only |
| Photos additionnelles d'un bien | ✅ (`PhotoBienViewSet` — ownership check fragile, voir quirks) |
| Annuaire des entreprises | ⚠️ Web only |
| Fiche publique entreprise (biens publiés, zones couvertes, statistiques) | ⚠️ Web only |
| 🆕 Avis/notes sur une entreprise | ⚠️ Web only |
| 🆕 Carte + itinéraire vers une entreprise | ⚠️ Web only |

## 3. Visites & réservations

| Fonction | État |
|---|---|
| Demander une visite d'un bien | ✅ (`VisiteViewSet`, statut non exposé en écriture côté client) |
| Confirmer / refuser une visite (propriétaire) | ⚠️ Web only |
| Annuler ma visite (locataire) | ⚠️ Web only |
| 🆕 Une visite annulée/refusée ne bloque plus une nouvelle demande | ✅ correction de bug (logique serveur) |
| Réservation d'un bien (hold 72h) | ⚠️ Web only — `Reservation` a un modèle mais pas de ViewSet |
| Annuler ma réservation | ⚠️ Web only |
| Confirmation de réservation → création automatique d'un contrat brouillon | ⚠️ Web only |

## 4. Contrats

| Fonction | État |
|---|---|
| Liste / détail de mes contrats | ✅ (`ContratViewSet`, scoping par rôle) |
| Compléter un contrat brouillon (propriétaire) | ⚠️ Web only |
| Envoyer le contrat pour signature | ⚠️ Web only |
| Signer le contrat (clic-à-clic locataire) | ⚠️ Web only |
| Télécharger le contrat en PDF | ⚠️ Web only (fichier, pas JSON) |
| Rappeler un contrat envoyé pour le modifier | ⚠️ Web only |
| Supprimer un contrat brouillon | ⚠️ Web only |
| Archiver / désarchiver un contrat terminé | ⚠️ Web only |
| 🆕 Résilier un contrat en cours (motif obligatoire, notification locataire) | ⚠️ Web only |
| Suivi de caution (retenue/remboursement, motif) | ⚠️ Web only — absent des serializers |
| État des lieux (entrée/sortie) | ⚠️ Web only — modèle sans ViewSet |
| Centre de suivi du contrat (timeline complète) | ⚠️ Web only |
| Réclamations liées à un contrat | ⚠️ Web only — modèle sans ViewSet |
| Export ZIP de mes contrats (PDF) | ⚠️ Web only (fichier) |

## 5. Paiements & facturation

| Fonction | État |
|---|---|
| Liste de mes paiements | ✅ (`PaiementViewSet`) |
| Liste de mes factures | ✅ (`FactureViewSet`) — `contrat_id` en écriture cassé côté validation |
| Génération mensuelle automatique des factures | N/A (tâche Celery serveur) |
| Télécharger une facture en PDF | ⚠️ Web only |
| Export CSV paiements / rapport mensuel PDF | ⚠️ Web only |
| Paiement en ligne (Stripe) | ⚠️ Web only — pas d'endpoint pour créer une session depuis mobile |
| "Paiement" mobile money (Wave/Orange/MTN) — déclaratif | ⚠️ Web only — simple formulaire d'auto-déclaration |
| Rendez-vous de paiement en espèces (proposer/confirmer/refuser) | ⚠️ Web only — `RendezVousPaiement` sans ViewSet |
| Confirmation de réception des espèces (propriétaire), avec verrou de date | ⚠️ Web only |
| Centre des échéances (timeline mensuelle des paiements) | ⚠️ Web only |
| Rappels de paiement programmés (J+2/J+7/J+15) | ✅ lecture (`RappelPaiementViewSet`) |
| Moyens de paiement enregistrés | ⚠️ Web only — modèle sans ViewSet |

## 6. Gestion des retards & litiges

| Fonction | État |
|---|---|
| Escalade automatique (rappel → frais de retard → mise en demeure recommandée → alerte grave) | N/A (logique serveur, tâche périodique) |
| Envoyer une mise en demeure (propriétaire) | ⚠️ Web only |
| Télécharger la mise en demeure en PDF | ⚠️ Web only |
| Accorder un délai supplémentaire / clôturer / marquer "procédure" | ⚠️ Web only |
| Échelle de recouvrement (indicateur visuel, propriétaire uniquement) | ⚠️ Web only |
| Préparer le dossier juridique complet (contrat + paiements + factures + mises en demeure + messages) | ⚠️ Web only |

## 7. Messagerie

| Fonction | État |
|---|---|
| Liste de mes conversations | ⚠️ Web only — **aucune route DRF**, tout est HTML |
| Ouvrir une conversation / envoyer un message | ⚠️ Web only |
| Nouveaux messages (polling) | ⚠️ Semi-JSON non stable (`JsonResponse` non documenté) |
| Modifier / supprimer (soft) un message | ⚠️ Web only |
| Archiver une conversation | ⚠️ Web only |
| Changer la phase d'une conversation (commercial → SAV) | ⚠️ Web only |

> Domaine entier à construire côté API pour le mobile — priorité haute si le chat doit exister sur mobile (potentiellement via WebSocket/Channels plutôt que polling REST).

## 8. Notifications

| Fonction | État |
|---|---|
| Centre de notifications unifié (paiement, contrat, message, visite, devis, réclamation, mise en demeure) | ⚠️ Web only — **le modèle `dashboard.Notification` qui alimente la cloche n'a aucun ViewSet** |
| Marquer une notification comme lue | ⚠️ Web only |
| Tout marquer comme lu | ⚠️ Web only |
| 🆕 Supprimer une notification | ⚠️ Web only |
| Notifications construction (séparées) | ⚠️ Web only |
| Notifications facturation (email/SMS programmés) | ✅ (`facturation.Notification` via `/api/facturation/notifications/`) — modèle différent, plus étroit |

## 9. Construction

| Fonction | État |
|---|---|
| Annuaire des entreprises de construction | ⚠️ Web only |
| Profil entreprise construction (réalisations, spécialités) | ⚠️ Web only |
| 🆕 Gérer mon profil construction (description, services, horaires) | ⚠️ Web only |
| 🆕 Ajouter / modifier / supprimer une réalisation (portfolio) | ⚠️ Web only |
| Demander un devis (client) | ⚠️ Web only |
| 🆕 Préparer et envoyer un devis chiffré (entreprise) | ⚠️ Web only |
| 🆕 Accepter / refuser un devis (client, avec motif) | ⚠️ Web only |
| 🆕 Télécharger le devis en PDF | ⚠️ Web only |
| Mes projets de construction | ⚠️ Web only |
| Suivi de chantier (étapes, % avancement, photos) | ⚠️ Web only |
| Mettre à jour une étape (entreprise) | ⚠️ Semi-JSON non stable |
| Proposer / confirmer / annuler un RDV construction | ⚠️ Web only |
| Dashboard construction (KPIs entreprise) | ⚠️ Web only |

> Domaine entier à construire côté API — c'est aussi le domaine le plus enrichi cette session (devis réel, profil, réalisations).

## 10. Dashboard & statistiques

| Fonction | État |
|---|---|
| KPIs entreprise (biens, contrats actifs, paiements, projets construction) | ⚠️ Web only — vues function-based |
| Activité récente (flux fusionné bien/contrat/paiement/message/visite) | ⚠️ Web only |
| Tableau de bord locataire ("Mon espace" : contrat actif, prochain paiement, factures, favoris, notifications) | ⚠️ Web only |
| Rendez-vous du jour (visites + construction + espèces réunis) | ⚠️ Web only |
| Centre de validation des paiements | ⚠️ Web only |
| Alertes système | ✅ (`AlerteSystemeViewSet`) |
| Logs d'activité | ✅ modèle exposé (`LogActiviteViewSet`) mais **jamais rempli** — table vide |
| Configuration dashboard personnalisée | ✅ (`ConfigurationDashboardViewSet`) |

## 11. Assistant IA 🆕

| Fonction | État |
|---|---|
| Menu guidé (trouver un logement, comprendre mon contrat, paiement, construction, contacter une entreprise) | ⚠️ Web only |
| Recherche de logement guidée (ville + budget → résultats en cartes) | ⚠️ Web only |
| Menu entreprise (client, paiements en retard, RDV du jour, devis) | ⚠️ Web only |
| Question libre → recherche par mots-clés dans le centre d'aide | ⚠️ Web only |
| Historique de conversation avec l'assistant | ⚠️ Web only |

> Aucune dépendance à un LLM externe (Ollama a été retiré) — tout est basé sur des règles + données de l'app, donc facilement portable côté mobile une fois les endpoints exposés.

## 12. Centre d'aide 🆕

| Fonction | État |
|---|---|
| FAQ par catégorie (location, construction, paiements, contrats, compte, messagerie, paramètres) | ⚠️ Web only — contenu statique en Python, facile à exposer en JSON |

---

## Synthèse — priorités suggérées pour le mobile

**Déjà prêt côté API (juste à consommer)** :
Auth, biens (liste/détail/photos), visites (lecture/création), contrats (lecture), paiements (lecture), factures (lecture), favoris, recherches sauvegardées, historique de recherche, alertes système.

**Gains rapides si on expose l'API (logique déjà écrite, juste besoin d'un serializer/ViewSet)** :
Notifications unifiées (bloque toute expérience "cloche" mobile), Company/profil entreprise, avis biens/entreprises, réclamations, état des lieux, caution.

**Chantiers plus lourds (domaine entier à construire)** :
Messagerie (idéalement WebSocket pour du temps réel plutôt que du polling), Construction (devis + suivi chantier), Assistant IA guidé, paiement en ligne mobile (Stripe SDK natif ou deep link), gestion des litiges/mise en demeure.

**Probablement à garder web-only (peu de valeur ou complexité disproportionnée sur mobile)** :
Dossier juridique PDF, exports CSV/ZIP, dashboard statistiques entreprise détaillé (mieux adapté à un grand écran), configuration du régime TVA/RCCM.
