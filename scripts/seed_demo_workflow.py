"""
Peuple des exemples réalistes pour les comptes de test déjà utilisés
(Abeja King / Bintou Diaby / fatimah dby) : biens, contrat, visites,
réclamation, favori, message, notifications — pour voir les pages
construites récemment (Mes biens, Mes visites, Mes favoris, Réclamations,
Notifications, Pipeline CRM) avec du contenu au lieu d'états vides.

Usage: python scripts/seed_demo_workflow.py
"""
import os
import sys
from pathlib import Path
from datetime import timedelta

BASE = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'immobilier_config.settings')
import django
django.setup()

from django.utils import timezone
from utilisateurs.models import Utilisateur, ProprietaireProfile
from biens.models import Bien, Visite
from contrats.models import Contrat, Reclamation
from messagerie.models import Conversation, Message
from recherche.models import BienFavori
from dashboard.services import NotificationService

owner = Utilisateur.objects.get(username='Abejakings')
locataire = Utilisateur.objects.get(username='Bintoudby')
prospect = Utilisateur.objects.get(username='fatimahdby07')

# ── Profil propriétaire minimal (pour la checklist de complétude) ──────────
prof, _ = ProprietaireProfile.objects.get_or_create(utilisateur=owner)
if not prof.numero_siret_siren:
    prof.numero_siret_siren = 'CI-RCCM-2024-B-5821'
    prof.nom_entreprise = prof.nom_entreprise or 'Abeja King'
    prof.save()
    print('OK profil propriétaire complété (RCCM)')

# ── Biens pour Abeja King ───────────────────────────────────────────────────
BIENS = [
    dict(
        titre='Villa 4 pièces – Grand-Bassam',
        description="Villa moderne à deux pas de la plage, jardin clos, sécurisée.",
        type_bien=Bien.TypeBien.MAISON, transaction_type=Bien.TransactionType.LOCATION,
        adresse='Rue des Cocotiers', quartier='Front de mer', commune='Grand-Bassam', ville='Grand-Bassam',
        surface_m2=180, nombre_chambres=4, nombre_salles_bain=2, nombre_etages=1,
        prix_mensuel=350000, prix_depot_garantie=700000,
    ),
    dict(
        titre='Appartement T2 – Grand-Bassam Centre',
        description="Appartement calme proche du marché central, idéal jeune couple.",
        type_bien=Bien.TypeBien.T2, transaction_type=Bien.TransactionType.LOCATION,
        adresse='Avenue de la République', quartier='Centre', commune='Grand-Bassam', ville='Grand-Bassam',
        surface_m2=65, nombre_chambres=2, nombre_salles_bain=1, nombre_etages=2,
        prix_mensuel=150000, prix_depot_garantie=300000,
    ),
    dict(
        titre='Terrain 300 m² – Grand-Bassam',
        description="Terrain viabilisé proche lagune, titre foncier disponible.",
        type_bien=Bien.TypeBien.TERRAIN, transaction_type=Bien.TransactionType.VENTE,
        adresse='Route de la lagune', quartier='Impérial', commune='Grand-Bassam', ville='Grand-Bassam',
        surface_m2=300, nombre_chambres=0, nombre_salles_bain=0, nombre_etages=1,
        prix_mensuel=0, prix_vente=12000000, prix_depot_garantie=0,
    ),
]

created_biens = []
for data in BIENS:
    bien = Bien.objects.filter(titre=data['titre'], proprietaire=owner).first()
    if bien:
        print(f'  (déjà existant) {bien.titre}')
        created_biens.append(bien)
        continue
    bien = Bien(proprietaire=owner, statut=Bien.Statut.DISPONIBLE, date_publication=timezone.now(), **data)
    bien.full_clean(exclude=['photo_principale'])
    bien.save()
    created_biens.append(bien)
    print(f'  OK {bien.titre} -> /biens/{bien.id}/')

villa, appartement, terrain = created_biens[0], created_biens[1], created_biens[2]

# ── Contrat actif : Bintou loue la villa ────────────────────────────────────
contrat, created = Contrat.objects.get_or_create(
    bien=villa, proprietaire=owner, locataire=locataire,
    defaults=dict(
        numero_contrat='CONTRAT-BASSAM-0001',
        date_debut=timezone.now().date() - timedelta(days=60),
        date_fin=timezone.now().date() + timedelta(days=305),
        date_signature=timezone.now() - timedelta(days=60),
        statut=Contrat.Statut.EN_COURS,
        prix_mensuel=350000, prix_depot_garantie=700000,
    )
)
print('OK contrat actif' if created else '  (déjà existant) contrat actif', '-> /contrats/%d/' % contrat.id)
villa.statut = Bien.Statut.LOUE
villa.save(update_fields=['statut'])

# ── Réclamation ouverte de Bintou sur la villa ──────────────────────────────
reclamation, created = Reclamation.objects.get_or_create(
    bien=villa, locataire=locataire, titre="Fuite d'eau sous l'évier",
    defaults=dict(description="Il y a une fuite persistante sous l'évier de la cuisine depuis 3 jours.", priorite=Reclamation.Priorite.URGENTE)
)
if created:
    NotificationService.send(
        destinataire=owner, expediteur=locataire, type_notification='reclamation',
        titre=f"Réclamation — {villa.titre}", message=reclamation.titre, lien='/dashboard/reclamations/',
    )
print('OK réclamation' if created else '  (déjà existante) réclamation')

# ── Visite en attente : fatimah (prospect) sur l'appartement ────────────────
visite, created = Visite.objects.get_or_create(
    bien=appartement, locataire=prospect, date_visite=timezone.now() + timedelta(days=3, hours=2),
    defaults=dict(notes="Disponible en semaine après 16h.")
)
if created:
    NotificationService.send(
        destinataire=owner, expediteur=prospect, type_notification='visite',
        titre=f"Demande de visite — {appartement.titre}",
        message=f"{prospect.get_full_name()} souhaite visiter le {visite.date_visite.strftime('%d/%m/%Y à %H:%M')}.",
        lien='/dashboard/rdv/',
    )
print('OK visite en attente' if created else '  (déjà existante) visite en attente')

# ── Favori : fatimah a mis le terrain en favori ─────────────────────────────
favori, created = BienFavori.objects.get_or_create(utilisateur=prospect, bien=terrain)
print('OK favori' if created else '  (déjà existant) favori')

# ── Conversation + message : fatimah a écrit à propos de l'appartement ──────
conv, created = Conversation.objects.get_or_create(
    bien=appartement, demandeur=prospect, defaults={'proprietaire': owner}
)
if created or not conv.messages.exists():
    msg = Message.objects.create(conversation=conv, expediteur=prospect, contenu="Bonjour, cet appartement est-il toujours disponible ?")
    conv.mis_a_jour_le = timezone.now()
    conv.save(update_fields=['mis_a_jour_le'])
    NotificationService.send(
        destinataire=owner, expediteur=prospect, type_notification='message',
        titre=f"Nouveau message de {prospect.get_full_name()}", message=msg.contenu, lien=f'/chat/{conv.id}/',
    )
    print('OK conversation + message')
else:
    print('  (déjà existante) conversation')

print('\nTerminé. Connectez-vous en tant que Abejakings (propriétaire) ou Bintoudby (locataire) pour voir les exemples.')
