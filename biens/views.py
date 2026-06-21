from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from .models import Bien, PhotoBien, Visite
from .serializers import (
    BienListSerializer, BienDetailSerializer, BienCreateUpdateSerializer,
    PhotoBienSerializer, VisiteSerializer
)
from .forms import BienForm


@login_required
def publier_bien(request):
    """Affiche le formulaire de publication en ne montrant que les opérations
    activées pour l'entreprise de l'utilisateur.
    """
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

    # display company name even if company is None
    display_company = company if company is not None else type('C', (), {'name': f"{user.username} Company"})()

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
    queryset = Bien.objects.filter(statut=Bien.Statut.DISPONIBLE)

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
    """Détail d'un bien"""
    bien = Bien.objects.filter(id=pk).first()
    if not bien:
        from django.http import Http404
        raise Http404('Bien non trouvé')
    return render(request, 'biens/detail.html', {'bien': bien})


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
