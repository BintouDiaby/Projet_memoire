from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets, filters, status
from django.db.models import Sum, Count, Q
from utilisateurs.models import Utilisateur
from biens.models import Bien
from contrats.models import Contrat, Paiement
from facturation.models import Facture, Notification
from django.utils import timezone
from datetime import timedelta
from .models import (
    StatistiquesProprietaire, TableauBordLocataire, AlerteSysteme,
    LogActivite, RapportMensuel, ConfigurationDashboard
)
from .serializers import (
    StatistiquesProprietaireSerializer, TableauBordLocataireSerializer,
    AlerteSystemeSerializer, LogActiviteSerializer, RapportMensuelSerializer,
    ConfigurationDashboardSerializer
)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_proprietaire(request):
    """Dashboard pour un propriétaire"""
    utilisateur = request.user
    
    if utilisateur.role != 'proprietaire':
        return Response({'error': 'Accès non autorisé'}, status=403)
    
    # Récupérer ou créer les statistiques
    stats, _ = StatistiquesProprietaire.objects.get_or_create(proprietaire=utilisateur)
    stats.mettre_a_jour_statistiques()
    
    serializer = StatistiquesProprietaireSerializer(stats)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_locataire(request):
    """Dashboard pour un locataire"""
    utilisateur = request.user
    
    if utilisateur.role != 'locataire':
        return Response({'error': 'Accès non autorisé'}, status=403)
    
    # Récupérer ou créer les données du dashboard
    tableau_bord, _ = TableauBordLocataire.objects.get_or_create(locataire=utilisateur)
    
    # Mettre à jour les données
    tableau_bord.nombre_contrats_actifs = Contrat.objects.filter(
        locataire=utilisateur,
        statut='en_cours'
    ).count()
    
    tableau_bord.nombre_recherches_sauvegardees = utilisateur.recherches_sauvegardees.count()
    tableau_bord.nombre_biens_favoris = utilisateur.biens_favoris.count()
    
    # Paiements
    paiements_retard = Paiement.objects.filter(
        contrat__locataire=utilisateur,
        statut__in=['retard_mineur', 'retard_majeur', 'impaye']
    )
    tableau_bord.paiements_en_retard = paiements_retard.count()
    tableau_bord.montant_en_retard = paiements_retard.aggregate(Sum('montant_du'))['montant_du__sum'] or 0
    
    tableau_bord.save()
    
    serializer = TableauBordLocataireSerializer(tableau_bord)
    return Response(serializer.data)


class StatistiquesProprietaireViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les statistiques des propriétaires"""
    queryset = StatistiquesProprietaire.objects.all()
    serializer_class = StatistiquesProprietaireSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Récupérer les statistiques de l'utilisateur"""
        if self.request.user.role == 'proprietaire':
            return StatistiquesProprietaire.objects.filter(proprietaire=self.request.user)
        return StatistiquesProprietaire.objects.none()


class AlerteSystemeViewSet(viewsets.ModelViewSet):
    """ViewSet pour les alertes système"""
    serializer_class = AlerteSystemeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'severite']
    ordering = ['-date_creation']
    
    def get_queryset(self):
        """Récupérer les alertes pertinentes pour l'utilisateur"""
        user = self.request.user
        queryset = AlerteSysteme.objects.filter(statut='active')
        
        # Filtrer par rôle
        q_filter = Q(tout_le_monde=True)
        if user.role == 'proprietaire':
            q_filter |= Q(proprietaires=True)
        elif user.role == 'locataire':
            q_filter |= Q(locataires=True)
        
        # Ajouter les alertes spécifiques
        q_filter |= Q(utilisateurs_specifiques=user)
        
        return queryset.filter(q_filter).distinct()


class LogActiviteViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les logs d'activité"""
    serializer_class = LogActiviteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_activite', 'type_activite']
    ordering = ['-date_activite']
    
    def get_queryset(self):
        """Récupérer les logs de l'utilisateur"""
        return LogActivite.objects.filter(utilisateur=self.request.user)


class ConfigurationDashboardViewSet(viewsets.ModelViewSet):
    """ViewSet pour la configuration du dashboard"""
    serializer_class = ConfigurationDashboardSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Récupérer la configuration de l'utilisateur"""
        return ConfigurationDashboard.objects.filter(utilisateur=self.request.user)
    
    def perform_create(self, serializer):
        """Créer une configuration pour l'utilisateur"""
        serializer.save(utilisateur=self.request.user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rapport_mensuel(request):
    """Générer un rapport mensuel pour un propriétaire"""
    utilisateur = request.user
    
    if utilisateur.role != 'proprietaire':
        return Response({'error': 'Accès non autorisé'}, status=403)
    
    # Récupérer le mois
    mois = request.query_params.get('mois')
    if not mois:
        mois = timezone.now().date().replace(day=1)
    
    # Générer le rapport
    rapport, _ = RapportMensuel.objects.get_or_create(
        proprietaire=utilisateur,
        mois=mois
    )
    
    # Mettre à jour les données
    contrats_actifs = Contrat.objects.filter(
        proprietaire=utilisateur,
        statut='en_cours',
        date_debut__lte=timezone.now().date(),
        date_fin__gte=timezone.now().date()
    )
    
    rapport.nombre_proprietes = Bien.objects.filter(proprietaire=utilisateur).count()
    rapport.nombre_contrats_actifs = contrats_actifs.count()
    rapport.nombre_locataires = contrats_actifs.values('locataire').distinct().count()
    
    # Calculs financiers
    paiements = Paiement.objects.filter(
        contrat__proprietaire=utilisateur,
        mois=mois
    )
    
    rapport.revenu_attendu = paiements.aggregate(Sum('montant_du'))['montant_du__sum'] or 0
    rapport.revenu_recu = paiements.filter(
        statut='recu'
    ).aggregate(Sum('montant_recu'))['montant_recu__sum'] or 0
    rapport.montant_impaye = paiements.filter(
        statut__in=['impaye', 'retard_majeur']
    ).aggregate(Sum('montant_du'))['montant_du__sum'] or 0
    
    if rapport.revenu_attendu > 0:
        rapport.taux_collecte = (rapport.revenu_recu / rapport.revenu_attendu) * 100
    
    rapport.save()
    
    serializer = RapportMensuelSerializer(rapport)
    return Response(serializer.data)
    
    # Récupérer les stats du propriétaire
    biens = Bien.objects.filter(proprietaire=utilisateur)
    contrats = Contrat.objects.filter(proprietaire=utilisateur)
    paiements_dus = Paiement.objects.filter(
        contrat__proprietaire=utilisateur,
        statut__in=[Paiement.Statut.RETARD_MINEUR, Paiement.Statut.RETARD_MAJEUR, Paiement.Statut.IMPAYE]
    )
    
    # Calculs
    stats = {
        'nombre_biens': biens.count(),
        'nombre_biens_loues': biens.filter(statut=Bien.Statut.LOUE).count(),
        'nombre_contrats_actifs': contrats.filter(statut=Contrat.Statut.EN_COURS).count(),
        'revenus_mensuels': contrats.filter(statut=Contrat.Statut.EN_COURS).aggregate(
            total=Sum('prix_mensuel')
        )['total'] or 0,
        'paiements_en_retard': paiements_dus.count(),
        'montant_en_retard': paiements_dus.aggregate(
            total=Sum('montant_du')
        )['total'] or 0,
    }
    
    # Graphiques (données simples pour exemple)
    factures_recentes = Facture.objects.filter(contrat__proprietaire=utilisateur).order_by('-date_generation')[:5]
    
    return Response({
        'stats': stats,
        'factures_recentes': [
            {'numero': f.numero_facture, 'montant': str(f.montant_total), 'statut': f.statut}
            for f in factures_recentes
        ]
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_locataire(request):
    """Dashboard pour un locataire"""
    utilisateur = request.user
    
    if utilisateur.role != Utilisateur.Role.LOCATAIRE:
        return Response({'error': 'Accès non autorisé'}, status=403)
    
    # Récupérer les infos du locataire
    contrats = Contrat.objects.filter(locataire=utilisateur, statut=Contrat.Statut.EN_COURS)
    paiements = Paiement.objects.filter(
        contrat__locataire=utilisateur
    ).order_by('-mois')
    
    # Calculs
    stats = {
        'nombre_contrats_actifs': contrats.count(),
        'loyer_total_mensuel': contrats.aggregate(Sum('prix_mensuel'))['prix_mensuel__sum'] or 0,
        'paiements_a_venir': paiements.filter(statut=Paiement.Statut.EN_ATTENTE).count(),
        'montant_du': paiements.filter(
            statut=Paiement.Statut.EN_ATTENTE
        ).aggregate(Sum('montant_du'))['montant_du__sum'] or 0,
    }
    
    # Factures récentes
    factures = Facture.objects.filter(
        paiement__contrat__locataire=utilisateur
    ).order_by('-date_generation')[:5]
    
    return Response({
        'stats': stats,
        'factures': [
            {
                'numero': f.numero_facture,
                'montant': str(f.montant_total),
                'date_echéance': str(f.date_echéance),
                'statut': f.statut
            }
            for f in factures
        ]
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_admin(request):
    """Dashboard pour l'administrateur"""
    if not request.user.is_staff:
        return Response({'error': 'Accès non autorisé'}, status=403)
    
    # Stats globales
    stats = {
        'nombre_utilisateurs': Utilisateur.objects.count(),
        'nombre_biens': Bien.objects.count(),
        'nombre_contrats': Contrat.objects.count(),
        'nombre_factures': Facture.objects.count(),
        'paiements_impayees': Paiement.objects.filter(statut=Paiement.Statut.IMPAYE).count(),
        'montant_impaye': Paiement.objects.filter(
            statut=Paiement.Statut.IMPAYE
        ).aggregate(Sum('montant_du'))['montant_du__sum'] or 0,
    }
    
    return Response({'stats': stats})



from django.contrib.auth.decorators import login_required


@login_required
def dashboard_company(request):
    """Vue UI pour les entreprises nouvellement inscrites.
    Rend la page `dashboard_entreprise_vide.html` avec le contexte attendu.
    """
    user = request.user
    real_company = getattr(user, 'company', None)

    # Si l'utilisateur a une company réelle, compter ses biens.
    if real_company is not None:
        biens_count = Bien.objects.filter(proprietaire__company=real_company).count()
        display_company = real_company
    else:
        biens_count = 0
        # Objet léger pour l'affichage uniquement (NE PAS le passer au ORM)
        class TempCompany:
            pass
        display_company = TempCompany()
        display_company.name = f"{user.username} Company"
        display_company.types = []
        display_company.est_verifiee = False
    # Indicateurs pour les "premiers pas"
    user_profile_complete = bool(request.user.telephone and request.user.adresse and request.user.photo_profil)
    documents_verifies = bool(getattr(request.user, 'documents_verifies', False))

    steps_completed = 0
    # Etape 1 : compte créé (toujours done)
    steps_completed += 1
    # Etape 2 : profil complété
    if user_profile_complete:
        steps_completed += 1
    # Etape 3 : documents vérifiés
    if documents_verifies:
        steps_completed += 1
    # Etape 4 : au moins un bien publié
    if biens_count > 0:
        steps_completed += 1

    context = {
        'entreprise': display_company,
        'biens_count': biens_count,
        'profile_complete': user_profile_complete,
        'documents_verifies': documents_verifies,
        'steps_completed': steps_completed,
    }
    return render(request, 'dashboard/dashboard_entreprise_vide.html', context)
