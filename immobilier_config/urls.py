"""
URL configuration for immobilier_config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Q
from django.core.paginator import Paginator
from django.utils import timezone
from utilisateurs import views as utilisateurs_views
from dashboard import views as dashboard_views
from biens import views as biens_views
from contrats import views as contrats_views
from django.http import JsonResponse, HttpResponse

# Importer modèles pour métriques de la page d'accueil
from utilisateurs.models import Utilisateur
from biens.models import Bien
from contrats.models import Contrat, Paiement
from facturation.models import Facture


def _haversine_km(lat1, lng1, lat2, lng2):
    """Distance à vol d'oiseau entre deux points GPS, en kilomètres."""
    import math
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def home(request):
    """Page d'accueil : redirige vers login si non-authentifié, vers onboarding si profil incomplet, sinon dashboard."""
    if not request.user.is_authenticated:
        # Visiteur anonyme → afficher une landing publique avec CTA vers login/signup
        utilisateurs_count = Utilisateur.objects.count()
        biens_count = Bien.objects.count()
        contrats_count = Contrat.objects.filter(statut=Contrat.Statut.EN_COURS).count()
        landing_context = {
            'stats': {
                'utilisateurs_actifs': utilisateurs_count,
                'biens_total': biens_count,
                'contrats_actifs': contrats_count,
            }
        }
        return render(request, 'landing.html', landing_context)

    # Rediriger selon le rôle — logique unique centralisée
    role = request.user.role
    company = getattr(request.user, 'company', None)

    if role == Utilisateur.Role.LOCATAIRE:
        return redirect('guest_landing')
    if role in (Utilisateur.Role.PROPRIETAIRE, Utilisateur.Role.GESTIONNAIRE):
        if company and getattr(company, 'types', None):
            return redirect('dashboard_company')
        return redirect('onboarding')
    if role == Utilisateur.Role.ADMIN or request.user.is_superuser:
        return redirect('dashboard_company')
    
    # Calculer métriques dynamiques
    utilisateurs_count = Utilisateur.objects.count()
    biens_count = Bien.objects.count()
    contrats_count = Contrat.objects.filter(statut=Contrat.Statut.EN_COURS).count()

    # Paiements en attente / retard
    paiements_a_suivre = Paiement.objects.filter(~Q(statut=Paiement.Statut.RECU)).order_by('date_limite')[:5]
    # Somme des montants non reçus
    montant_out = Paiement.objects.filter(~Q(statut=Paiement.Statut.RECU)).aggregate(
        total_out=Sum(ExpressionWrapper(F('montant_du') - F('montant_recu'), output_field=DecimalField()))
    )['total_out'] or 0

    # Derniers éléments
    derniers_biens = Bien.objects.all()[:5]
    derniers_contrats = Contrat.objects.order_by('-date_creation')[:5]

    # Comportement spécifique pour les locataires
    locataire_context = {}
    try:
        if getattr(request.user, 'role', None) == 'locataire':
            contrats_locataire = Contrat.objects.filter(locataire=request.user).order_by('-date_creation')
            if contrats_locataire.exists():
                # Locataire existant
                paiements_prochains = Paiement.objects.filter(contrat__in=contrats_locataire, statut__in=(Paiement.Statut.EN_ATTENTE, Paiement.Statut.RETARD_MINEUR, Paiement.Statut.RETARD_MAJEUR)).order_by('date_limite')[:5]
                locataire_context.update({
                    'locataire_is_new': False,
                    'locataire_contrats': contrats_locataire,
                    'locataire_paiements_prochains': paiements_prochains,
                })
            else:
                # Nouveau locataire — montrer recommandations
                recommandations = Bien.objects.filter(statut=Bien.Statut.DISPONIBLE).order_by('-date_publication')[:8]
                locataire_context.update({
                    'locataire_is_new': True,
                    'locataire_recommandations': recommandations,
                })
    except Exception:
        # En cas d'erreur accessoire, ne pas bloquer l'affichage du dashboard
        locataire_context = {}

    context = {
        'message': '🎉 Plateforme Web de Gestion Locative',
        'version': '1.0.0',
        'status': 'API Running ✅',
        'utilisateurs_count': utilisateurs_count,
        'biens_count': biens_count,
        'contrats_actifs_count': contrats_count,
        'paiements_a_suivre': paiements_a_suivre,
        'montant_outstanding': montant_out,
        'derniers_biens': derniers_biens,
        'derniers_contrats': derniers_contrats,
        'home_stats': {
            'utilisateurs_count': utilisateurs_count,
            'biens_count': biens_count,
            'contrats_actifs_count': contrats_count,
            'montant_outstanding': float(montant_out) if montant_out is not None else 0
        },
        'endpoints': {
            'admin': 'http://127.0.0.1:8000/admin/',
            'api_utilisateurs': 'http://127.0.0.1:8000/api/utilisateurs/',
            'api_biens': 'http://127.0.0.1:8000/api/biens/',
            'api_contrats': 'http://127.0.0.1:8000/api/contrats/',
            'api_facturation': 'http://127.0.0.1:8000/api/facturation/',
            'api_recherche': 'http://127.0.0.1:8000/api/recherche/',
            'api_dashboard': 'http://127.0.0.1:8000/api/dashboard/',
        },
        'documentation': {
            'guide': 'GUIDE_DEMARRAGE.md',
            'quick_ref': 'QUICK_REFERENCE.md',
            'architecture': 'ARCHITECTURE.md'
        }
    }
    # Fusionner le contexte spécifique locataire si présent
    context.update(locataire_context)
    return render(request, 'home.html', context)


def landing_page(request):
    """Landing publique accessible via /landing/ (statistiques minimales).
    Un utilisateur déjà connecté ne doit jamais retomber sur cette page
    marketing anonyme — on le renvoie vers son espace approprié."""
    if request.user.is_authenticated:
        role = getattr(request.user, 'role', None)
        if role in (Utilisateur.Role.PROPRIETAIRE, Utilisateur.Role.GESTIONNAIRE, Utilisateur.Role.ADMIN) or request.user.is_superuser:
            return redirect('dashboard_company')
        return redirect('guest_landing')

    utilisateurs_count = Utilisateur.objects.count()
    biens_count = Bien.objects.count()
    contrats_count = Contrat.objects.filter(statut=Contrat.Statut.EN_COURS).count()
    context = {
        'stats': {
            'utilisateurs_actifs': utilisateurs_count,
            'biens_total': biens_count,
            'contrats_actifs': contrats_count,
        }
    }
    return render(request, 'landing.html', context)


def guest_landing(request):
    """Page publique dédiée aux invités et locataires.
    Les propriétaires/gestionnaires/admin sont redirigés vers leur dashboard.
    """
    if request.user.is_authenticated:
        role = getattr(request.user, 'role', None)
        if role in (Utilisateur.Role.PROPRIETAIRE, Utilisateur.Role.GESTIONNAIRE, Utilisateur.Role.ADMIN) or request.user.is_superuser:
            return redirect('dashboard_company')

    from utilisateurs.models import Company

    biens_vedette = (
        Bien.objects.filter(statut=Bien.Statut.DISPONIBLE)
        .select_related('proprietaire__company')
        .order_by('-date_creation')[:6]
    )

    nb_biens_dispo = Bien.objects.filter(statut=Bien.Statut.DISPONIBLE).count()
    nb_locations = Bien.objects.filter(statut=Bien.Statut.DISPONIBLE, transaction_type__in=['location', 'both']).count()
    nb_ventes = Bien.objects.filter(statut=Bien.Statut.DISPONIBLE, transaction_type__in=['vente', 'both']).count()
    nb_terrains = Bien.objects.filter(statut=Bien.Statut.DISPONIBLE, type_bien='terrain').count()
    nb_magasins = Bien.objects.filter(statut=Bien.Statut.DISPONIBLE, type_bien__in=['magasin', 'boutique', 'local_commercial']).count()
    nb_bureaux = Bien.objects.filter(statut=Bien.Statut.DISPONIBLE, type_bien='bureau').count()
    nb_projets = Bien.objects.filter(statut=Bien.Statut.DISPONIBLE, type_bien__in=['immeuble', 'residence']).count()
    nb_entreprises = Company.objects.count()

    entreprises_vedette = []
    # Vitrine volontairement limitée aux deux entreprises de démonstration
    # principales (Abeja King, Azimuts SARL) — toujours lu en base, jamais
    # de nom en dur.
    for nom in ('Abeja King', 'Azimuts SARL'):
        candidats = Company.objects.filter(name=nom)
        meilleure, meilleur_nb = None, -1
        for c in candidats:
            nb_biens_c = Bien.objects.filter(proprietaire__company=c, statut=Bien.Statut.DISPONIBLE).count()
            if nb_biens_c > meilleur_nb:
                meilleure, meilleur_nb = c, nb_biens_c
        if meilleure:
            entreprises_vedette.append({
                'company': meilleure,
                'nb_biens': meilleur_nb,
                'verifie': meilleure.users.filter(documents_verifies=True).exists(),
            })

    COMMUNES_ABIDJAN = [
        'Abobo', 'Adjamé', 'Anyama', 'Attécoubé', 'Bingerville',
        'Cocody', 'Koumassi', 'Marcory', 'Plateau', 'Port-Bouët',
        'Songon', 'Treichville', 'Yopougon',
    ]

    context = {
        'biens': biens_vedette,
        'nb_biens_dispo': nb_biens_dispo,
        'nb_locations': nb_locations,
        'nb_ventes': nb_ventes,
        'nb_terrains': nb_terrains,
        'nb_magasins': nb_magasins,
        'nb_bureaux': nb_bureaux,
        'nb_projets': nb_projets,
        'nb_entreprises': nb_entreprises,
        'entreprises_vedette': entreprises_vedette,
        'communes_list': COMMUNES_ABIDJAN,
        'stats': {
            'utilisateurs_actifs': Utilisateur.objects.count(),
            'biens_total': Bien.objects.count(),
            'contrats_actifs': Contrat.objects.filter(statut=Contrat.Statut.EN_COURS).count(),
        }
    }
    return render(request, 'landing_guest.html', context)


def centre_aide(request):
    """Centre d'aide public : FAQ groupée par catégorie + accès rapide au support."""
    from .faq_data import FAQ_CATEGORIES
    return render(request, 'centre_aide.html', {'categories': FAQ_CATEGORIES})


def guest_debug(request):
    """Page de debug minimale pour vérifier le rendu CSS côté navigateur."""
    html = '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>guest-debug</title></head><body style="background:#ff00aa;color:#ffffff;font-family:Arial,sans-serif"><div style="padding:32px;font-size:18px">DEBUG CSS: fond magenta appliqué — si vous voyez ceci, le CSS inline est rendu.</div></body></html>'''
    return HttpResponse(html)


def explorer_view(request):
    """Marketplace publique avec onglets par catégorie de bien."""
    TYPES_RESIDENTIEL = ['maison', 'maison_basse', 'duplex', 'appartement', 'studio', 't1', 't2', 't3', 't4', 't5plus']
    TYPES_COMMERCIAL = ['magasin', 'boutique', 'local_commercial', 'entrepot']
    TYPES_CONSTRUCTION = ['immeuble', 'residence']

    TAB_FILTER = {
        'locations': Q(transaction_type__in=['location', 'both']),
        'vente': Q(transaction_type__in=['vente', 'both']) & Q(type_bien__in=TYPES_RESIDENTIEL),
        'terrains': Q(type_bien='terrain'),
        'magasins': Q(type_bien__in=TYPES_COMMERCIAL),
        'bureaux': Q(type_bien='bureau'),
        'construction': Q(type_bien__in=TYPES_CONSTRUCTION),
    }

    tab = request.GET.get('tab', 'locations')
    if tab == 'construction':
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect('/construction/')
    if tab not in TAB_FILTER:
        tab = 'locations'

    import json as _json

    q = request.GET.get('q', '').strip()
    ville_filtre = request.GET.get('ville', '').strip()
    commune_filtre = request.GET.get('commune', '').strip()
    budget_max = request.GET.get('budget_max', '').strip()
    chambres = request.GET.get('chambres', '').strip()
    vue = request.GET.get('vue', 'liste')  # 'liste' ou 'carte'

    def to_float_or_none(raw):
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    user_lat = to_float_or_none(request.GET.get('lat', '').strip())
    user_lng = to_float_or_none(request.GET.get('lng', '').strip())
    autour_de_moi = user_lat is not None and user_lng is not None
    distance_max = request.GET.get('distance_max', '').strip()

    qs = Bien.objects.filter(statut=Bien.Statut.DISPONIBLE).filter(TAB_FILTER[tab]).select_related('proprietaire__company')

    if q:
        qs = qs.filter(Q(titre__icontains=q) | Q(adresse__icontains=q) | Q(ville__icontains=q) | Q(quartier__icontains=q) | Q(commune__icontains=q))
    if ville_filtre:
        qs = qs.filter(ville__icontains=ville_filtre)
    if commune_filtre:
        qs = qs.filter(commune__iexact=commune_filtre)
    if budget_max:
        try:
            bmax = float(budget_max)
            if tab in ('vente', 'terrains', 'construction'):
                qs = qs.filter(Q(prix_vente__lte=bmax) | Q(prix_mensuel__lte=bmax))
            else:
                qs = qs.filter(prix_mensuel__lte=bmax)
        except ValueError:
            pass
    if chambres:
        try:
            qs = qs.filter(nombre_chambres__gte=int(chambres))
        except ValueError:
            pass

    if autour_de_moi:
        # Mode « autour de moi » : seuls les biens géolocalisés comptent, triés
        # par distance croissante. On calcule en Python (distance à vol d'oiseau,
        # aucune fonction trigonométrique fiable côté SQLite).
        biens_proches = list(qs.exclude(latitude=None, longitude=None).order_by('-date_publication'))
        for b in biens_proches:
            b.distance_km = _haversine_km(user_lat, user_lng, b.latitude, b.longitude)
        # « Toute la Côte d'Ivoire » (distance_max='all') retire toute limite ;
        # sinon on applique toujours une limite réelle, avec 20 km par défaut
        # si l'utilisateur n'a rien choisi (au lieu de ne rien filtrer du tout).
        if distance_max != 'all':
            dmax = to_float_or_none(distance_max) or 20
            biens_proches = [b for b in biens_proches if b.distance_km <= dmax]
        biens_proches.sort(key=lambda b: b.distance_km)
        paginator = Paginator(biens_proches, 12)
        page_obj = paginator.get_page(request.GET.get('page', 1))
    else:
        qs = qs.order_by('-date_publication', '-date_creation')
        paginator = Paginator(qs, 12)
        page_obj = paginator.get_page(request.GET.get('page', 1))

    # Données carte : tous les biens avec coordonnées GPS (pas paginés)
    biens_carte = []
    for b in qs.exclude(latitude=None, longitude=None).values(
        'id', 'titre', 'ville', 'commune', 'quartier',
        'latitude', 'longitude', 'prix_mensuel', 'prix_vente',
        'transaction_type', 'photo_principale'
    ):
        biens_carte.append({
            'id': b['id'],
            'titre': b['titre'],
            'lieu': ', '.join(filter(None, [b['commune'] or '', b['ville'] or ''])),
            'lat': b['latitude'],
            'lng': b['longitude'],
            'prix': float(b['prix_mensuel'] or b['prix_vente'] or 0),
            'type_tx': b['transaction_type'],
            'url': f"/biens/{b['id']}/",
        })

    base_qs = Bien.objects.filter(statut=Bien.Statut.DISPONIBLE)
    tabs_info = [
        {'key': 'locations',    'label': 'Locations',              'count': base_qs.filter(transaction_type__in=['location', 'both']).count()},
        {'key': 'vente',        'label': 'Maisons à vendre',       'count': base_qs.filter(transaction_type__in=['vente', 'both'], type_bien__in=TYPES_RESIDENTIEL).count()},
        {'key': 'terrains',     'label': 'Terrains',               'count': base_qs.filter(type_bien='terrain').count()},
        {'key': 'magasins',     'label': 'Magasins',               'count': base_qs.filter(type_bien__in=TYPES_COMMERCIAL).count()},
        {'key': 'bureaux',      'label': 'Bureaux',                'count': base_qs.filter(type_bien='bureau').count()},
        {'key': 'construction', 'label': 'Projets en construction', 'count': base_qs.filter(type_bien__in=TYPES_CONSTRUCTION).count()},
    ]

    villes = base_qs.values_list('ville', flat=True).distinct().order_by('ville')
    communes = (
        base_qs.exclude(commune='').exclude(commune=None)
        .values_list('commune', flat=True).distinct().order_by('commune')
    )

    # Communes d'Abidjan prédéfinies (toujours présentes dans le filtre)
    COMMUNES_ABIDJAN = [
        'Abobo', 'Adjamé', 'Anyama', 'Attécoubé', 'Bingerville',
        'Cocody', 'Koumassi', 'Marcory', 'Plateau', 'Port-Bouët',
        'Songon', 'Treichville', 'Yopougon',
    ]
    communes_list = sorted(set(list(communes) + COMMUNES_ABIDJAN))

    favoris_ids = set()
    if request.user.is_authenticated:
        from recherche.models import BienFavori
        favoris_ids = set(
            BienFavori.objects.filter(utilisateur=request.user, bien__in=page_obj.object_list)
            .values_list('bien_id', flat=True)
        )

    return render(request, 'explorer.html', {
        'tab': tab,
        'biens': page_obj,
        'tabs': tabs_info,
        'villes': villes,
        'communes': communes_list,
        'q': q,
        'ville_filtre': ville_filtre,
        'commune_filtre': commune_filtre,
        'budget_max': budget_max,
        'chambres': chambres,
        'total': paginator.count,
        'has_filters': bool(q or ville_filtre or commune_filtre or budget_max or chambres),
        'vue': vue,
        'biens_carte_json': _json.dumps(biens_carte),
        'favoris_ids': favoris_ids,
        'autour_de_moi': autour_de_moi,
        'user_lat': user_lat,
        'user_lng': user_lng,
        'distance_max': distance_max,
    })


def annuaire_entreprises(request):
    """Annuaire public des entreprises actives sur la plateforme (location, vente, construction)."""
    from utilisateurs.models import Company

    q = request.GET.get('q', '').strip()
    companies = Company.objects.all().order_by('name')
    if q:
        companies = companies.filter(name__icontains=q)

    entreprises = []
    for c in companies:
        nb_biens = Bien.objects.filter(proprietaire__company=c, statut=Bien.Statut.DISPONIBLE).count()
        est_construction = 'construction' in (c.types or [])
        if nb_biens == 0 and not est_construction:
            continue  # entreprise sans activité visible côté client
        contact = c.users.first()
        entreprises.append({
            'company': c,
            'nb_biens': nb_biens,
            'est_construction': est_construction,
            'verifie': bool(contact and contact.documents_verifies),
        })

    return render(request, 'entreprises/liste.html', {
        'entreprises': entreprises,
        'q': q,
        'total': len(entreprises),
    })


def entreprise_publique_detail(request, company_id):
    """Fiche publique d'une entreprise : coordonnées + biens publiés."""
    from utilisateurs.models import Company, ProprietaireProfile

    company = get_object_or_404(Company, id=company_id)
    contact = company.users.first()
    biens_qs = Bien.objects.filter(proprietaire__company=company).select_related('proprietaire')
    biens = biens_qs.filter(statut=Bien.Statut.DISPONIBLE).order_by('-date_publication')

    numero_rccm = company.numero_rccm or None
    if not numero_rccm and contact:
        prof = ProprietaireProfile.objects.filter(utilisateur=contact).first()
        if prof and prof.numero_siret_siren:
            numero_rccm = prof.numero_siret_siren

    zones = sorted({v for v in biens_qs.exclude(ville__isnull=True).exclude(ville='').values_list('ville', flat=True)})
    nb_locations = Contrat.objects.filter(proprietaire__company=company, statut=Contrat.Statut.EN_COURS).count()

    avis_liste = list(company.avis.select_related('auteur').all())
    nb_avis = len(avis_liste)
    note_moyenne_entreprise = round(sum(a.note for a in avis_liste) / nb_avis, 1) if nb_avis else None
    mon_avis_entreprise = None
    peut_noter_entreprise = False
    if request.user.is_authenticated and request.user.role == Utilisateur.Role.LOCATAIRE:
        mon_avis_entreprise = next((a for a in avis_liste if a.auteur_id == request.user.id), None)
        if mon_avis_entreprise is None:
            peut_noter_entreprise = Contrat.objects.filter(
                proprietaire__company=company, locataire=request.user
            ).exclude(statut__in=[Contrat.Statut.BROUILLON, Contrat.Statut.EN_ATTENTE_SIGNATURE]).exists()

    horaires_affichage = [
        {'jour': j, 'horaire': company.horaires.get(j, '')}
        for j in Company.JOURS_SEMAINE
    ] if company.horaires else []

    return render(request, 'entreprises/detail.html', {
        'company': company,
        'contact': contact,
        'biens': biens,
        'verifie': bool(contact and contact.documents_verifies),
        'est_construction': 'construction' in (company.types or []),
        'numero_rccm': numero_rccm,
        'zones': zones,
        'nb_biens_total': biens_qs.count(),
        'nb_locations': nb_locations,
        'avis_liste': avis_liste,
        'nb_avis': nb_avis,
        'note_moyenne_entreprise': note_moyenne_entreprise,
        'mon_avis_entreprise': mon_avis_entreprise,
        'peut_noter_entreprise': peut_noter_entreprise,
        'statut_dispo': company.statut_actuel(),
        'horaires_affichage': horaires_affichage,
    })


def avis_entreprise_ajouter(request, company_id):
    """Un locataire ayant réellement loué un bien de cette entreprise laisse
    une note + un commentaire. Un seul avis par locataire et par entreprise."""
    from django.contrib import messages
    from utilisateurs.models import Company, AvisEntreprise

    if not request.user.is_authenticated:
        return redirect('login')

    company = get_object_or_404(Company, id=company_id)
    next_url = request.POST.get('next') or f'/entreprises/{company_id}/'

    if request.method == 'POST':
        if request.user.role != Utilisateur.Role.LOCATAIRE:
            messages.error(request, "Seuls les locataires peuvent laisser un avis.")
            return redirect(next_url)

        a_loue = Contrat.objects.filter(proprietaire__company=company, locataire=request.user).exclude(
            statut__in=[Contrat.Statut.BROUILLON, Contrat.Statut.EN_ATTENTE_SIGNATURE]
        ).exists()
        if not a_loue:
            messages.error(request, "Vous ne pouvez laisser un avis que sur une entreprise dont vous avez loué un bien.")
            return redirect(next_url)

        if AvisEntreprise.objects.filter(company=company, auteur=request.user).exists():
            messages.error(request, "Vous avez déjà laissé un avis sur cette entreprise.")
            return redirect(next_url)

        try:
            note = int(request.POST.get('note', ''))
        except (TypeError, ValueError):
            note = 0
        commentaire = request.POST.get('commentaire', '').strip()
        if note < 1 or note > 5 or not commentaire:
            messages.error(request, "Merci de choisir une note (1 à 5) et d'écrire un commentaire.")
            return redirect(next_url)

        AvisEntreprise.objects.create(company=company, auteur=request.user, note=note, commentaire=commentaire)
        messages.success(request, "Merci, votre avis a été publié.")

    return redirect(next_url)


def avis_entreprise_supprimer(request, avis_id):
    """L'auteur supprime son propre avis sur une entreprise."""
    from django.contrib import messages
    from utilisateurs.models import AvisEntreprise

    if not request.user.is_authenticated:
        return redirect('login')

    avis = AvisEntreprise.objects.filter(id=avis_id, auteur=request.user).first()
    next_url = request.POST.get('next') or (f'/entreprises/{avis.company_id}/' if avis else '/entreprises/')
    if request.method == 'POST' and avis:
        avis.delete()
        messages.success(request, "Votre avis a été supprimé.")
    return redirect(next_url)


def mon_espace_locataire(request):
    """Espace privé du locataire : contrat actif, paiements, factures, favoris."""
    from facturation.models import Facture

    if not request.user.is_authenticated:
        return redirect('login')
    if request.user.role != Utilisateur.Role.LOCATAIRE:
        return redirect('dashboard')

    user = request.user
    today = timezone.now().date()
    mois_actuel = today.replace(day=1)

    # Contrats actifs (une personne peut louer plusieurs biens à la fois)
    contrats_actifs = list(
        Contrat.objects.filter(locataire=user, statut=Contrat.Statut.EN_COURS)
        .select_related('bien', 'proprietaire', 'proprietaire__company')
        .order_by('date_debut')
    )
    contrat_actif = contrats_actifs[0] if contrats_actifs else None

    # Tous les contrats (historique)
    tous_contrats = (
        Contrat.objects.filter(locataire=user)
        .select_related('bien')
        .order_by('-date_creation')
    )

    # Historique des paiements : mois passés/actuel uniquement (pas les
    # échéances futures déjà générées à l'avance), du plus ancien au plus récent.
    paiements_recents = list(reversed(
        Paiement.objects.filter(contrat__locataire=user, mois__lte=mois_actuel)
        .select_related('contrat__bien')
        .order_by('-mois')[:6]
    ))

    # Paiement du mois en cours, pour chaque contrat actif
    paiements_du_mois = {
        p.contrat_id: p
        for p in Paiement.objects.filter(contrat__in=contrats_actifs, mois=mois_actuel)
    }
    for c in contrats_actifs:
        c.paiement_du_mois = paiements_du_mois.get(c.id)

    paiement_du_mois = contrats_actifs[0].paiement_du_mois if contrats_actifs else None
    nb_contrats_payes_ce_mois = sum(1 for c in contrats_actifs if c.paiement_du_mois and c.paiement_du_mois.statut == Paiement.Statut.RECU)
    total_loyer_mensuel = sum(c.prix_mensuel for c in contrats_actifs)

    # Carte de mes logements : un point par contrat actif dont le bien a des coordonnées GPS
    import json as _json
    logements_carte = []
    for c in contrats_actifs:
        if c.bien.latitude is None or c.bien.longitude is None:
            continue
        logements_carte.append({
            'titre': c.bien.titre,
            'lieu': ', '.join(filter(None, [c.bien.commune or '', c.bien.ville or ''])),
            'lat': c.bien.latitude,
            'lng': c.bien.longitude,
            'loyer': float(c.prix_mensuel or 0),
            'statut': c.paiement_du_mois.statut if c.paiement_du_mois else '',
            'url': f'/contrats/{c.id}/suivi/',
        })
    logements_carte_json = _json.dumps(logements_carte)
    nb_logements_sans_localisation = sum(1 for c in contrats_actifs if c.bien.latitude is None or c.bien.longitude is None)

    # Prochain paiement en attente
    prochain_paiement = (
        Paiement.objects.filter(
            contrat__locataire=user,
            statut=Paiement.Statut.EN_ATTENTE
        )
        .order_by('date_limite')
        .first()
    )

    # Paiements en retard
    paiements_retard = Paiement.objects.filter(
        contrat__locataire=user,
        statut__in=[Paiement.Statut.RETARD_MINEUR, Paiement.Statut.RETARD_MAJEUR, Paiement.Statut.IMPAYE]
    )
    nb_retards = paiements_retard.count()
    montant_retard = paiements_retard.aggregate(total=Sum('montant_du'))['total'] or 0

    # Mise(s) en demeure en cours — alerte prioritaire sur le simple retard
    from contrats.models import MiseEnDemeure
    mise_en_demeure_active = (
        MiseEnDemeure.objects.filter(
            contrat__locataire=user,
            statut__in=[MiseEnDemeure.Statut.ENVOYEE, MiseEnDemeure.Statut.DELAI_SUPPLEMENTAIRE, MiseEnDemeure.Statut.EXPIREE],
        )
        .select_related('paiement__facture', 'contrat__bien')
        .order_by('-date_creation')
        .first()
    )
    facture_mise_en_demeure = getattr(mise_en_demeure_active.paiement, 'facture', None) if mise_en_demeure_active else None

    # Factures récentes
    factures_recentes = (
        Facture.objects.filter(contrat__locataire=user)
        .order_by('-date_generation')[:4]
    )

    # Favoris
    try:
        nb_favoris = user.biens_favoris.count()
    except Exception:
        nb_favoris = 0

    # Biens recommandés (si pas de contrat actif)
    biens_recommandes = []
    if not contrat_actif:
        biens_recommandes = (
            Bien.objects.filter(statut=Bien.Statut.DISPONIBLE, transaction_type__in=['location', 'both'])
            .order_by('-date_publication')[:4]
        )

    from dashboard.models import Notification
    from dashboard.services import NotificationService
    notifications = list(
        Notification.objects.filter(destinataire=user).select_related('expediteur').order_by('-date_creation')[:10]
    )
    nb_notifs = NotificationService.unread_count(user)

    from messagerie.models import Conversation
    nb_messages_non_lus = sum(
        conv.messages.filter(lu=False).exclude(expediteur=user).count()
        for conv in Conversation.objects.filter(demandeur=user)
    )

    from contrats.models import Reclamation
    nb_reclamations_actives = Reclamation.objects.filter(
        locataire=user, statut__in=[Reclamation.Statut.OUVERTE, Reclamation.Statut.EN_COURS]
    ).count()

    return render(request, 'mon_espace_locataire.html', {
        'nb_messages_non_lus': nb_messages_non_lus,
        'nb_reclamations_actives': nb_reclamations_actives,
        'contrat_actif': contrat_actif,
        'contrats_actifs': contrats_actifs,
        'nb_contrats_payes_ce_mois': nb_contrats_payes_ce_mois,
        'total_loyer_mensuel': total_loyer_mensuel,
        'logements_carte_json': logements_carte_json,
        'nb_logements_sans_localisation': nb_logements_sans_localisation,
        'tous_contrats': tous_contrats,
        'paiements_recents': paiements_recents,
        'paiement_du_mois': paiement_du_mois,
        'prochain_paiement': prochain_paiement,
        'nb_retards': nb_retards,
        'montant_retard': montant_retard,
        'mise_en_demeure_active': mise_en_demeure_active,
        'facture_mise_en_demeure': facture_mise_en_demeure,
        'factures_recentes': factures_recentes,
        'nb_favoris': nb_favoris,
        'biens_recommandes': biens_recommandes,
        'notifications': notifications,
        'nb_notifs': nb_notifs,
        'today': today,
        'mois_actuel': mois_actuel,
    })


def mon_profil(request):
    """Profil public du locataire : identité, préférences de recherche, activité, documents."""
    from utilisateurs.models import LocataireProfile
    from recherche.models import RechercheSauvegardee, BienFavori
    from biens.models import Visite, Reservation
    from contrats.models import DocumentContrat
    from facturation.models import Facture

    if not request.user.is_authenticated:
        return redirect('login')
    if request.user.role != Utilisateur.Role.LOCATAIRE:
        return redirect('dashboard')

    user = request.user
    profile, _ = LocataireProfile.objects.get_or_create(utilisateur=user)

    recherche = (
        RechercheSauvegardee.objects.filter(utilisateur=user)
        .order_by('-date_derniere_recherche', '-date_creation')
        .first()
    )

    stats = {
        'locations': Contrat.objects.filter(locataire=user).count(),
        'favoris': BienFavori.objects.filter(utilisateur=user).count(),
        'visites': Visite.objects.filter(locataire=user).count(),
        'reservations': Reservation.objects.filter(client=user).count(),
    }

    documents = {
        'identite_verifiee': user.documents_verifies,
        'nb_contrats_docs': DocumentContrat.objects.filter(contrat__locataire=user).count(),
        'nb_factures': Facture.objects.filter(contrat__locataire=user).count(),
    }

    return render(request, 'mon_profil.html', {
        'profile': profile,
        'recherche': recherche,
        'stats': stats,
        'documents': documents,
    })


def mon_profil_modifier(request):
    """Modification du profil locataire (identité + préférences de recherche)."""
    from utilisateurs.models import LocataireProfile

    if not request.user.is_authenticated:
        return redirect('login')
    if request.user.role != Utilisateur.Role.LOCATAIRE:
        return redirect('dashboard')

    user = request.user
    profile, _ = LocataireProfile.objects.get_or_create(utilisateur=user)

    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.telephone = request.POST.get('telephone', '').strip()
        user.ville = request.POST.get('ville', '').strip()
        user.bio = request.POST.get('bio', '').strip()
        user.save()

        profile.localisation_preferee = request.POST.get('localisation_preferee', '').strip()
        budget_max = request.POST.get('budget_max_mensuel', '').strip()
        if budget_max:
            from decimal import Decimal, InvalidOperation
            try:
                profile.budget_max_mensuel = Decimal(budget_max)
            except InvalidOperation:
                pass
        profile.save()

        from django.contrib import messages
        messages.success(request, "Votre profil a été mis à jour.")
        return redirect('mon_profil')

    return render(request, 'mon_profil_modifier.html', {'profile': profile})


NOTIF_CATEGORIES = ['messages', 'paiements', 'contrats', 'visites', 'devis']
NOTIF_LABELS = {
    'messages': 'Messages', 'paiements': 'Paiements', 'contrats': 'Contrats',
    'visites': 'Visites', 'devis': 'Devis',
}


def parametres(request):
    """Paramètres du compte locataire : infos générales, sécurité, notifications,
    confidentialité, documents, suppression du compte."""
    from django.contrib.auth.forms import PasswordChangeForm
    from django.contrib.auth import update_session_auth_hash, logout as auth_logout
    from django.contrib.sessions.models import Session
    from django.contrib import messages as dj_messages

    if not request.user.is_authenticated:
        return redirect('login')
    if request.user.role != Utilisateur.Role.LOCATAIRE:
        return redirect('dashboard')

    user = request.user
    password_form = None

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'general':
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            if email:
                user.email = email
            user.telephone = request.POST.get('telephone', '').strip()
            user.save()
            dj_messages.success(request, "Vos informations ont été mises à jour.")
            return redirect('parametres')

        elif action == 'password':
            password_form = PasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                dj_messages.success(request, "Mot de passe mis à jour.")
                return redirect('parametres')
            dj_messages.error(request, "Impossible de changer le mot de passe : vérifiez les champs ci-dessous.")

        elif action == 'notifications':
            prefs = dict(user.dashboard_preferences or {})
            prefs['notifications'] = {cat: (f'notif_{cat}' in request.POST) for cat in NOTIF_CATEGORIES}
            user.dashboard_preferences = prefs
            user.save(update_fields=['dashboard_preferences'])
            dj_messages.success(request, "Préférences de notification enregistrées.")
            return redirect('parametres')

        elif action == 'confidentialite':
            user.afficher_telephone = 'afficher_telephone' in request.POST
            user.afficher_email = 'afficher_email' in request.POST
            user.accepte_appels = 'accepte_appels' in request.POST
            user.save(update_fields=['afficher_telephone', 'afficher_email', 'accepte_appels'])
            dj_messages.success(request, "Préférences de confidentialité enregistrées.")
            return redirect('parametres')

        elif action == 'revoke_session':
            session_key = request.POST.get('session_key', '')
            if session_key and session_key != request.session.session_key:
                Session.objects.filter(pk=session_key).delete()
                dj_messages.success(request, "Session déconnectée.")
            return redirect('parametres')

        elif action == 'delete_account':
            confirm_text = request.POST.get('confirm_text', '').strip()
            if confirm_text != 'SUPPRIMER':
                dj_messages.error(request, "Tapez SUPPRIMER (en majuscules) pour confirmer la suppression.")
                return redirect('parametres')
            if Contrat.objects.filter(locataire=user, statut=Contrat.Statut.EN_COURS).exists():
                dj_messages.error(request, "Vous avez un contrat actif — il doit être clôturé avant la suppression de votre compte.")
                return redirect('parametres')
            auth_logout(request)
            user.delete()
            return redirect('landing')

    sessions = []
    for s in Session.objects.filter(expire_date__gte=timezone.now()):
        data = s.get_decoded()
        if str(data.get('_auth_user_id')) == str(user.id):
            sessions.append({
                'key': s.session_key,
                'is_current': s.session_key == request.session.session_key,
                'expire_date': s.expire_date,
            })
    sessions.sort(key=lambda s: s['is_current'], reverse=True)

    notif_prefs_raw = (user.dashboard_preferences or {}).get('notifications', {})
    notif_prefs = [
        {'key': cat, 'label': NOTIF_LABELS[cat], 'active': notif_prefs_raw.get(cat, True)}
        for cat in NOTIF_CATEGORIES
    ]

    if password_form is None:
        password_form = PasswordChangeForm(user)

    return render(request, 'parametres.html', {
        'sessions': sessions,
        'notif_prefs': notif_prefs,
        'password_form': password_form,
    })


def choisir_profil_entry(request):
    """Point d'entrée convivial pour les liens externes `/choisir-profil/?profil=...`.
    - `profil=invite|guest|visiteur` -> redirige vers la page invité `/guest/`
    - `profil=entreprise` -> redirige vers la page de choix (namespace `utilisateurs_ui:choix_profil`) en conservant le querystring
    - `profil=particulier` -> redirige vers la page de choix en conservant le querystring
    """
    p = (request.GET.get('profil') or '').lower()
    if p in ('invite', 'guest', 'visiteur'):
        return redirect('guest_landing')
    if p in ('entreprise', 'pro', 'proprietaire'):
        return redirect(reverse('company_signup'))
    # passer la requête au gestionnaire existant de l'app utilisateurs (choix de profil)
    # Conserver les paramètres de requête en redirigeant vers l'URL nommée
    target = reverse('utilisateurs_ui:choix_profil')
    if p:
        target = f"{target}?profil={p}"
    return redirect(target)

urlpatterns = [
    # Landing page publique à la racine
    path('', landing_page, name='landing'),
    path('choisir-profil/', choisir_profil_entry, name='choisir_profil'),
    path('guest/', guest_landing, name='guest_landing'),
    path('aide/', centre_aide, name='centre_aide'),
    path('explorer/', explorer_view, name='explorer'),
    path('entreprises/', annuaire_entreprises, name='annuaire_entreprises'),
    path('entreprises/<int:company_id>/', entreprise_publique_detail, name='entreprise_publique_detail'),
    path('entreprises/<int:company_id>/avis/', avis_entreprise_ajouter, name='avis_entreprise_ajouter'),
    path('avis-entreprise/<int:avis_id>/supprimer/', avis_entreprise_supprimer, name='avis_entreprise_supprimer'),
    path('mon-espace/', mon_espace_locataire, name='mon_espace_locataire'),
    path('mes-notifications/', dashboard_views.notifications_locataire_view, name='mes_notifications_locataire'),
    path('mon-profil/', mon_profil, name='mon_profil'),
    path('mon-profil/modifier/', mon_profil_modifier, name='mon_profil_modifier'),
    path('parametres/', parametres, name='parametres'),
    path('parametres/documents/contrats.zip', contrats_views.mes_contrats_zip, name='mes_contrats_zip'),
    path('accounts/signup/company/', utilisateurs_views.company_signup, name='company_signup'),
    path('guest-debug/', guest_debug, name='guest_debug'),
    path('dashboard/company/', dashboard_views.dashboard_company, name='dashboard_company'),
    path('dashboard/biens/', dashboard_views.mes_biens, name='dashboard_biens'),
    path('dashboard/rdv/', dashboard_views.rdv_view, name='dashboard_rdv'),
    path('dashboard/statistiques/', dashboard_views.statistiques_view, name='dashboard_statistiques'),
    path('dashboard/personnel/', dashboard_views.personnel_view, name='personnel'),
    path('dashboard/personnel/ajouter/', dashboard_views.ajouter_collaborateur, name='ajouter_collaborateur'),
    path('dashboard/personnel/<int:user_id>/modifier/', dashboard_views.modifier_collaborateur, name='modifier_collaborateur'),
    path('dashboard/personnel/<int:user_id>/toggle/', dashboard_views.toggle_collaborateur_actif, name='toggle_collaborateur_actif'),
    path('dashboard/personnel/<int:user_id>/reset-mdp/', dashboard_views.reinitialiser_mot_de_passe_collaborateur, name='reset_mdp_collaborateur'),
    path('dashboard/personnel/<int:user_id>/voir/', dashboard_views.voir_collaborateur, name='voir_collaborateur'),
    path('dashboard/personnel/<int:user_id>/taches/creer/', dashboard_views.creer_tache, name='creer_tache'),
    path('mes-taches/', dashboard_views.mes_taches_view, name='mes_taches'),
    path('mes-taches/<int:tache_id>/toggle/', dashboard_views.marquer_tache_faite, name='marquer_tache_faite'),
    path('dashboard/performances/', dashboard_views.performances_view, name='performances'),
    path('mes-conges/', dashboard_views.mes_conges_view, name='mes_conges'),
    path('dashboard/conges/', dashboard_views.conges_view, name='conges'),
    path('dashboard/conges/<int:conge_id>/traiter/', dashboard_views.traiter_conge, name='traiter_conge'),
    path('mon-planning/', dashboard_views.mon_planning_view, name='mon_planning'),
    path('dashboard/taches/', dashboard_views.taches_equipe_view, name='taches_equipe'),
    path('dashboard/planning/', dashboard_views.planning_equipe_view, name='planning_equipe'),
    path('dashboard/reservations/', biens_views.dashboard_reservations, name='dashboard_reservations'),
    path('dashboard/rdv/visite/<int:visite_id>/annulation/', biens_views.traiter_annulation_visite, name='traiter_annulation_visite'),
    path('dashboard/notifications/', dashboard_views.notifications_view, name='dashboard_notifications'),
    path('dashboard/notifications/lire/<int:notif_id>/', dashboard_views.notification_marquer_lue, name='notification_marquer_lue'),
    path('dashboard/notifications/construction/lire/<int:notif_id>/', dashboard_views.notification_construction_marquer_lue, name='notification_construction_marquer_lue'),
    path('dashboard/notifications/tout-lire/', dashboard_views.notifications_marquer_toutes_lues, name='notifications_marquer_toutes_lues'),
    path('dashboard/notifications/supprimer/<int:notif_id>/', dashboard_views.notification_supprimer, name='notification_supprimer'),
    path('dashboard/clients/', dashboard_views.clients_crm_view, name='dashboard_clients'),
    path('dashboard/reclamations/', dashboard_views.reclamations_view, name='dashboard_reclamations'),
    path('dashboard/devis/', dashboard_views.devis_view, name='dashboard_devis'),
    path('dashboard/client/<int:client_id>/', dashboard_views.client_detail_view, name='dashboard_client_detail'),
    path('dashboard/facturation/', dashboard_views.facturation_dashboard_view, name='dashboard_facturation'),
    path('dashboard/facturation/signaler-paiement/', dashboard_views.signaler_paiement, name='signaler_paiement'),
    path('dashboard/facturation/confirmer-reception/', dashboard_views.confirmer_reception_paiement, name='confirmer_reception_paiement'),
    path('dashboard/paiements/validation/', dashboard_views.centre_validation_paiements, name='centre_validation_paiements'),
    path('dashboard/facturation/demander-rdv-paiement/', dashboard_views.demander_rdv_paiement, name='demander_rdv_paiement'),
    path('dashboard/facturation/repondre-rdv-paiement/', dashboard_views.repondre_rdv_paiement, name='repondre_rdv_paiement'),
    path('dashboard/facturation/repondre-contre-proposition-rdv/', dashboard_views.repondre_contre_proposition_rdv, name='repondre_contre_proposition_rdv'),
    path('dashboard/facturation/confirmer-paiement-espece/', dashboard_views.confirmer_paiement_espece, name='confirmer_paiement_espece'),
    path('dashboard/facturation/stripe/creer-session/', dashboard_views.stripe_creer_session, name='stripe_creer_session'),
    path('dashboard/facturation/stripe/succes/', dashboard_views.stripe_paiement_reussi, name='stripe_paiement_reussi'),
    path('dashboard/facturation/signaler-probleme/', dashboard_views.signaler_probleme_paiement, name='signaler_probleme_paiement'),
    path('dashboard/facturation/factures.zip', dashboard_views.factures_zip, name='factures_zip'),
    path('dashboard/facturation/<int:facture_id>/', dashboard_views.facture_detail, name='facture_detail'),
    path('dashboard/facturation/<int:facture_id>/pdf/', dashboard_views.facture_pdf, name='facture_pdf'),
    path('dashboard/facturation/<int:facture_id>/archiver/', dashboard_views.facture_archiver, name='facture_archiver'),
    path('dashboard/contrats/', dashboard_views.contrats_dashboard_view, name='dashboard_contrats'),
    path('dashboard/contrats/export/', dashboard_views.export_contrats_csv, name='export_contrats_csv'),
    path('dashboard/paiements/export/', dashboard_views.export_paiements_csv, name='export_paiements_csv'),
    path('dashboard/rapport-mensuel/pdf/', dashboard_views.rapport_mensuel_pdf, name='rapport_mensuel_pdf'),
    # Répondre aux requêtes du Chrome DevTools manifest pour éviter les 404 dans les logs
    path('.well-known/appspecific/com.chrome.devtools.json', lambda request: JsonResponse({}, status=200)),
    # Dashboard (utilisateurs authentifiés)
    path('dashboard/', home, name='dashboard'),
    path('admin/', admin.site.urls),
    # redirect legacy profile URL to dashboard
    path('accounts/profile/', lambda request: redirect('dashboard')),
    path('accounts/login/', utilisateurs_views.login_view, name='login'),
    path('accounts/login/company/', utilisateurs_views.company_login, name='login_company'),
    path('accounts/signup/', utilisateurs_views.signup, name='signup'),
    path('accounts/confirmer-email/', utilisateurs_views.confirmer_email, name='confirmer_email'),
    path('accounts/renvoyer-confirmation/', utilisateurs_views.renvoyer_confirmation, name='renvoyer_confirmation'),
    # UI pages (front-end) linked to backend models
    path('biens/', include(('biens.urls_ui', 'biens'), namespace='biens_ui')),
    path('chat/', include(('messagerie.urls', 'messagerie'), namespace='messagerie')),
    path('construction/', include(('construction.urls', 'construction'), namespace='construction')),
    path('assistant/', include(('assistant.urls', 'assistant'), namespace='assistant')),
    path('utilisateurs/', include(('utilisateurs.urls_ui', 'utilisateurs'), namespace='utilisateurs_ui')),
    path('contrats/', include(('contrats.urls_ui', 'contrats'), namespace='contrats_ui')),
    path('onboarding/', utilisateurs_views.onboarding, name='onboarding'),
    path('onboarding/apply/', utilisateurs_views.onboarding_apply, name='onboarding_apply'),
    path('dashboard/entreprise/modifier/', utilisateurs_views.company_profile_edit, name='company_profile_edit'),
    path('dashboard/entreprise/profil/', dashboard_views.entreprise_profil, name='entreprise_profil'),
    path('dashboard/entreprise/parametres/', dashboard_views.entreprise_parametres, name='entreprise_parametres'),
    path('verification-entreprises/', utilisateurs_views.admin_verification_entreprises, name='admin_verification_entreprises'),
    path('verification-entreprises/<int:company_id>/', utilisateurs_views.admin_verifier_entreprise, name='admin_verifier_entreprise'),

    # APIs
    path('api/utilisateurs/', include('utilisateurs.urls')),
    path('api/biens/', include('biens.urls')),
    path('api/contrats/', include('contrats.urls')),
    path('api/facturation/', include('facturation.urls')),
    path('api/recherche/', include('recherche.urls')),
    path('api/dashboard/', include('dashboard.urls')),
    
    # DRF auth
    path('api-auth/', include('rest_framework.urls')),
    path('accounts/logout/', utilisateurs_views.logout_view, name='logout'),
    path('accounts/', include('django.contrib.auth.urls')),
]

# Servir les fichiers médias en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
