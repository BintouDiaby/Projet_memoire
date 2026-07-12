from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from .models import Bien, PhotoBien, Visite, Reservation
from .serializers import (
    BienListSerializer, BienDetailSerializer, BienCreateUpdateSerializer,
    PhotoBienSerializer, VisiteSerializer
)
from .forms import BienForm


TYPE_BIEN_LABEL_MAP = {
    'Appartement': Bien.TypeBien.APPARTEMENT,
    'Villa': Bien.TypeBien.MAISON,
    'Studio': Bien.TypeBien.STUDIO,
    'Chambre': Bien.TypeBien.STUDIO,
    'Magasin': Bien.TypeBien.MAGASIN,
    'Boutique': Bien.TypeBien.BOUTIQUE,
    'Bureau': Bien.TypeBien.BUREAU,
    'Entrepôt': Bien.TypeBien.ENTREPOT,
    'Maison': Bien.TypeBien.MAISON,
    'Terrain': Bien.TypeBien.TERRAIN,
    'Parcelle viabilisée': Bien.TypeBien.TERRAIN,
    'Lot titré (ACD)': Bien.TypeBien.TERRAIN,
    'Terrain agricole': Bien.TypeBien.TERRAIN,
    'Projet sur plan': Bien.TypeBien.IMMEUBLE,
}


@login_required
def publier_bien(request):
    """Formulaire de publication (opération -> champs adaptés) ; enregistre le
    bien du propriétaire connecté à la soumission.
    """
    from decimal import Decimal, InvalidOperation
    from django.contrib import messages
    from django.utils import timezone

    user = request.user
    company = getattr(user, 'company', None)

    # calculer les opérations activées à partir des types enregistrés
    ops = set()
    if company and getattr(company, 'types', None):
        for t in company.types:
            if str(t).startswith('location'):
                ops.add('location')
            if str(t).startswith('vente'):
                ops.add('vente')
            if 'terrain' in str(t):
                ops.add('terrain')
            if str(t).startswith('construction'):
                ops.add('construction')
    if not ops:
        # pas de company / types reconnus : ne pas bloquer la publication
        ops = {'location', 'vente', 'terrain', 'construction'}

    # display company name even if company is None
    display_company = company if company is not None else type('C', (), {'name': f"{user.username} Company"})()

    if request.method == 'POST':
        def to_decimal(name):
            raw = (request.POST.get(name) or '').strip()
            if not raw:
                return None
            try:
                return Decimal(raw)
            except InvalidOperation:
                return None

        def to_float(name):
            raw = (request.POST.get(name) or '').strip()
            if not raw:
                return None
            try:
                return float(raw)
            except ValueError:
                return None

        operation = (request.POST.get('operation') or '').strip()
        titre = (request.POST.get('titre') or '').strip()
        commune = (request.POST.get('commune') or '').strip()
        ville = (request.POST.get('ville') or '').strip() or commune or 'Abidjan'
        adresse = (request.POST.get('adresse') or '').strip()
        description = (request.POST.get('description') or '').strip()
        type_bien = TYPE_BIEN_LABEL_MAP.get((request.POST.get('type_bien') or '').strip())
        latitude = to_float('latitude')
        longitude = to_float('longitude')

        errors = []
        if operation not in ('location', 'vente', 'terrain', 'construction'):
            errors.append("Choisissez une opération.")
        if not titre:
            errors.append("Le titre de l'annonce est requis.")
        if not commune:
            errors.append("La commune est requise.")
        if not type_bien:
            errors.append("Le type de bien est requis.")

        prix_mensuel = Decimal('0')
        prix_vente = None
        surface = Decimal('0')
        chambres = 0
        transaction_type = Bien.TransactionType.LOCATION

        if operation == 'location':
            prix_mensuel = to_decimal('loyer') or Decimal('0')
            surface = to_decimal('surface') or Decimal('0')
            chambres = int(to_decimal('pieces') or 0)
            transaction_type = Bien.TransactionType.LOCATION
            if not prix_mensuel:
                errors.append('Le loyer mensuel est requis.')
        elif operation == 'vente':
            prix_vente = to_decimal('prix')
            surface = to_decimal('surface_v') or Decimal('0')
            chambres = int(to_decimal('pieces_v') or 0)
            transaction_type = Bien.TransactionType.VENTE
            if not prix_vente:
                errors.append('Le prix de vente est requis.')
        elif operation == 'terrain':
            prix_vente = to_decimal('prix_t')
            surface = to_decimal('superficie') or Decimal('0')
            transaction_type = Bien.TransactionType.VENTE
            if not prix_vente:
                errors.append('Le prix est requis.')
        elif operation == 'construction':
            if not titre:
                titre = (request.POST.get('nom_projet') or '').strip()
            prix_vente = to_decimal('prix_min')
            transaction_type = Bien.TransactionType.VENTE

        if not errors:
            bien = Bien(
                titre=titre,
                description=description,
                type_bien=type_bien,
                statut=Bien.Statut.DISPONIBLE,
                adresse=adresse,
                commune=commune,
                ville=ville,
                latitude=latitude,
                longitude=longitude,
                surface_m2=surface,
                nombre_chambres=chambres,
                nombre_salles_bain=0,
                prix_mensuel=prix_mensuel,
                prix_vente=prix_vente,
                transaction_type=transaction_type,
                proprietaire=user,
                date_publication=timezone.now(),
            )
            photos = request.FILES.getlist('photos')
            if photos:
                bien.photo_principale = photos[0]
            bien.save()
            for extra in photos[1:]:
                PhotoBien.objects.create(bien=bien, photo=extra)
            messages.success(request, 'Bien publié avec succès.')
            return redirect('biens_ui:detail', pk=bien.id)

        context = {
            'entreprise': display_company,
            'ops_enabled': ops,
            'errors': errors,
        }
        return render(request, 'biens/publier_bien.html', context)

    context = {
        'entreprise': display_company,
        'ops_enabled': ops,
    }
    return render(request, 'biens/publier_bien.html', context)


@login_required
def ajouter_bien_module(request, operation):
    """Page scoped à une opération (location, vente, terrain, construction).
    La vue rend le template fourni et fixe `operation` dans le contexte pour
    initialiser le JS côté client.
    """
    allowed = ('location', 'vente', 'terrain', 'construction')
    if operation not in allowed:
        from django.http import Http404
        raise Http404('Opération inconnue')

    company = getattr(request.user, 'company', None)
    display_company = company if company is not None else type('C', (), {'name': request.user.username+' Company'})()

    context = {
        'operation': operation,
        'entreprise': display_company,
    }
    return render(request, 'biens/ajouter_bien_module.html', context)


def ui_index(request):
    """Page front simple pour les biens"""
    context = {
        'title': 'Biens',
        'api_url': '/api/biens/biens/'
    }
    return render(request, 'biens/index.html', context)


def ui_list(request):
    """Liste publique des biens"""
    queryset = Bien.objects.filter(statut=Bien.Statut.DISPONIBLE).select_related('proprietaire')

    # Filtres provenant de la requête GET
    ville = request.GET.get('ville')
    transaction_types = request.GET.getlist('transaction_type')
    types_bien = request.GET.getlist('type_bien')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    min_chambres = request.GET.get('min_chambres')
    entreprises_verifiees = request.GET.get('entreprises_verifiees')

    if ville:
        queryset = queryset.filter(ville__icontains=ville)

    if transaction_types:
        queryset = queryset.filter(transaction_type__in=transaction_types)

    if types_bien:
        queryset = queryset.filter(type_bien__in=types_bien)

    if min_price:
        try:
            queryset = queryset.filter(prix_mensuel__gte=float(min_price))
        except ValueError:
            pass

    if max_price:
        try:
            queryset = queryset.filter(prix_mensuel__lte=float(max_price))
        except ValueError:
            pass

    if min_chambres:
        try:
            queryset = queryset.filter(nombre_chambres__gte=int(min_chambres))
        except ValueError:
            pass

    if entreprises_verifiees:
        queryset = queryset.filter(proprietaire__documents_verifies=True)

    biens = queryset.order_by('-date_publication')[:200]

    context = {
        'biens': biens,
        'title': 'Biens disponibles',
        'type_choices': Bien.TypeBien.choices,
        'transaction_choices': Bien.TransactionType.choices,
        'rooms_range': range(0, 7),
        'selected_transaction_types': transaction_types,
        'selected_types_bien': types_bien,
        'selected_min_price': min_price,
        'selected_max_price': max_price,
        'selected_min_chambres': min_chambres,
        'selected_entreprises_verifiees': entreprises_verifiees,
    }

    return render(request, 'biens/list.html', context)


def ui_detail(request, pk):
    """Détail d'un bien avec demande de visite"""
    from django.http import Http404
    from utilisateurs.models import Utilisateur

    bien = Bien.objects.select_related('proprietaire__company').filter(id=pk).first()
    if not bien:
        raise Http404('Bien non trouvé')

    visite_ok = False
    visite_erreur = None

    if request.method == 'POST' and request.user.is_authenticated:
        if request.POST.get('action') == 'demander_visite':
            date_str = request.POST.get('date_visite', '').strip()
            notes = request.POST.get('notes', '').strip()
            if date_str:
                from django.utils.dateparse import parse_datetime
                date_visite = parse_datetime(date_str)
                if date_visite:
                    if not Visite.objects.filter(bien=bien, locataire=request.user, date_visite=date_visite).exists():
                        Visite.objects.create(bien=bien, locataire=request.user, date_visite=date_visite, notes=notes)
                        from dashboard.services import NotificationService
                        NotificationService.send(
                            destinataire=bien.proprietaire,
                            expediteur=request.user,
                            type_notification='visite',
                            titre=f"Demande de visite — {bien.titre}",
                            message=f"{request.user.get_full_name() or request.user.username} souhaite visiter le {date_visite.strftime('%d/%m/%Y à %H:%M')}.",
                            lien='/dashboard/rdv/',
                        )
                        visite_ok = True
                    else:
                        visite_erreur = "Vous avez déjà une visite planifiée à cette date pour ce bien."
                else:
                    visite_erreur = "Format de date invalide."
            else:
                visite_erreur = "Veuillez choisir une date et heure."

    biens_similaires = list(
        Bien.objects.filter(statut=Bien.Statut.DISPONIBLE, type_bien=bien.type_bien)
        .exclude(id=bien.id)
        .select_related('proprietaire__company')[:3]
    )
    if len(biens_similaires) < 3:
        ids_excl = [b.id for b in biens_similaires] + [bien.id]
        extra = list(
            Bien.objects.filter(statut=Bien.Statut.DISPONIBLE)
            .exclude(id__in=ids_excl)
            .select_related('proprietaire__company')[:3 - len(biens_similaires)]
        )
        biens_similaires = biens_similaires + extra

    visite_existante = None
    est_favori = False
    reservation_existante = None
    est_gestionnaire = False
    if request.user.is_authenticated:
        est_gestionnaire = (
            request.user == bien.proprietaire or request.user.is_staff
            or request.user.role == Utilisateur.Role.GESTIONNAIRE
        )
        if not est_gestionnaire:
            visite_existante = Visite.objects.filter(bien=bien, locataire=request.user).order_by('-date_reservation').first()
            reservation_existante = Reservation.objects.filter(bien=bien, client=request.user).first()
        from recherche.models import BienFavori
        est_favori = BienFavori.objects.filter(utilisateur=request.user, bien=bien).exists()

    nb_visites_en_attente = None
    nb_reservations_en_attente = None
    if est_gestionnaire:
        nb_visites_en_attente = bien.visites.filter(statut=Visite.Statut.EN_ATTENTE).count()
        nb_reservations_en_attente = bien.reservations.filter(statut=Reservation.Statut.EN_ATTENTE).count()

    return render(request, 'biens/detail.html', {
        'bien': bien,
        'biens_similaires': biens_similaires,
        'visite_ok': visite_ok,
        'visite_erreur': visite_erreur,
        'visite_existante': visite_existante,
        'est_favori': est_favori,
        'reservation_existante': reservation_existante,
        'est_gestionnaire': est_gestionnaire,
        'nb_visites_en_attente': nb_visites_en_attente,
        'nb_reservations_en_attente': nb_reservations_en_attente,
    })


@login_required
def ui_create(request):
    if request.method == 'POST':
        form = BienForm(request.POST, request.FILES)
        if form.is_valid():
            bien = form.save(commit=False)
            bien.proprietaire = request.user
            bien.save()
            return redirect('biens_ui:detail', pk=bien.id)
    else:
        form = BienForm()
    return render(request, 'biens/form.html', {'form': form, 'title': 'Créer un bien'})


@login_required
def ui_update(request, pk):
    bien = Bien.objects.filter(id=pk).first()
    if not bien:
        from django.http import Http404
        raise Http404('Bien non trouvé')
    # permission : seulement le propriétaire ou staff
    if not (request.user == bien.proprietaire or request.user.is_staff):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('Accès refusé')

    if request.method == 'POST':
        form = BienForm(request.POST, request.FILES, instance=bien)
        if form.is_valid():
            form.save()
            return redirect('biens_ui:detail', pk=bien.id)
    else:
        form = BienForm(instance=bien)
    return render(request, 'biens/form.html', {'form': form, 'title': 'Éditer le bien'})


@login_required
def ui_delete(request, pk):
    bien = Bien.objects.filter(id=pk).first()
    if not bien:
        from django.http import Http404
        raise Http404('Bien non trouvé')
    if not (request.user == bien.proprietaire or request.user.is_staff):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('Accès refusé')

    if request.method == 'POST':
        bien.delete()
        return redirect('biens_ui:list')
    return render(request, 'biens/confirm_delete.html', {'bien': bien})


@login_required
def ui_gerer(request, pk):
    """Page de pilotage d'un bien (propriétaire/gestionnaire) : demandes de
    visite en attente, réservations, favoris reçus, publier/dépublier —
    distincte de la page publique de l'annonce (biens_ui:detail)."""
    from django.http import Http404, HttpResponseForbidden
    from recherche.models import BienFavori
    from messagerie.models import Conversation
    from django.contrib import messages

    bien = Bien.objects.select_related('proprietaire__company').filter(id=pk).first()
    if not bien:
        raise Http404('Bien non trouvé')
    if not (request.user == bien.proprietaire or request.user.is_staff or request.user.role == 'gestionnaire'):
        return HttpResponseForbidden('Accès refusé')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'depublier' and bien.statut != Bien.Statut.ARCHIVE:
            bien.statut = Bien.Statut.ARCHIVE
            bien.save(update_fields=['statut'])
            messages.success(request, "Annonce dépubliée.")
        elif action == 'publier' and bien.statut == Bien.Statut.ARCHIVE:
            bien.statut = Bien.Statut.DISPONIBLE
            bien.save(update_fields=['statut'])
            messages.success(request, "Annonce republiée.")
        return redirect('biens_ui:gerer', pk=bien.id)

    visites_en_attente = list(
        Visite.objects.filter(bien=bien, statut=Visite.Statut.EN_ATTENTE)
        .select_related('locataire').order_by('date_visite')
    )
    reservations_en_attente = list(
        Reservation.objects.filter(bien=bien, statut=Reservation.Statut.EN_ATTENTE)
        .select_related('client').order_by('-date_creation')
    )
    nb_favoris = BienFavori.objects.filter(bien=bien).count()
    nb_conversations = Conversation.objects.filter(bien=bien).count()

    return render(request, 'biens/gerer.html', {
        'bien': bien,
        'visites_en_attente': visites_en_attente,
        'reservations_en_attente': reservations_en_attente,
        'nb_favoris': nb_favoris,
        'nb_conversations': nb_conversations,
    })


@login_required
def mes_visites(request):
    """Liste des visites demandées par le locataire connecté, avec leur statut."""
    if request.user.role != 'locataire':
        return redirect('dashboard')

    visites = (
        Visite.objects.filter(locataire=request.user)
        .select_related('bien', 'bien__proprietaire__company')
        .order_by('-date_visite')
    )
    return render(request, 'biens/mes_visites.html', {'visites': visites})


@login_required
def reserver_bien(request, bien_id):
    """Le client réserve un bien (engagement préalable, distinct d'une visite)."""
    from django.http import Http404
    from dashboard.services import NotificationService

    if request.method != 'POST':
        return redirect('biens_ui:detail', pk=bien_id)

    bien = Bien.objects.select_related('proprietaire').filter(id=bien_id).first()
    if not bien:
        raise Http404('Bien non trouvé')

    reservation, created = Reservation.objects.get_or_create(
        bien=bien, client=request.user,
        defaults={'notes': request.POST.get('notes', '').strip()}
    )
    if created:
        NotificationService.send(
            destinataire=bien.proprietaire, expediteur=request.user,
            type_notification='reservation',
            titre=f"Nouvelle réservation — {bien.titre}",
            message=f"{request.user.get_full_name() or request.user.username} a réservé ce bien.",
            lien='/dashboard/reservations/',
        )
        from django.contrib import messages
        messages.success(request, "Votre réservation a été envoyée au propriétaire.")
    else:
        from django.contrib import messages
        messages.info(request, "Vous avez déjà réservé ce bien.")

    return redirect('biens_ui:detail', pk=bien_id)


@login_required
def mes_reservations(request):
    """Liste des réservations du client connecté."""
    if request.user.role != 'locataire':
        return redirect('dashboard')

    reservations = (
        Reservation.objects.filter(client=request.user)
        .select_related('bien', 'bien__proprietaire__company')
        .order_by('-date_creation')
    )
    return render(request, 'biens/mes_reservations.html', {'reservations': reservations})


@login_required
def annuler_visite(request, visite_id):
    """Le locataire annule sa propre demande de visite."""
    from django.contrib import messages
    from dashboard.services import NotificationService

    visite = Visite.objects.select_related('bien', 'bien__proprietaire').filter(
        id=visite_id, locataire=request.user
    ).first()
    if not visite:
        from django.http import Http404
        raise Http404('Visite non trouvée')

    if request.method == 'POST' and visite.statut != Visite.Statut.ANNULEE:
        visite.statut = Visite.Statut.ANNULEE
        visite.save(update_fields=['statut'])
        NotificationService.send(
            destinataire=visite.bien.proprietaire, expediteur=request.user,
            type_notification='visite',
            titre=f"Visite annulée — {visite.bien.titre}",
            message=f"{request.user.get_full_name() or request.user.username} a annulé sa demande de visite.",
            lien='/dashboard/rdv/',
        )
        messages.success(request, "Votre demande de visite a été annulée.")

    return redirect('biens_ui:mes_visites')


@login_required
def annuler_reservation(request, reservation_id):
    """Le locataire annule sa propre réservation."""
    from django.contrib import messages
    from dashboard.services import NotificationService

    reservation = Reservation.objects.select_related('bien', 'bien__proprietaire').filter(
        id=reservation_id, client=request.user
    ).first()
    if not reservation:
        from django.http import Http404
        raise Http404('Réservation non trouvée')

    if request.method == 'POST' and reservation.statut != Reservation.Statut.ANNULEE:
        reservation.statut = Reservation.Statut.ANNULEE
        reservation.save(update_fields=['statut'])
        NotificationService.send(
            destinataire=reservation.bien.proprietaire, expediteur=request.user,
            type_notification='reservation',
            titre=f"Réservation annulée — {reservation.bien.titre}",
            message=f"{request.user.get_full_name() or request.user.username} a annulé sa réservation.",
            lien='/dashboard/reservations/',
        )
        messages.success(request, "Votre réservation a été annulée.")

    return redirect('biens_ui:mes_reservations')


@login_required
def dashboard_reservations(request):
    """Le propriétaire confirme ou annule les réservations reçues sur ses biens."""
    from django.contrib import messages
    from dashboard.views import _sidebar_context
    from dashboard.services import NotificationService

    user = request.user
    if user.role not in ('proprietaire', 'gestionnaire'):
        return redirect('dashboard')

    if request.method == 'POST':
        res = Reservation.objects.filter(id=request.POST.get('reservation_id'), bien__proprietaire=user).first()
        action_ = request.POST.get('action')
        if res and action_ in ('confirmer', 'annuler'):
            res.statut = Reservation.Statut.CONFIRMEE if action_ == 'confirmer' else Reservation.Statut.ANNULEE
            res.save(update_fields=['statut'])
            NotificationService.send(
                destinataire=res.client, expediteur=user,
                type_notification='reservation',
                titre=f"Réservation {res.get_statut_display().lower()} — {res.bien.titre}",
                message=f"Votre réservation a été {res.get_statut_display().lower()}.",
                lien='/biens/mes-reservations/',
            )
            messages.success(request, "Réservation mise à jour.")
        return redirect('dashboard_reservations')

    reservations = (
        Reservation.objects.filter(bien__proprietaire=user)
        .select_related('bien', 'client')
        .order_by('-date_creation')
    )
    ctx = _sidebar_context(user)
    ctx.update({'active_page': 'reservations', 'reservations': reservations})
    return render(request, 'dashboard/reservations.html', ctx)


class BienViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des biens immobiliers"""
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['statut', 'type_bien', 'transaction_type', 'ville', 'prix_mensuel']
    search_fields = ['titre', 'description', 'adresse', 'ville']
    ordering_fields = ['prix_mensuel', 'date_creation', 'date_publication']
    ordering = ['-date_creation']
    
    def get_queryset(self):
        """Filtrer les biens selon l'utilisateur"""
        queryset = Bien.objects.all()
        user = self.request.user
        
        if user.is_authenticated and user.role == 'proprietaire':
            # Les propriétaires peuvent voir leurs propres biens
            if self.request.query_params.get('mes_biens'):
                queryset = queryset.filter(proprietaire=user)
        
        return queryset
    
    def get_serializer_class(self):
        """Choisir le serializer approprié"""
        if self.action == 'retrieve':
            return BienDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return BienCreateUpdateSerializer
        return BienListSerializer
    
    def perform_create(self, serializer):
        """Assigner automatiquement le propriétaire à l'utilisateur connecté"""
        serializer.save(proprietaire=self.request.user)
    
    @action(detail=True, methods=['post'])
    def marquer_disponible(self, request, pk=None):
        """Marquer un bien comme disponible"""
        bien = self.get_object()
        bien.statut = Bien.Statut.DISPONIBLE
        bien.save()
        return Response({'status': 'Bien marqué comme disponible'})
    
    @action(detail=True, methods=['post'])
    def marquer_loue(self, request, pk=None):
        """Marquer un bien comme loué"""
        bien = self.get_object()
        bien.statut = Bien.Statut.LOUE
        bien.save()
        return Response({'status': 'Bien marqué comme loué'})


class PhotoBienViewSet(viewsets.ModelViewSet):
    """ViewSet pour les photos des biens"""
    queryset = PhotoBien.objects.all()
    serializer_class = PhotoBienSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        """Vérifier que le bien appartient au propriétaire"""
        bien_id = self.request.data.get('bien')
        bien = Bien.objects.get(id=bien_id)
        if bien.proprietaire != self.request.user:
            return Response(
                {'error': 'Vous ne pouvez pas ajouter des photos à ce bien'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer.save()


class VisiteViewSet(viewsets.ModelViewSet):
    """ViewSet pour les visites de biens"""
    queryset = Visite.objects.all()
    serializer_class = VisiteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['bien', 'interet']
    ordering_fields = ['date_visite', 'date_reservation']
    
    def get_queryset(self):
        """Filtrer les visites selon l'utilisateur"""
        user = self.request.user
        if user.role == 'locataire':
            return Visite.objects.filter(locataire=user)
        elif user.role == 'proprietaire':
            return Visite.objects.filter(bien__proprietaire=user)
        return Visite.objects.all()
    
    def perform_create(self, serializer):
        """Assigner automatiquement le locataire à l'utilisateur connecté"""
        serializer.save(locataire=self.request.user)
