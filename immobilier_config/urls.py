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
from django.shortcuts import render, redirect
from django.urls import reverse
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Q
from django.core.paginator import Paginator
from django.utils import timezone
from utilisateurs import views as utilisateurs_views
from dashboard import views as dashboard_views
from django.http import JsonResponse, HttpResponse

# Importer modèles pour métriques de la page d'accueil
from utilisateurs.models import Utilisateur
from biens.models import Bien
from contrats.models import Contrat, Paiement
from facturation.models import Facture


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

    # Profil propriétaire/gestionnaire incomplet → onboarding
    needs_onboarding = (
        request.user.role in (Utilisateur.Role.PROPRIETAIRE, Utilisateur.Role.GESTIONNAIRE)
        and (not request.user.company or not request.user.company.types)
    )
    if needs_onboarding:
        return redirect('onboarding')
    # Rediriger selon le rôle pour afficher le dashboard adapté
    if request.user.role in (Utilisateur.Role.PROPRIETAIRE, Utilisateur.Role.GESTIONNAIRE):
        # Si l'utilisateur a une company configurée, utiliser le dashboard entreprise
        if getattr(request.user, 'company', None):
            return redirect('dashboard_company')
    elif request.user.role == Utilisateur.Role.LOCATAIRE:
        # Les locataires sont dirigés vers la landing guest (flux particulier)
        try:
            return redirect('guest_landing')
        except Exception:
            pass
    
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
    """Landing publique accessible via /landing/ (statistiques minimales)."""
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
    """Page publique dédiée aux invités."""
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
    return render(request, 'landing_guest.html', context)


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
    if tab not in TAB_FILTER:
        tab = 'locations'

    q = request.GET.get('q', '').strip()
    ville_filtre = request.GET.get('ville', '').strip()
    budget_max = request.GET.get('budget_max', '').strip()
    chambres = request.GET.get('chambres', '').strip()

    qs = Bien.objects.filter(statut=Bien.Statut.DISPONIBLE).filter(TAB_FILTER[tab]).select_related('proprietaire__company')

    if q:
        qs = qs.filter(Q(titre__icontains=q) | Q(adresse__icontains=q) | Q(ville__icontains=q))
    if ville_filtre:
        qs = qs.filter(ville__icontains=ville_filtre)
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

    qs = qs.order_by('-date_publication', '-date_creation')
    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    base_qs = Bien.objects.filter(statut=Bien.Statut.DISPONIBLE)
    tabs_info = [
        {'key': 'locations', 'emoji': '🏠', 'label': 'Locations', 'count': base_qs.filter(transaction_type__in=['location', 'both']).count()},
        {'key': 'vente', 'emoji': '🏡', 'label': 'Maisons à vendre', 'count': base_qs.filter(transaction_type__in=['vente', 'both'], type_bien__in=TYPES_RESIDENTIEL).count()},
        {'key': 'terrains', 'emoji': '🌍', 'label': 'Terrains', 'count': base_qs.filter(type_bien='terrain').count()},
        {'key': 'magasins', 'emoji': '🏬', 'label': 'Magasins', 'count': base_qs.filter(type_bien__in=TYPES_COMMERCIAL).count()},
        {'key': 'bureaux', 'emoji': '🏢', 'label': 'Bureaux', 'count': base_qs.filter(type_bien='bureau').count()},
        {'key': 'construction', 'emoji': '🏗️', 'label': 'Projets en construction', 'count': base_qs.filter(type_bien__in=TYPES_CONSTRUCTION).count()},
    ]

    villes = Bien.objects.filter(statut=Bien.Statut.DISPONIBLE).values_list('ville', flat=True).distinct().order_by('ville')

    return render(request, 'explorer.html', {
        'tab': tab,
        'biens': page_obj,
        'tabs': tabs_info,
        'villes': villes,
        'q': q,
        'ville_filtre': ville_filtre,
        'budget_max': budget_max,
        'chambres': chambres,
        'total': paginator.count,
        'has_filters': bool(q or ville_filtre or budget_max or chambres),
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
    path('explorer/', explorer_view, name='explorer'),
    path('accounts/signup/company/', utilisateurs_views.company_signup, name='company_signup'),
    path('guest-debug/', guest_debug, name='guest_debug'),
    path('dashboard/company/', dashboard_views.dashboard_company, name='dashboard_company'),
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
    # UI pages (front-end) linked to backend models
    path('biens/', include(('biens.urls_ui', 'biens'), namespace='biens_ui')),
    path('utilisateurs/', include(('utilisateurs.urls_ui', 'utilisateurs'), namespace='utilisateurs_ui')),
    path('contrats/', include(('contrats.urls_ui', 'contrats'), namespace='contrats_ui')),
    path('onboarding/', utilisateurs_views.onboarding, name='onboarding'),
    path('onboarding/apply/', utilisateurs_views.onboarding_apply, name='onboarding_apply'),
    
    # APIs
    path('api/utilisateurs/', include('utilisateurs.urls')),
    path('api/biens/', include('biens.urls')),
    path('api/contrats/', include('contrats.urls')),
    path('api/facturation/', include('facturation.urls')),
    path('api/recherche/', include('recherche.urls')),
    path('api/dashboard/', include('dashboard.urls')),
    
    # DRF auth
    path('api-auth/', include('rest_framework.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
]

# Servir les fichiers médias en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
