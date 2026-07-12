from django.shortcuts import render
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from biens.models import Bien
from .models import RechercheSauvegardee, BienFavori, HistoriqueRecherche
from .serializers import (
    RechercheSauvegardeeSerializer, BienFavoriSerializer,
    HistoriqueRechercheSerializer
)
from biens.serializers import BienListSerializer
from django.utils import timezone


class RechercheSauvegardeeViewSet(viewsets.ModelViewSet):
    """ViewSet pour les recherches sauvegardées"""
    serializer_class = RechercheSauvegardeeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Récupérer les recherches sauvegardées de l'utilisateur"""
        return RechercheSauvegardee.objects.filter(utilisateur=self.request.user)
    
    def perform_create(self, serializer):
        """Créer une recherche sauvegardée pour l'utilisateur"""
        serializer.save(utilisateur=self.request.user)
    
    @action(detail=True, methods=['post'])
    def executer(self, request, pk=None):
        """Exécuter une recherche sauvegardée"""
        recherche = self.get_object()
        
        # Construire la requête
        queryset = Bien.objects.filter(statut=Bien.Statut.DISPONIBLE)
        
        if recherche.villes:
            queryset = queryset.filter(ville__in=recherche.villes)
        if recherche.budget_min:
            queryset = queryset.filter(prix_mensuel__gte=recherche.budget_min)
        if recherche.budget_max:
            queryset = queryset.filter(prix_mensuel__lte=recherche.budget_max)
        if recherche.nombre_chambres_min:
            queryset = queryset.filter(nombre_chambres__gte=recherche.nombre_chambres_min)
        if recherche.types_bien:
            queryset = queryset.filter(type_bien__in=recherche.types_bien)
        
        # Mettre à jour la recherche
        recherche.date_derniere_recherche = timezone.now()
        recherche.nombre_utilisations += 1
        recherche.save()
        
        # Sauvegarder l'historique
        HistoriqueRecherche.objects.create(
            utilisateur=request.user,
            requete=recherche.nom,
            nombre_resultats=queryset.count()
        )
        
        serializer = BienListSerializer(queryset, many=True)
        return Response({
            'search': RechercheSauvegardeeSerializer(recherche).data,
            'results': serializer.data,
            'count': queryset.count()
        })


class BienFavoriViewSet(viewsets.ModelViewSet):
    """ViewSet pour les biens favoris"""
    serializer_class = BienFavoriSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Récupérer les biens favoris de l'utilisateur"""
        return BienFavori.objects.filter(utilisateur=self.request.user)
    
    def perform_create(self, serializer):
        """Ajouter un bien aux favoris"""
        serializer.save(utilisateur=self.request.user)
    
    @action(detail=True, methods=['post'])
    def noter(self, request, pk=None):
        """Ajouter une note à un bien favori"""
        favori = self.get_object()
        note = int(request.data.get('note', 0))
        if not (0 <= note <= 5):
            return Response(
                {'error': 'La note doit être entre 0 et 5'},
                status=status.HTTP_400_BAD_REQUEST
            )
        favori.note = note
        favori.save()
        return Response({'status': 'Note ajoutée'})


class HistoriqueRechercheViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour l'historique des recherches"""
    serializer_class = HistoriqueRechercheSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_recherche']
    ordering = ['-date_recherche']
    
    def get_queryset(self):
        """Récupérer l'historique de l'utilisateur"""
        return HistoriqueRecherche.objects.filter(utilisateur=self.request.user)


@api_view(['GET'])
@permission_classes([AllowAny])
def recherche_avancee(request):
    """API de recherche avancée de biens"""
    queryset = Bien.objects.filter(statut=Bien.Statut.DISPONIBLE)
    
    # Filtres
    ville = request.query_params.get('ville')
    budget_min = request.query_params.get('budget_min')
    budget_max = request.query_params.get('budget_max')
    chambres_min = request.query_params.get('chambres_min')
    type_bien = request.query_params.get('type_bien')
    operation = request.query_params.get('operation')  # 'location' or 'vente'
    
    if ville:
        queryset = queryset.filter(ville__icontains=ville)
    if budget_min:
        queryset = queryset.filter(prix_mensuel__gte=float(budget_min))
    if budget_max:
        queryset = queryset.filter(prix_mensuel__lte=float(budget_max))
    if chambres_min:
        queryset = queryset.filter(nombre_chambres__gte=int(chambres_min))
    if type_bien:
        # accepter plusieurs types séparés par des virgules
        types = [t.strip() for t in type_bien.split(',') if t.strip()]
        if types:
            queryset = queryset.filter(type_bien__in=types)

    # Filtrer par type d'opération si fourni
    if operation:
        op = operation.lower()
        if op == 'location':
            queryset = queryset.filter(transaction_type__in=['location', 'both'])
        elif op == 'vente' or op == 'achat':
            queryset = queryset.filter(transaction_type__in=['vente', 'both'])
    
    # Enregistrer dans l'historique
    if request.user.is_authenticated:
        HistoriqueRecherche.objects.create(
            utilisateur=request.user,
            requete=str(request.query_params),
            nombre_resultats=queryset.count()
        )
    
    serializer = BienListSerializer(queryset, many=True)
    return Response({
        'count': queryset.count(),
        'results': serializer.data
    })


def ui_index(request):
    """Page front simple pour la recherche"""
    context = {
        'title': 'Recherche',
        'api_url': '/api/recherche/'
    }
    return render(request, 'recherche/index.html', context)


from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


@login_required
def mes_favoris(request):
    """Liste des biens que le locataire a mis en favoris."""
    favoris = (
        BienFavori.objects.filter(utilisateur=request.user)
        .select_related('bien', 'bien__proprietaire__company')
        .order_by('-date_ajout')
    )
    return render(request, 'recherche/mes_favoris.html', {'favoris': favoris})


@login_required
def favori_toggle(request, bien_id):
    """Ajoute ou retire un bien des favoris de l'utilisateur connecté."""
    if request.method != 'POST':
        return redirect('biens_ui:detail', pk=bien_id)

    favori = BienFavori.objects.filter(utilisateur=request.user, bien_id=bien_id).first()
    if favori:
        favori.delete()
        est_favori = False
    else:
        BienFavori.objects.create(utilisateur=request.user, bien_id=bien_id)
        est_favori = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.http import JsonResponse
        return JsonResponse({'ok': True, 'est_favori': est_favori})

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/explorer/'
    return redirect(next_url)
