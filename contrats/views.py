from django.shortcuts import render
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from .models import Contrat, Paiement, DocumentContrat
from .serializers import (
    ContratListSerializer, ContratDetailSerializer,
    ContratCreateUpdateSerializer, PaiementSerializer
)

from django.contrib.auth.decorators import login_required


class ContratViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des contrats"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['statut', 'bien', 'locataire', 'proprietaire']
    ordering_fields = ['date_debut', 'date_creation']
    ordering = ['-date_creation']
    
    def get_queryset(self):
        """Filtrer les contrats selon l'utilisateur"""
        user = self.request.user
        if user.role == 'proprietaire':
            return Contrat.objects.filter(proprietaire=user)
        elif user.role == 'locataire':
            return Contrat.objects.filter(locataire=user)
        return Contrat.objects.all()
    
    def get_serializer_class(self):
        """Choisir le serializer approprié"""
        if self.action == 'retrieve':
            return ContratDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ContratCreateUpdateSerializer
        return ContratListSerializer
    
    def perform_create(self, serializer):
        """Générer automatiquement le numéro de contrat"""
        contrat = serializer.save()
        if not contrat.numero_contrat:
            contrat.generer_numero()
            contrat.save()
    
    @action(detail=True, methods=['post'])
    def activer(self, request, pk=None):
        """Activer un contrat (passer au statut EN_COURS)"""
        contrat = self.get_object()
        if contrat.statut != Contrat.Statut.BROUILLON:
            return Response(
                {'error': 'Seuls les contrats en brouillon peuvent être activés'},
                status=status.HTTP_400_BAD_REQUEST
            )
        contrat.statut = Contrat.Statut.EN_COURS
        contrat.date_signature = timezone.now()
        contrat.save()
        return Response({'status': 'Contrat activé avec succès'})
    
    @action(detail=True, methods=['post'])
    def resilier(self, request, pk=None):
        """Résilier un contrat"""
        contrat = self.get_object()
        contrat.statut = Contrat.Statut.RESILIE
        contrat.save()
        return Response({'status': 'Contrat résilié'})
    
    @action(detail=True, methods=['get'])
    def paiements(self, request, pk=None):
        """Récupérer les paiements associés au contrat"""
        contrat = self.get_object()
        paiements = contrat.paiements.all()
        serializer = PaiementSerializer(paiements, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def statistiques(self, request, pk=None):
        """Récupérer les statistiques du contrat"""
        contrat = self.get_object()
        paiements = contrat.paiements.all()
        montant_total_du = sum(p.montant_du for p in paiements)
        montant_total_recu = sum(p.montant_recu for p in paiements)
        montant_impaye = montant_total_du - montant_total_recu
        
        return Response({
            'montant_total_du': montant_total_du,
            'montant_total_recu': montant_total_recu,
            'montant_impaye': montant_impaye,
            'nombre_paiements': paiements.count(),
            'paiements_recus': paiements.filter(statut='recu').count(),
            'paiements_en_retard': paiements.filter(statut__in=['retard_mineur', 'retard_majeur']).count()
        })


class PaiementViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des paiements"""
    queryset = Paiement.objects.all()
    serializer_class = PaiementSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['statut', 'contrat', 'mois']
    ordering_fields = ['mois', 'date_limite']
    ordering = ['-mois']
    
    def get_queryset(self):
        """Filtrer les paiements selon l'utilisateur"""
        user = self.request.user
        if user.role == 'proprietaire':
            return Paiement.objects.filter(contrat__proprietaire=user)
        elif user.role == 'locataire':
            return Paiement.objects.filter(contrat__locataire=user)
        return Paiement.objects.all()
    
    @action(detail=True, methods=['post'])
    def enregistrer_paiement(self, request, pk=None):
        """Enregistrer un paiement"""
        paiement = self.get_object()
        montant_recu = float(request.data.get('montant_recu', 0))
        
        paiement.montant_recu = montant_recu
        paiement.date_paiement = timezone.now().date()
        paiement.mettre_a_jour_statut()
        paiement.save()
        
        return Response({
            'status': 'Paiement enregistré',
            'montant_recu': paiement.montant_recu,
            'statut': paiement.statut
        })
    
    @action(detail=False, methods=['get'])
    def en_retard(self, request):
        """Récupérer les paiements en retard"""
        paiements_retard = self.get_queryset().filter(
            statut__in=['retard_mineur', 'retard_majeur', 'impaye']
        )
        serializer = self.get_serializer(paiements_retard, many=True)
        return Response(serializer.data)


def ui_index(request):
    """Page front simple pour les contrats"""
    context = {
        'title': 'Contrats',
        'api_url': '/api/contrats/contrats/'
    }
    return render(request, 'contrats/index.html', context)


def ui_list(request):
    """Liste des contrats (vue simplifiée)"""
    contrats = Contrat.objects.all().order_by('-date_creation')[:50]
    return render(request, 'contrats/list.html', {'contrats': contrats, 'title': 'Contrats'})


def ui_detail(request, pk):
    contrat = Contrat.objects.filter(id=pk).first()
    if not contrat:
        from django.http import Http404
        raise Http404('Contrat non trouvé')
    return render(request, 'contrats/detail.html', {'contrat': contrat})


@login_required
def ui_mes_locations(request):
    """Afficher les locations (contrats) pour le locataire connecté."""
    user = request.user
    if user.role != 'locataire':
        # Rediriger vers la liste générale si l'utilisateur n'est pas locataire
        return redirect('contrats:list')

    contrats = Contrat.objects.filter(locataire=user).order_by('-date_creation')
    # Montrer en priorité les contrats actifs
    actifs = [c for c in contrats if c.is_actif()]
    autres = [c for c in contrats if not c.is_actif()]

    context = {
        'title': 'Mes locations',
        'contrats_actifs': actifs,
        'contrats_autres': autres,
    }
    return render(request, 'contrats/mes_locations.html', context)
