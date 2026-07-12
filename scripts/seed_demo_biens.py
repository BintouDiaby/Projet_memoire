"""
Crée des biens de démonstration correspondant aux cartes vitrines de landing_guest.html.
Usage: python scripts/seed_demo_biens.py
"""
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'immobilier_config.settings')
import django
django.setup()

from utilisateurs.models import Utilisateur, Company
from biens.models import Bien

# ── Entreprise ────────────────────────────────────────────────────────────────
company, _ = Company.objects.get_or_create(
    name='Azimuts SARL',
    defaults={'types': ['location', 'vente', 'construction']}
)

# ── Utilisateur propriétaire ──────────────────────────────────────────────────
proprietaire, created = Utilisateur.objects.get_or_create(
    username='azimuts_demo',
    defaults={
        'first_name': 'Azimuts',
        'last_name': 'SARL',
        'email': 'contact@azimuts-demo.ci',
        'role': Utilisateur.Role.PROPRIETAIRE,
        'company': company,
        'telephone': '0707000001',
        'documents_verifies': True,
    }
)
if created:
    proprietaire.set_password('demo1234!')
    proprietaire.save()
    print('Propriétaire créé : azimuts_demo / demo1234!')
else:
    print('Propriétaire déjà existant : azimuts_demo')

# ── Biens ─────────────────────────────────────────────────────────────────────
BIENS = [
    {
        'titre': 'Appartement F4 meublé – Riviera',
        'description': 'Bel appartement F4 entièrement meublé, climatisé, avec parking et gardien. Idéal pour famille ou expatriés.',
        'type_bien': Bien.TypeBien.APPARTEMENT,
        'transaction_type': Bien.TransactionType.LOCATION,
        'adresse': 'Riviera, Cocody',
        'quartier': 'Riviera',
        'commune': 'Cocody',
        'ville': 'Abidjan',
        'surface_m2': 120,
        'nombre_chambres': 4,
        'nombre_salles_bain': 2,
        'nombre_etages': 3,
        'prix_mensuel': 450000,
        'prix_depot_garantie': 900000,
        'equipements': ['Climatisation', 'Parking', 'Gardien', 'Cuisine équipée', 'Balcon'],
        'latitude': 5.3670,
        'longitude': -3.9591,
    },
    {
        'titre': 'Villa basse 5 pièces + piscine – Riviera Golf',
        'description': 'Splendide villa basse avec piscine privée, jardin arboré, 5 chambres, double garage. Quartier résidentiel sécurisé.',
        'type_bien': Bien.TypeBien.MAISON_BASSE,
        'transaction_type': Bien.TransactionType.VENTE,
        'adresse': 'Riviera Golf, Cocody',
        'quartier': 'Riviera Golf',
        'commune': 'Cocody',
        'ville': 'Abidjan',
        'surface_m2': 380,
        'nombre_chambres': 5,
        'nombre_salles_bain': 3,
        'nombre_etages': 1,
        'prix_mensuel': 0,
        'prix_vente': 95000000,
        'prix_depot_garantie': 0,
        'equipements': ['Piscine', 'Jardin', 'Double garage', 'Climatisation', 'Groupe électrogène'],
        'latitude': 5.3750,
        'longitude': -3.9512,
    },
    {
        'titre': 'Terrain 500 m² titré ACD – Bingerville',
        'description': 'Terrain viabilisé de 500 m², titre foncier ACD disponible. Eau, électricité sur la parcelle. Idéal pour construction.',
        'type_bien': Bien.TypeBien.TERRAIN,
        'transaction_type': Bien.TransactionType.VENTE,
        'adresse': 'Bingerville Centre',
        'quartier': 'Centre',
        'commune': 'Bingerville',
        'ville': 'Abidjan',
        'surface_m2': 500,
        'nombre_chambres': 0,
        'nombre_salles_bain': 0,
        'nombre_etages': 1,
        'prix_mensuel': 0,
        'prix_vente': 18000000,
        'prix_depot_garantie': 0,
        'equipements': ['Eau', 'Électricité', 'Titre ACD'],
        'latitude': 5.3547,
        'longitude': -3.8768,
    },
    {
        'titre': 'Boutique 60 m² sur grande voie – Yopougon',
        'description': 'Local commercial de 60 m² en rez-de-chaussée sur axe passant. Grande vitrine, accès facile, eau et électricité.',
        'type_bien': Bien.TypeBien.BOUTIQUE,
        'transaction_type': Bien.TransactionType.LOCATION,
        'adresse': 'Grande voie, Yopougon',
        'quartier': 'Kouté',
        'commune': 'Yopougon',
        'ville': 'Abidjan',
        'surface_m2': 60,
        'nombre_chambres': 0,
        'nombre_salles_bain': 1,
        'nombre_etages': 1,
        'prix_mensuel': 250000,
        'prix_depot_garantie': 500000,
        'equipements': ['Grande vitrine', 'Eau', 'Électricité', 'Toilettes'],
        'latitude': 5.3433,
        'longitude': -4.0714,
    },
    {
        'titre': 'Studio meublé Zone 4 – Marcory',
        'description': 'Studio tout équipé, climatisé, en résidence sécurisée. Idéal pour célibataire ou étudiant. Proche commerces et transports.',
        'type_bien': Bien.TypeBien.STUDIO,
        'transaction_type': Bien.TransactionType.LOCATION,
        'adresse': 'Zone 4, Marcory',
        'quartier': 'Zone 4',
        'commune': 'Marcory',
        'ville': 'Abidjan',
        'surface_m2': 38,
        'nombre_chambres': 1,
        'nombre_salles_bain': 1,
        'nombre_etages': 2,
        'prix_mensuel': 180000,
        'prix_depot_garantie': 360000,
        'equipements': ['Climatisation', 'Meublé', 'Sécurité 24h/24', 'Eau chaude'],
        'latitude': 5.3054,
        'longitude': -3.9981,
    },
    {
        'titre': 'Les Jardins de Bingerville – Projet 24 villas',
        'description': 'Résidence haut standing de 24 villas, livraison prévue en 2027. Paiement échelonné possible. Titre foncier garanti.',
        'type_bien': Bien.TypeBien.RESIDENCE,
        'transaction_type': Bien.TransactionType.VENTE,
        'adresse': 'Route de Bingerville',
        'quartier': 'Jardins',
        'commune': 'Bingerville',
        'ville': 'Abidjan',
        'surface_m2': 200,
        'nombre_chambres': 4,
        'nombre_salles_bain': 2,
        'nombre_etages': 2,
        'prix_mensuel': 0,
        'prix_vente': 25000000,
        'prix_depot_garantie': 0,
        'equipements': ['Titre foncier', 'Gardiennage', 'Espace vert', 'Paiement échelonné'],
        'latitude': 5.3547,
        'longitude': -3.8800,
    },
]

created_count = 0
for data in BIENS:
    if Bien.objects.filter(titre=data['titre']).exists():
        print(f'  (déjà existant) {data["titre"]}')
        continue
    prix_vente = data.pop('prix_vente', None)
    equipements = data.pop('equipements', [])
    b = Bien(
        proprietaire=proprietaire,
        statut=Bien.Statut.DISPONIBLE,
        photo_principale='',
        **data,
    )
    if prix_vente:
        b.prix_vente = prix_vente
    b.equipements = equipements
    b.full_clean(exclude=['photo_principale'])
    b.save()
    created_count += 1
    print(f'  OK {b.titre} -> /biens/{b.id}/')

print(f'\n{created_count} bien(s) crees. Actualisez la page d\'accueil.')
