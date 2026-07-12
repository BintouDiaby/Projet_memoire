from django.shortcuts import render
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from .models import Facture, Notification, RappelPaiement
from .serializers import FactureSerializer, NotificationSerializer, RappelPaiementSerializer

def ui_index(request):
    from django.shortcuts import redirect
    return redirect('/dashboard/facturation/')

class FactureViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des factures"""
    serializer_class = FactureSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['statut', 'contrat', 'date_echéance']
    ordering_fields = ['date_echéance', 'date_generation', 'montant_total']
    ordering = ['-date_generation']
    
    def get_queryset(self):
        """Filtrer les factures selon l'utilisateur"""
        user = self.request.user
        if user.role == 'proprietaire':
            return Facture.objects.filter(contrat__proprietaire=user)
        elif user.role == 'locataire':
            return Facture.objects.filter(contrat__locataire=user)
        return Facture.objects.all()
    
    @action(detail=True, methods=['post'])
    def marquer_payee(self, request, pk=None):
        """Marquer une facture comme payée"""
        facture = self.get_object()
        facture.statut = Facture.Statut.PAYEE
        facture.date_paiement = timezone.now().date()
        facture.save()
        return Response({'status': 'Facture marquée comme payée'})
    
    @action(detail=True, methods=['post'])
    def envoyer(self, request, pk=None):
        """Envoyer la facture par email"""
        facture = self.get_object()
        facture.statut = Facture.Statut.ENVOYEE
        facture.dernier_envoi = timezone.now()
        facture.tentatives_envoi += 1
        facture.save()
        return Response({'status': 'Facture envoyée'})
    
    @action(detail=False, methods=['get'])
    def echues(self, request):
        """Récupérer les factures échues"""
        factures_echues = self.get_queryset().filter(
            statut__in=['generee', 'envoyee'],
            date_echéance__lt=timezone.now().date()
        )
        serializer = self.get_serializer(factures_echues, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def impayees(self, request):
        """Récupérer les factures impayées"""
        factures_impayees = self.get_queryset().exclude(statut='payee')
        serializer = self.get_serializer(factures_impayees, many=True)
        return Response(serializer.data)


class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des notifications"""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['statut', 'type_notification', 'utilisateur']
    ordering_fields = ['date_creation', 'date_envoi']
    ordering = ['-date_creation']
    
    def get_queryset(self):
        """Récupérer les notifications de l'utilisateur connecté"""
        return Notification.objects.filter(utilisateur=self.request.user)
    
    @action(detail=True, methods=['post'])
    def marquer_comme_lue(self, request, pk=None):
        """Marquer une notification comme lue"""
        notification = self.get_object()
        notification.statut = Notification.Statut.LUE
        notification.date_lecture = timezone.now()
        notification.save()
        return Response({'status': 'Notification marquée comme lue'})
    
    @action(detail=False, methods=['post'])
    def marquer_tout_comme_lu(self, request):
        """Marquer toutes les notifications comme lues"""
        notifications = self.get_queryset().exclude(statut='lue')
        notifications.update(
            statut=Notification.Statut.LUE,
            date_lecture=timezone.now()
        )
        return Response({'count': notifications.count()})


class RappelPaiementViewSet(viewsets.ModelViewSet):
    """ViewSet pour les rappels de paiement"""
    queryset = RappelPaiement.objects.all()
    serializer_class = RappelPaiementSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['est_envoye', 'type_rappel']
    
    @action(detail=True, methods=['post'])
    def envoyer_rappel(self, request, pk=None):
        """Envoyer un rappel de paiement"""
        rappel = self.get_object()
        if rappel.est_envoye:
            return Response(
                {'error': 'Ce rappel a déjà été envoyé'},
                status=status.HTTP_400_BAD_REQUEST
            )
        rappel.est_envoye = True
        rappel.date_envoi_reel = timezone.now()
        rappel.save()
        return Response({'status': 'Rappel envoyé'})
