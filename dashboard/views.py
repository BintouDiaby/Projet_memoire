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
            return StatistiquesProprietaire.objects.filter(proprietaire__in=self.request.user.comptes_entreprise())
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
from utilisateurs.decorators import acces_requis


# Les activités choisies à l'inscription/onboarding sont enregistrées sous des
# libellés fins (ex: "location_maison"). Le dashboard entreprise raisonne par
# grand module (location/vente/terrain/construction) : ce mapping fait le lien
# entre les deux, sans quoi aucune activité n'apparaît jamais comme active.
TYPE_TO_MODULE = {
    'location_maison': 'location',
    'location_bureau': 'location',
    'colocation': 'location',
    'location': 'location',
    'vente_maison': 'vente',
    'vente_commercial': 'vente',
    'vente': 'vente',
    'vente_terrain': 'terrain',
    'terrain': 'terrain',
    'construction': 'construction',
}


def _modules_actifs(company):
    """Déduit les modules (location/vente/terrain/construction) actifs à partir
    des types réellement enregistrés sur la company."""
    raw_types = list(company.types or []) if company else []
    return sorted({TYPE_TO_MODULE[t] for t in raw_types if t in TYPE_TO_MODULE})


def _crm_pipeline(user):
    """Répartit les contacts d'un propriétaire en 5 étapes de pipeline
    (prospects → visites → négociation → clients actifs → anciens clients),
    déduites des conversations/visites/contrats existants (pas de modèle "lead" dédié).
    Retourne des dicts {locataire_id: objet le plus pertinent}."""
    from messagerie.models import Conversation
    from biens.models import Visite

    contrats_actifs = (
        Contrat.objects.filter(proprietaire__in=user.comptes_entreprise(), statut=Contrat.Statut.EN_COURS)
        .select_related('locataire', 'bien')
    )
    clients_contrats = {c.locataire_id: c for c in contrats_actifs if c.locataire}

    contrats_termines = (
        Contrat.objects.filter(proprietaire__in=user.comptes_entreprise(), statut__in=[Contrat.Statut.TERMINE, Contrat.Statut.RESILIE])
        .select_related('locataire', 'bien').order_by('-date_fin')
    )
    clients_anciens = {
        c.locataire_id: c for c in contrats_termines
        if c.locataire and c.locataire_id not in clients_contrats
    }

    visites_confirmees = (
        Visite.objects.filter(bien__proprietaire__in=user.comptes_entreprise(), statut=Visite.Statut.CONFIRMEE)
        .select_related('locataire', 'bien')
    )
    clients_negociation = {
        v.locataire_id: v for v in visites_confirmees if v.locataire_id not in clients_contrats
    }

    visites_attente = (
        Visite.objects.filter(bien__proprietaire__in=user.comptes_entreprise(), statut=Visite.Statut.EN_ATTENTE)
        .select_related('locataire', 'bien').order_by('date_visite')
    )
    clients_visites = {
        v.locataire_id: v for v in visites_attente
        if v.locataire_id not in clients_contrats and v.locataire_id not in clients_negociation
    }

    convs = (
        Conversation.objects.filter(proprietaire__in=user.comptes_entreprise())
        .select_related('demandeur', 'bien').order_by('-mis_a_jour_le')
    )
    clients_prospects = {
        conv.demandeur_id: conv for conv in convs
        if conv.demandeur_id not in clients_contrats
        and conv.demandeur_id not in clients_negociation
        and conv.demandeur_id not in clients_visites
        and conv.demandeur_id not in clients_anciens
    }

    return {
        'prospects': clients_prospects,
        'visites': clients_visites,
        'negociation': clients_negociation,
        'contrats': clients_contrats,
        'anciens': clients_anciens,
    }


@login_required
def dashboard_company(request):
    from django.utils import timezone
    from django.shortcuts import redirect
    from messagerie.models import Conversation, Message
    from biens.models import Visite
    from contrats.models import Reclamation
    from construction.models import ProjetConstruction, NotificationConstruction
    from .services import NotificationService

    user = request.user
    if user.role == Utilisateur.Role.LOCATAIRE:
        return redirect('mon_espace_locataire')

    company = getattr(user, 'company', None)
    types = _modules_actifs(company)

    company_name = (company.name if company else None) or user.get_full_name() or user.username
    company_initial = company_name[0].upper() if company_name else '?'

    biens_qs = Bien.objects.filter(proprietaire__in=user.comptes_entreprise())
    biens_count = biens_qs.count()

    try:
        prof = user.proprietaire_profile
        profile_complete = bool(prof.nom_entreprise)
        documents_verifies = bool(prof.certification)
        rccm_rempli = bool(prof.numero_siret_siren)
    except Exception:
        prof = None
        profile_complete = False
        documents_verifies = False
        rccm_rempli = False

    # ── Checklist de complétude (remplace l'ancien "2/4" incohérent) ──
    checklist = [
        {'label': "Compte entreprise créé", 'done': True},
        {'label': "Compléter le profil (nom, description)", 'done': profile_complete},
        {'label': "Ajouter vos coordonnées (adresse, téléphone)", 'done': bool(company and company.adresse and company.telephone)},
        {'label': "Renseigner votre RCCM", 'done': rccm_rempli},
        {'label': "Ajouter un logo", 'done': bool(company and company.logo)},
        {'label': "Publier votre premier bien", 'done': biens_count > 0},
    ]
    steps_completed = sum(1 for s in checklist if s['done'])
    steps_total = len(checklist)
    completion_pct = round(100 * steps_completed / steps_total)

    nb_messages_non_lus = sum(
        conv.messages.filter(lu=False).exclude(expediteur=user).count()
        for conv in Conversation.objects.filter(proprietaire__in=user.comptes_entreprise())
    )
    nb_rdv_en_attente = Visite.objects.filter(
        bien__proprietaire__in=user.comptes_entreprise(), statut=Visite.Statut.EN_ATTENTE
    ).count()
    from facturation.models import RendezVousPaiement
    nb_rdv_en_attente += RendezVousPaiement.objects.filter(
        facture__contrat__proprietaire__in=user.comptes_entreprise(), statut=RendezVousPaiement.Statut.EN_ATTENTE
    ).count()
    nb_reclamations_ouvertes = Reclamation.objects.filter(
        bien__proprietaire__in=user.comptes_entreprise(), statut=Reclamation.Statut.OUVERTE
    ).count()
    nb_devis_en_attente = 0
    nb_notifs = NotificationService.unread_count(user)
    if 'construction' in types and company:
        nb_devis_en_attente = ProjetConstruction.objects.filter(
            entreprise=company, statut=ProjetConstruction.Statut.EN_ATTENTE
        ).count()
    from facturation.models import Facture
    nb_a_valider = Facture.objects.filter(
        contrat__proprietaire__in=user.comptes_entreprise(), statut=Facture.Statut.EN_VALIDATION
    ).count()
    from utilisateurs.models import Tache, DemandeConge
    nb_taches_a_faire = Tache.objects.filter(assignee_a=user, statut=Tache.Statut.A_FAIRE).count()
    nb_conges_en_attente = 0
    if user.role == Utilisateur.Role.PROPRIETAIRE:
        nb_conges_en_attente = DemandeConge.objects.filter(
            demandeur__in=user.comptes_entreprise(), statut=DemandeConge.Statut.EN_ATTENTE
        ).exclude(demandeur=user).count()

    # ── Cartes statistiques ──
    nb_clients = (
        Contrat.objects.filter(proprietaire__in=user.comptes_entreprise()).exclude(locataire=None)
        .values('locataire').distinct().count()
    )
    nb_paiements = Paiement.objects.filter(contrat__proprietaire__in=user.comptes_entreprise()).count()
    nb_conversations = Conversation.objects.filter(proprietaire__in=user.comptes_entreprise()).count()
    nb_rdv_total = Visite.objects.filter(bien__proprietaire__in=user.comptes_entreprise()).exclude(
        statut__in=[Visite.Statut.ANNULEE, Visite.Statut.REFUSEE]
    ).count()

    # ── Aperçus (messages / rendez-vous / devis) — les pages dédiées ont le détail ──
    messages_recents = [
        {'conv': conv, 'dernier': conv.dernier_message(), 'nb_non_lus': conv.nb_non_lus_pour(user)}
        for conv in Conversation.objects.filter(proprietaire__in=user.comptes_entreprise()).select_related('demandeur', 'bien').order_by('-mis_a_jour_le')[:4]
    ]
    rdv_prochains = list(
        Visite.objects.filter(bien__proprietaire__in=user.comptes_entreprise(), date_visite__gte=timezone.now())
        .exclude(statut__in=[Visite.Statut.ANNULEE, Visite.Statut.REFUSEE])
        .select_related('bien', 'locataire').order_by('date_visite')[:4]
    )
    devis_recents = []
    if 'construction' in types and company:
        devis_recents = list(
            ProjetConstruction.objects.filter(entreprise=company, statut=ProjetConstruction.Statut.EN_ATTENTE)
            .select_related('client').order_by('-cree_le')[:4]
        )

    # ── Pipeline CRM (résumé — la page /dashboard/clients/ a le détail) ──
    pipeline = _crm_pipeline(user)
    crm_counts = {k: len(v) for k, v in pipeline.items()}

    # ── Modules avec de vrais compteurs (plus de démo) ──
    modules_data = []
    if 'location' in types:
        modules_data.append({
            'key': 'location', 'label': 'Location',
            'metrics': [
                (biens_qs.filter(transaction_type__in=['location', 'both']).exclude(type_bien='terrain').count(), 'biens en location'),
                (Contrat.objects.filter(proprietaire__in=user.comptes_entreprise(), statut=Contrat.Statut.EN_COURS).count(), 'contrats actifs'),
            ],
        })
    if 'vente' in types:
        modules_data.append({
            'key': 'vente', 'label': 'Vente',
            'metrics': [
                (biens_qs.filter(transaction_type__in=['vente', 'both']).exclude(type_bien='terrain').count(), 'biens en vente'),
                (Visite.objects.filter(bien__proprietaire__in=user.comptes_entreprise(), bien__transaction_type__in=['vente', 'both']).count(), 'visites programmées'),
            ],
        })
    if 'terrain' in types:
        modules_data.append({
            'key': 'terrain', 'label': 'Terrains',
            'metrics': [
                (biens_qs.filter(type_bien='terrain').count(), 'parcelles'),
                (Visite.objects.filter(bien__proprietaire__in=user.comptes_entreprise(), bien__type_bien='terrain').count(), 'visites'),
            ],
        })
    if 'construction' in types:
        modules_data.append({
            'key': 'construction', 'label': 'Construction',
            'metrics': [
                (ProjetConstruction.objects.filter(entreprise=company).count() if company else 0, 'projets'),
                (nb_devis_en_attente, 'devis en attente'),
            ],
        })

    # ── Activité récente (synthétisée depuis les modèles existants —
    # pas de nouveau modèle : LogActivite existe mais n'est écrit nulle part) ──
    activites = []
    for b in biens_qs.exclude(date_publication=None).order_by('-date_publication')[:5]:
        activites.append({'type': 'bien', 'titre': f"Bien publié — {b.titre}", 'date': b.date_publication})
    for c in Contrat.objects.filter(proprietaire__in=user.comptes_entreprise()).select_related('bien').order_by('-date_creation')[:5]:
        activites.append({'type': 'contrat', 'titre': f"Contrat {c.get_statut_display().lower()} — {c.bien.titre}", 'date': c.date_creation})
    for p in Paiement.objects.filter(contrat__proprietaire__in=user.comptes_entreprise(), statut=Paiement.Statut.RECU, date_paiement__isnull=False).select_related('contrat__bien').order_by('-date_paiement')[:5]:
        activites.append({
            'type': 'paiement', 'titre': f"Paiement reçu — {p.contrat.bien.titre}",
            'date': timezone.make_aware(timezone.datetime.combine(p.date_paiement, timezone.datetime.min.time())),
        })
    for m in Message.objects.filter(conversation__proprietaire__in=user.comptes_entreprise()).exclude(expediteur=user).select_related('expediteur').order_by('-cree_le')[:5]:
        activites.append({'type': 'message', 'titre': f"Message reçu de {m.expediteur.get_full_name() or m.expediteur.username}", 'date': m.cree_le})
    for v in Visite.objects.filter(bien__proprietaire__in=user.comptes_entreprise()).select_related('bien').order_by('-date_reservation')[:5]:
        activites.append({'type': 'visite', 'titre': f"Visite demandée — {v.bien.titre}", 'date': v.date_reservation})

    activites.sort(key=lambda a: a['date'], reverse=True)
    activites = activites[:8]

    context = {
        'company': company,
        'company_name': company_name,
        'company_initial': company_initial,
        'types': types,
        'biens_count': biens_count,
        'profile_complete': profile_complete,
        'documents_verifies': documents_verifies,
        'checklist': checklist,
        'steps_completed': steps_completed,
        'steps_total': steps_total,
        'completion_pct': completion_pct,
        'nb_clients': nb_clients,
        'nb_paiements': nb_paiements,
        'nb_conversations': nb_conversations,
        'nb_rdv_total': nb_rdv_total,
        'modules_data': modules_data,
        'activites': activites,
        'crm_counts': crm_counts,
        'messages_recents': messages_recents,
        'rdv_prochains': rdv_prochains,
        'devis_recents': devis_recents,
        'nb_messages_non_lus': nb_messages_non_lus,
        'nb_rdv_en_attente': nb_rdv_en_attente,
        'nb_reclamations_ouvertes': nb_reclamations_ouvertes,
        'nb_devis_en_attente': nb_devis_en_attente,
        'nb_notifs': nb_notifs,
        'nb_a_valider': nb_a_valider,
        'nb_taches_a_faire': nb_taches_a_faire,
        'nb_conges_en_attente': nb_conges_en_attente,
    }
    return render(request, 'dashboard/dashboard_company.html', context)


@login_required
def entreprise_profil(request):
    """Fiche profil de l'entreprise connectée : identité, coordonnées,
    documents vérifiés, services, zones couvertes, statistiques réelles."""
    from django.shortcuts import redirect
    from utilisateurs.models import ProprietaireProfile
    from construction.models import ProjetConstruction

    user = request.user
    if user.role == Utilisateur.Role.LOCATAIRE:
        return redirect('mon_espace_locataire')

    ctx = _sidebar_context(user)
    company = ctx['company']
    if not company:
        return redirect('company_profile_edit')

    prof, _ = ProprietaireProfile.objects.get_or_create(utilisateur=user)

    biens_qs = Bien.objects.filter(proprietaire__company=company)
    nb_locations = Contrat.objects.filter(proprietaire__company=company, statut=Contrat.Statut.EN_COURS).count()
    nb_constructions = 0
    if 'construction' in ctx['types']:
        nb_constructions = ProjetConstruction.objects.filter(entreprise=company).count()

    zones = sorted({v for v in biens_qs.exclude(ville__isnull=True).exclude(ville='').values_list('ville', flat=True)})

    ctx.update({
        'active_page': 'profil',
        'profile': prof,
        'nb_biens': biens_qs.count(),
        'nb_locations': nb_locations,
        'nb_constructions': nb_constructions,
        'zones': zones,
    })
    return render(request, 'dashboard/entreprise_profil.html', ctx)


ENTREPRISE_NOTIF_CATEGORIES = ['messages', 'visites', 'reclamations', 'devis', 'paiements']
ENTREPRISE_NOTIF_LABELS = {
    'messages': 'Nouveau message', 'visites': 'Nouvelle visite / rendez-vous',
    'reclamations': 'Nouvelle réclamation', 'devis': 'Nouvelle demande de devis',
    'paiements': 'Paiement reçu',
}
SERVICE_MODULES = ['location', 'vente', 'terrain', 'construction']
SERVICE_LABELS = {'location': 'Location', 'vente': 'Vente', 'terrain': 'Terrain', 'construction': 'Construction'}


@login_required
def entreprise_parametres(request):
    """Paramètres du compte entreprise : services, vérification, notifications,
    sécurité (mot de passe + sessions), fermeture du compte."""
    from django.shortcuts import redirect
    from django.contrib import messages as dj_messages
    from django.contrib.auth.forms import PasswordChangeForm
    from django.contrib.auth import update_session_auth_hash, logout as auth_logout
    from django.contrib.sessions.models import Session
    from utilisateurs.models import ProprietaireProfile

    user = request.user
    if user.role == Utilisateur.Role.LOCATAIRE:
        return redirect('mon_espace_locataire')

    company = getattr(user, 'company', None)
    if not company:
        return redirect('company_profile_edit')

    prof, _ = ProprietaireProfile.objects.get_or_create(utilisateur=user)
    password_form = None

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'services':
            selected = set(request.POST.getlist('services'))
            current = [t for t in (company.types or []) if t not in SERVICE_MODULES]
            company.types = current + sorted(selected)
            company.save(update_fields=['types'])
            dj_messages.success(request, "Services mis à jour.")
            return redirect('entreprise_parametres')

        elif action == 'notifications':
            prefs = dict(user.dashboard_preferences or {})
            prefs['notifications'] = {cat: (f'notif_{cat}' in request.POST) for cat in ENTREPRISE_NOTIF_CATEGORIES}
            user.dashboard_preferences = prefs
            user.save(update_fields=['dashboard_preferences'])
            dj_messages.success(request, "Préférences de notification enregistrées.")
            return redirect('entreprise_parametres')

        elif action == 'password':
            password_form = PasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                dj_messages.success(request, "Mot de passe mis à jour.")
                return redirect('entreprise_parametres')
            dj_messages.error(request, "Impossible de changer le mot de passe : vérifiez les champs ci-dessous.")

        elif action == 'revoke_session':
            session_key = request.POST.get('session_key', '')
            if session_key and session_key != request.session.session_key:
                Session.objects.filter(pk=session_key).delete()
                dj_messages.success(request, "Session déconnectée.")
            return redirect('entreprise_parametres')

        elif action == 'delete_account':
            confirm_text = request.POST.get('confirm_text', '').strip()
            if confirm_text != 'SUPPRIMER':
                dj_messages.error(request, "Tapez SUPPRIMER (en majuscules) pour confirmer.")
                return redirect('entreprise_parametres')
            # Contrat.proprietaire est en PROTECT : tout contrat (même terminé)
            # empêche la suppression du compte au niveau base de données.
            if Contrat.objects.filter(proprietaire__in=user.comptes_entreprise()).exists():
                dj_messages.error(request, "Votre compte a un historique de contrats — la fermeture directe n'est pas possible. Contactez le support pour archiver votre compte.")
                return redirect('entreprise_parametres')
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
        {'key': cat, 'label': ENTREPRISE_NOTIF_LABELS[cat], 'active': notif_prefs_raw.get(cat, True)}
        for cat in ENTREPRISE_NOTIF_CATEGORIES
    ]

    services_actifs = {t for t in (company.types or []) if t in SERVICE_MODULES}
    services = [{'key': m, 'label': SERVICE_LABELS[m], 'active': m in services_actifs} for m in SERVICE_MODULES]

    if password_form is None:
        password_form = PasswordChangeForm(user)

    ctx = _sidebar_context(user)
    ctx.update({
        'active_page': 'parametres',
        'profile': prof,
        'services': services,
        'notif_prefs': notif_prefs,
        'sessions': sessions,
        'password_form': password_form,
    })
    return render(request, 'dashboard/entreprise_parametres.html', ctx)


def _sidebar_context(user):
    """Contexte commun pour la sidebar des pages dashboard."""
    from messagerie.models import Conversation
    from biens.models import Visite, Reservation
    from contrats.models import Reclamation
    from construction.models import ProjetConstruction, NotificationConstruction
    from .services import NotificationService

    company = getattr(user, 'company', None)
    types = _modules_actifs(company)
    company_name = (company.name if company else None) or user.get_full_name() or user.username
    company_initial = company_name[0].upper() if company_name else '?'
    biens_count = Bien.objects.filter(proprietaire__in=user.comptes_entreprise()).count()

    try:
        prof = user.proprietaire_profile
        documents_verifies = bool(prof.certification)
    except Exception:
        documents_verifies = False

    nb_messages_non_lus = sum(
        conv.messages.filter(lu=False).exclude(expediteur=user).count()
        for conv in Conversation.objects.filter(proprietaire__in=user.comptes_entreprise())
    )
    nb_rdv_en_attente = Visite.objects.filter(
        bien__proprietaire__in=user.comptes_entreprise(), statut=Visite.Statut.EN_ATTENTE
    ).count()
    from facturation.models import RendezVousPaiement
    nb_rdv_en_attente += RendezVousPaiement.objects.filter(
        facture__contrat__proprietaire__in=user.comptes_entreprise(), statut=RendezVousPaiement.Statut.EN_ATTENTE
    ).count()
    nb_reservations_en_attente = Reservation.objects.filter(
        bien__proprietaire__in=user.comptes_entreprise(), statut=Reservation.Statut.EN_ATTENTE
    ).count()
    nb_reclamations_ouvertes = Reclamation.objects.filter(
        bien__proprietaire__in=user.comptes_entreprise(), statut=Reclamation.Statut.OUVERTE
    ).count()
    nb_devis_en_attente = 0
    nb_notifs = NotificationService.unread_count(user)
    if 'construction' in types and company:
        nb_devis_en_attente = ProjetConstruction.objects.filter(
            entreprise=company, statut=ProjetConstruction.Statut.EN_ATTENTE
        ).count()
    from facturation.models import Facture
    nb_a_valider = Facture.objects.filter(
        contrat__proprietaire__in=user.comptes_entreprise(), statut=Facture.Statut.EN_VALIDATION
    ).count()
    from utilisateurs.models import Tache, DemandeConge
    nb_taches_a_faire = Tache.objects.filter(assignee_a=user, statut=Tache.Statut.A_FAIRE).count()
    nb_conges_en_attente = 0
    if user.role == Utilisateur.Role.PROPRIETAIRE:
        nb_conges_en_attente = DemandeConge.objects.filter(
            demandeur__in=user.comptes_entreprise(), statut=DemandeConge.Statut.EN_ATTENTE
        ).exclude(demandeur=user).count()

    return {
        'company': company,
        'company_name': company_name,
        'company_initial': company_initial,
        'types': types,
        'biens_count': biens_count,
        'documents_verifies': documents_verifies,
        'nb_messages_non_lus': nb_messages_non_lus,
        'nb_rdv_en_attente': nb_rdv_en_attente,
        'nb_reservations_en_attente': nb_reservations_en_attente,
        'nb_reclamations_ouvertes': nb_reclamations_ouvertes,
        'nb_devis_en_attente': nb_devis_en_attente,
        'nb_notifs': nb_notifs,
        'nb_a_valider': nb_a_valider,
        'nb_taches_a_faire': nb_taches_a_faire,
        'nb_conges_en_attente': nb_conges_en_attente,
    }


@login_required
@acces_requis('acces_commercial')
def mes_biens(request):
    """Liste des biens du propriétaire connecté (distincte de /biens/, qui est
    la vitrine publique de tous les biens disponibles sur la plateforme)."""
    from django.shortcuts import redirect

    user = request.user
    if user.role == Utilisateur.Role.LOCATAIRE:
        return redirect('mon_espace_locataire')
    ctx = _sidebar_context(user)

    mes_biens_qs = (
        Bien.objects.filter(proprietaire__in=user.comptes_entreprise())
        .order_by('-date_creation')
    )

    ctx.update({'active_page': 'biens', 'mes_biens': mes_biens_qs})
    return render(request, 'dashboard/mes_biens.html', ctx)


@login_required
@acces_requis('acces_commercial', 'acces_gestion_locative', 'acces_comptable')
def rdv_view(request):
    from biens.models import Visite
    from construction.models import ProjetConstruction
    from facturation.models import RendezVousPaiement
    from django.utils import timezone
    from django.shortcuts import redirect

    user = request.user
    if user.role == Utilisateur.Role.LOCATAIRE:
        return redirect('mon_espace_locataire')
    ctx = _sidebar_context(user)

    visites = (
        Visite.objects
        .filter(bien__proprietaire__in=user.comptes_entreprise())
        .exclude(statut__in=[Visite.Statut.ANNULEE, Visite.Statut.REFUSEE])
        .select_related('bien', 'locataire')
        .order_by('date_visite')
    )

    rdv_construction = []
    company = ctx['company']
    if company and 'construction' in ctx['types']:
        rdv_construction = list(
            ProjetConstruction.objects
            .filter(entreprise=company, date_rdv__isnull=False)
            .select_related('client')
            .order_by('date_rdv')
        )

    rdv_paiements = (
        RendezVousPaiement.objects
        .filter(facture__contrat__proprietaire__in=user.comptes_entreprise())
        .exclude(statut__in=[RendezVousPaiement.Statut.REFUSE, RendezVousPaiement.Statut.HONORE])
        .select_related('facture__contrat__bien', 'locataire')
        .order_by('date_demandee')
    )

    ctx.update({
        'visites': visites,
        'rdv_construction': rdv_construction,
        'rdv_paiements': rdv_paiements,
        'today': timezone.now(),
    })
    return render(request, 'dashboard/rdv.html', ctx)


@login_required
@acces_requis('acces_comptable')
def statistiques_view(request):
    """Page Statistiques du propriétaire : revenus, taux de collecte,
    impayés — calculés par StatistiquesProprietaire.mettre_a_jour_statistiques(),
    jusqu'ici uniquement exposés en JSON via /api/dashboard/proprietaire/ et
    jamais affichés sur aucune page."""
    from django.shortcuts import redirect
    from dateutil.relativedelta import relativedelta

    user = request.user
    if user.role == Utilisateur.Role.LOCATAIRE:
        return redirect('mon_espace_locataire')
    ctx = _sidebar_context(user)

    stats, _ = StatistiquesProprietaire.objects.get_or_create(proprietaire=user)
    stats.mettre_a_jour_statistiques()

    aujourd_hui = timezone.now().date()
    historique = []
    for i in range(5, -1, -1):
        mois = (aujourd_hui.replace(day=1) - relativedelta(months=i))
        paiements_mois = Paiement.objects.filter(contrat__proprietaire__in=user.comptes_entreprise(), mois=mois)
        agg = paiements_mois.aggregate(du=Sum('montant_du'), recu=Sum('montant_recu'))
        historique.append({
            'label': mois.strftime('%b %Y'),
            'attendu': agg['du'] or 0,
            'recu': agg['recu'] or 0,
        })
    max_montant = max([h['attendu'] for h in historique] + [1])
    for h in historique:
        h['pct_attendu'] = round(100 * float(h['attendu']) / float(max_montant)) if max_montant else 0
        h['pct_recu'] = round(100 * float(h['recu']) / float(max_montant)) if max_montant else 0

    repartition_biens = list(
        Bien.objects.filter(proprietaire__in=user.comptes_entreprise()).values('type_bien').annotate(n=Count('id')).order_by('-n')
    )

    ctx.update({
        'stats': stats,
        'historique': historique,
        'repartition_biens': repartition_biens,
    })
    return render(request, 'dashboard/statistiques.html', ctx)


@login_required
def personnel_view(request):
    """Page « Personnel » — liste des collaborateurs de l'entreprise,
    réservée au Directeur (le compte role=PROPRIETAIRE fondateur). Les
    employés (role=GESTIONNAIRE) voient les mêmes données que le Directeur
    partout ailleurs, mais ne gèrent pas eux-mêmes le personnel à cette étape."""
    from django.shortcuts import redirect
    from utilisateurs.models import Collaborateur

    user = request.user
    if user.role != Utilisateur.Role.PROPRIETAIRE:
        return redirect('dashboard')
    ctx = _sidebar_context(user)

    comptes = list(
        user.comptes_entreprise()
        .select_related('collaborateur_profile')
        .order_by('-date_creation')
    )
    directeur = next((c for c in comptes if c.role == Utilisateur.Role.PROPRIETAIRE), user)
    membres = [c for c in comptes if hasattr(c, 'collaborateur_profile')]
    nb_comptes_actifs = sum(1 for c in comptes if c.is_active)

    ctx.update({
        'directeur': directeur,
        'membres': membres,
        'nb_employes': len(membres),
        'nb_comptes_actifs': nb_comptes_actifs,
        'postes': Collaborateur.Poste.choices,
        'nb_roles': len(Collaborateur.Poste.choices),
    })
    return render(request, 'dashboard/personnel.html', ctx)


@login_required
def modifier_collaborateur(request, user_id):
    """Le Directeur modifie les coordonnées/le poste d'un employé existant."""
    from django.shortcuts import redirect
    from django.http import Http404
    from django.contrib import messages
    from utilisateurs.models import Collaborateur

    user = request.user
    if user.role != Utilisateur.Role.PROPRIETAIRE:
        return redirect('dashboard')

    employe = user.comptes_entreprise().filter(id=user_id).exclude(id=user.id).first()
    if not employe or not hasattr(employe, 'collaborateur_profile'):
        raise Http404('Collaborateur introuvable')

    if request.method == 'POST':
        employe.first_name = (request.POST.get('prenom') or '').strip()
        employe.last_name = (request.POST.get('nom') or '').strip()
        employe.telephone = (request.POST.get('telephone') or '').strip()
        email = (request.POST.get('email') or '').strip()
        if email:
            employe.email = email
        employe.save()

        poste = request.POST.get('poste')
        if poste in dict(Collaborateur.Poste.choices):
            profil = employe.collaborateur_profile
            profil.poste = poste
            profil.appliquer_preset_poste()
            profil.save(update_fields=['poste', 'acces_commercial', 'acces_comptable', 'acces_gestion_locative'])

        messages.success(request, f"Profil de {employe.get_full_name() or employe.username} mis à jour.")
        return redirect('personnel')

    ctx = _sidebar_context(user)
    ctx.update({'employe': employe, 'postes': Collaborateur.Poste.choices})
    return render(request, 'dashboard/personnel_modifier.html', ctx)


@login_required
def ajouter_collaborateur(request):
    """Le Directeur invite un nouvel employé : crée le compte (role=GESTIONNAIRE,
    même company), son profil Collaborateur, et lui envoie ses identifiants."""
    from django.shortcuts import redirect
    from django.contrib import messages
    from django.utils.text import slugify
    from django.utils.crypto import get_random_string
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from utilisateurs.models import Collaborateur

    user = request.user
    if user.role != Utilisateur.Role.PROPRIETAIRE:
        return redirect('dashboard')
    if request.method != 'POST':
        return redirect('personnel')

    prenom = (request.POST.get('prenom') or '').strip()
    nom = (request.POST.get('nom') or '').strip()
    telephone = (request.POST.get('telephone') or '').strip()
    email = (request.POST.get('email') or '').strip()
    poste = request.POST.get('poste') or Collaborateur.Poste.ASSISTANT

    if not (prenom and nom and email):
        messages.error(request, "Nom, prénom et email sont obligatoires.")
        return redirect('personnel')
    if not user.company_id:
        messages.error(request, "Complétez d'abord le profil de votre entreprise.")
        return redirect('personnel')

    base_username = slugify(f"{prenom}.{nom}") or 'collaborateur'
    username = base_username
    suffixe = 1
    while Utilisateur.objects.filter(username=username).exists():
        suffixe += 1
        username = f"{base_username}{suffixe}"

    mot_de_passe = get_random_string(10)
    employe = Utilisateur.objects.create_user(
        username=username,
        email=email,
        password=mot_de_passe,
        first_name=prenom,
        last_name=nom,
        telephone=telephone,
        role=Utilisateur.Role.GESTIONNAIRE,
        company_id=user.company_id,
    )
    collab = Collaborateur(utilisateur=employe, poste=poste, invite_par=user)
    collab.appliquer_preset_poste()
    collab.save()

    if email:
        try:
            contenu = render_to_string('registration/email_invitation_collaborateur.txt', {
                'employe': employe,
                'invite_par': user,
                'company_name': user.company.name,
                'poste_label': dict(Collaborateur.Poste.choices).get(poste, poste),
                'mot_de_passe': mot_de_passe,
                'login_url': request.build_absolute_uri('/accounts/login/company/'),
            })
            send_mail(
                "Votre accès ImmoGérer — " + user.company.name,
                contenu, None, [email], fail_silently=True,
            )
        except Exception:
            pass

    messages.success(
        request,
        f"Compte créé pour {employe.get_full_name()} — identifiant « {username} », "
        f"mot de passe temporaire « {mot_de_passe} » (également envoyé par email)."
    )
    return redirect('personnel')


@login_required
def toggle_collaborateur_actif(request, user_id):
    """Active/désactive le compte d'un collaborateur — bloque sa connexion
    (Django AuthenticationForm refuse déjà is_active=False nativement)."""
    from django.shortcuts import redirect
    from django.contrib import messages

    user = request.user
    if user.role != Utilisateur.Role.PROPRIETAIRE or request.method != 'POST':
        return redirect('dashboard')

    employe = user.comptes_entreprise().filter(id=user_id).exclude(id=user.id).first()
    if not employe:
        messages.error(request, "Collaborateur introuvable.")
        return redirect('personnel')

    employe.is_active = not employe.is_active
    employe.save(update_fields=['is_active'])
    messages.success(
        request,
        f"{employe.get_full_name() or employe.username} est maintenant "
        f"{'actif' if employe.is_active else 'désactivé'}."
    )
    return redirect('personnel')


@login_required
def reinitialiser_mot_de_passe_collaborateur(request, user_id):
    """Le mot de passe temporaire n'est affiché/envoyé qu'une seule fois à la
    création — le Directeur n'a ensuite aucun moyen de le retrouver. Cette
    vue génère et communique un nouveau mot de passe temporaire."""
    from django.shortcuts import redirect
    from django.contrib import messages
    from django.utils.crypto import get_random_string
    from django.core.mail import send_mail
    from django.template.loader import render_to_string

    user = request.user
    if user.role != Utilisateur.Role.PROPRIETAIRE or request.method != 'POST':
        return redirect('dashboard')

    employe = user.comptes_entreprise().filter(id=user_id).exclude(id=user.id).first()
    if not employe:
        messages.error(request, "Collaborateur introuvable.")
        return redirect('personnel')

    nouveau_mdp = get_random_string(10)
    employe.set_password(nouveau_mdp)
    employe.save(update_fields=['password'])

    if employe.email:
        try:
            profil = getattr(employe, 'collaborateur_profile', None)
            contenu = render_to_string('registration/email_invitation_collaborateur.txt', {
                'employe': employe,
                'invite_par': user,
                'company_name': user.company.name if user.company else '',
                'poste_label': profil.get_poste_display() if profil else '',
                'mot_de_passe': nouveau_mdp,
                'login_url': request.build_absolute_uri('/accounts/login/company/'),
            })
            send_mail(
                "Nouveau mot de passe ImmoGérer — " + (user.company.name if user.company else ''),
                contenu, None, [employe.email], fail_silently=True,
            )
        except Exception:
            pass

    messages.success(
        request,
        f"Nouveau mot de passe pour {employe.get_full_name() or employe.username} : "
        f"« {nouveau_mdp} » (également envoyé par email)."
    )
    return redirect('personnel')


@login_required
def voir_collaborateur(request, user_id):
    """Fiche d'un collaborateur : coordonnées, poste, et activité mesurable
    avec les données existantes (biens publiés, contrats créés, messages
    envoyés, dernière connexion) — pas de journal d'activité dédié pour
    l'instant (ce sera une étape ultérieure si le besoin va au-delà)."""
    from django.shortcuts import redirect
    from django.http import Http404
    from messagerie.models import Message
    from utilisateurs.models import Tache

    user = request.user
    if user.role != Utilisateur.Role.PROPRIETAIRE:
        return redirect('dashboard')

    employe = user.comptes_entreprise().filter(id=user_id).exclude(id=user.id).first()
    if not employe or not hasattr(employe, 'collaborateur_profile'):
        raise Http404('Collaborateur introuvable')

    ctx = _sidebar_context(user)
    ctx.update({
        'employe': employe,
        'nb_biens_publies': Bien.objects.filter(proprietaire=employe).count(),
        'nb_contrats_crees': Contrat.objects.filter(proprietaire=employe).count(),
        'nb_messages_envoyes': Message.objects.filter(expediteur=employe).count(),
        'taches': Tache.objects.filter(assignee_a=employe).order_by('statut', 'date_limite', '-date_creation'),
    })
    return render(request, 'dashboard/personnel_activite.html', ctx)


@login_required
def creer_tache(request, user_id):
    """Le Directeur assigne une tâche à un collaborateur."""
    from django.shortcuts import redirect
    from django.contrib import messages
    from utilisateurs.models import Tache

    user = request.user
    if user.role != Utilisateur.Role.PROPRIETAIRE or request.method != 'POST':
        return redirect('dashboard')

    employe = user.comptes_entreprise().filter(id=user_id).exclude(id=user.id).first()
    if not employe:
        messages.error(request, "Collaborateur introuvable.")
        return redirect('personnel')

    titre = (request.POST.get('titre') or '').strip()
    if not titre:
        messages.error(request, "Le titre de la tâche est obligatoire.")
        return redirect('voir_collaborateur', user_id=employe.id)

    Tache.objects.create(
        assignee_a=employe,
        creee_par=user,
        titre=titre,
        description=(request.POST.get('description') or '').strip(),
        date_limite=request.POST.get('date_limite') or None,
    )
    messages.success(request, f"Tâche assignée à {employe.get_full_name() or employe.username}.")
    return redirect('voir_collaborateur', user_id=employe.id)


@login_required
def mes_taches_view(request):
    """Liste des tâches assignées à l'utilisateur connecté (Directeur ou
    employé) — accessible à tout compte de l'entreprise, sans restriction
    par poste : chacun voit ses propres tâches."""
    from django.shortcuts import redirect
    from utilisateurs.models import Tache

    user = request.user
    if user.role == Utilisateur.Role.LOCATAIRE:
        return redirect('mon_espace_locataire')
    ctx = _sidebar_context(user)

    ctx.update({
        'taches': Tache.objects.filter(assignee_a=user).select_related('creee_par').order_by('statut', 'date_limite', '-date_creation'),
        'today': timezone.now().date(),
    })
    return render(request, 'dashboard/mes_taches.html', ctx)


@login_required
def marquer_tache_faite(request, tache_id):
    """Bascule une tâche entre « à faire » et « faite » — uniquement par la
    personne à qui elle est assignée."""
    from django.shortcuts import redirect
    from django.utils import timezone
    from utilisateurs.models import Tache

    if request.method != 'POST':
        return redirect('mes_taches')

    tache = Tache.objects.filter(id=tache_id, assignee_a=request.user).first()
    if tache:
        if tache.statut == Tache.Statut.FAIT:
            tache.statut = Tache.Statut.A_FAIRE
            tache.date_terminee = None
        else:
            tache.statut = Tache.Statut.FAIT
            tache.date_terminee = timezone.now()
        tache.save(update_fields=['statut', 'date_terminee'])

    next_url = request.POST.get('next') or 'mes_taches'
    return redirect(next_url)


@login_required
def performances_view(request):
    """Vue comparative des performances de l'équipe — réservée au Directeur.
    Basée sur les mêmes compteurs mesurables que la fiche individuelle
    (`voir_collaborateur`), pas de journal d'activité dédié."""
    from django.shortcuts import redirect
    from messagerie.models import Message
    from utilisateurs.models import Tache

    user = request.user
    if user.role != Utilisateur.Role.PROPRIETAIRE:
        return redirect('dashboard')
    ctx = _sidebar_context(user)

    membres = list(
        user.comptes_entreprise().exclude(id=user.id).select_related('collaborateur_profile')
    )
    perf = []
    for m in membres:
        perf.append({
            'employe': m,
            'nb_biens': Bien.objects.filter(proprietaire=m).count(),
            'nb_contrats': Contrat.objects.filter(proprietaire=m).count(),
            'nb_messages': Message.objects.filter(expediteur=m).count(),
            'nb_taches_faites': Tache.objects.filter(assignee_a=m, statut=Tache.Statut.FAIT).count(),
            'nb_taches_en_cours': Tache.objects.filter(assignee_a=m, statut=Tache.Statut.A_FAIRE).count(),
        })
    perf.sort(key=lambda p: p['nb_biens'] + p['nb_contrats'] + p['nb_messages'], reverse=True)

    ctx.update({'perf': perf})
    return render(request, 'dashboard/performances.html', ctx)


@login_required
def mes_conges_view(request):
    """Demandes de congé de l'utilisateur connecté — Directeur ou employé,
    accessible à tout membre de l'entreprise sans restriction par poste."""
    from django.shortcuts import redirect
    from django.contrib import messages
    from utilisateurs.models import DemandeConge

    user = request.user
    if user.role == Utilisateur.Role.LOCATAIRE:
        return redirect('mon_espace_locataire')

    if request.method == 'POST':
        date_debut = request.POST.get('date_debut')
        date_fin = request.POST.get('date_fin')
        if not date_debut or not date_fin:
            messages.error(request, "Les deux dates sont obligatoires.")
        elif date_fin < date_debut:
            messages.error(request, "La date de fin doit être après la date de début.")
        else:
            DemandeConge.objects.create(
                demandeur=user, date_debut=date_debut, date_fin=date_fin,
                motif=(request.POST.get('motif') or '').strip(),
            )
            messages.success(request, "Demande de congé envoyée.")
        return redirect('mes_conges')

    ctx = _sidebar_context(user)
    ctx.update({
        'conges': DemandeConge.objects.filter(demandeur=user).order_by('-date_demande'),
    })
    return render(request, 'dashboard/mes_conges.html', ctx)


@login_required
def conges_view(request):
    """Le Directeur consulte et traite les demandes de congé de son équipe."""
    from django.shortcuts import redirect
    from utilisateurs.models import DemandeConge

    user = request.user
    if user.role != Utilisateur.Role.PROPRIETAIRE:
        return redirect('dashboard')
    ctx = _sidebar_context(user)

    ctx.update({
        'conges': DemandeConge.objects.filter(demandeur__in=user.comptes_entreprise())
        .exclude(demandeur=user).select_related('demandeur').order_by('statut', '-date_demande'),
    })
    return render(request, 'dashboard/conges.html', ctx)


@login_required
def traiter_conge(request, conge_id):
    """Le Directeur accepte ou refuse une demande de congé."""
    from django.shortcuts import redirect
    from django.contrib import messages
    from django.utils import timezone
    from utilisateurs.models import DemandeConge

    user = request.user
    if user.role != Utilisateur.Role.PROPRIETAIRE or request.method != 'POST':
        return redirect('dashboard')

    conge = DemandeConge.objects.filter(
        id=conge_id, demandeur__in=user.comptes_entreprise()
    ).exclude(demandeur=user).first()
    if not conge:
        messages.error(request, "Demande introuvable.")
        return redirect('conges')

    action = request.POST.get('action')
    if action == 'accepter':
        conge.statut = DemandeConge.Statut.ACCEPTE
    elif action == 'refuser':
        conge.statut = DemandeConge.Statut.REFUSE
    else:
        return redirect('conges')

    conge.traite_par = user
    conge.date_traitement = timezone.now()
    conge.save(update_fields=['statut', 'traite_par', 'date_traitement'])
    messages.success(
        request,
        f"Demande de {conge.demandeur.get_full_name() or conge.demandeur.username} "
        f"{'acceptée' if action == 'accepter' else 'refusée'}."
    )
    return redirect('conges')


@login_required
def mon_planning_view(request):
    """Agenda personnel : mes tâches avec échéance, les rendez-vous partagés
    de l'entreprise que mon poste m'autorise à voir, et mes congés acceptés
    à venir. Les visites/RDV ne sont pas assignés à un employé précis dans
    ce système (ils restent partagés par toute l'entreprise, cf. Étape 1) —
    ce planning montre donc « ce qui est à venir et que je peux traiter »,
    pas une affectation individuelle stricte."""
    from django.shortcuts import redirect
    from biens.models import Visite
    from facturation.models import RendezVousPaiement
    from utilisateurs.models import Tache, DemandeConge

    user = request.user
    if user.role == Utilisateur.Role.LOCATAIRE:
        return redirect('mon_espace_locataire')
    ctx = _sidebar_context(user)

    today = timezone.now().date()
    evenements = []

    for t in Tache.objects.filter(assignee_a=user, date_limite__isnull=False).exclude(statut=Tache.Statut.FAIT):
        evenements.append({'date': t.date_limite, 'type': 'tache', 'label': 'Tâche', 'titre': t.titre, 'lien': '/mes-taches/'})

    if user.a_acces('acces_commercial', 'acces_gestion_locative'):
        visites = Visite.objects.filter(
            bien__proprietaire__in=user.comptes_entreprise(), date_visite__date__gte=today
        ).exclude(statut__in=[Visite.Statut.ANNULEE, Visite.Statut.REFUSEE]).select_related('bien')
        for v in visites:
            evenements.append({'date': v.date_visite.date(), 'heure': v.date_visite, 'type': 'visite', 'label': 'Visite', 'titre': v.bien.titre, 'lien': '/dashboard/rdv/'})

    if user.a_acces('acces_comptable'):
        rdv_paiements = RendezVousPaiement.objects.filter(
            facture__contrat__proprietaire__in=user.comptes_entreprise(),
            statut=RendezVousPaiement.Statut.CONFIRME, date_confirmee__date__gte=today,
        ).select_related('facture')
        for r in rdv_paiements:
            evenements.append({'date': r.date_confirmee.date(), 'heure': r.date_confirmee, 'type': 'paiement', 'label': 'RDV paiement', 'titre': r.facture.numero_facture, 'lien': '/dashboard/rdv/'})

    conges = DemandeConge.objects.filter(demandeur=user, statut=DemandeConge.Statut.ACCEPTE, date_fin__gte=today)
    for c in conges:
        evenements.append({'date': c.date_debut, 'type': 'conge', 'label': 'Congé', 'titre': f"jusqu'au {c.date_fin.strftime('%d/%m/%Y')}", 'lien': '/mes-conges/'})

    evenements.sort(key=lambda e: (e['date'], e.get('heure') is None))

    ctx.update({'evenements': evenements, 'today': today})
    return render(request, 'dashboard/planning.html', ctx)


@login_required
def taches_equipe_view(request):
    """Le Directeur n'a pas de tâches personnelles à suivre — il suit celles
    de son équipe pour voir l'avancement de chacun."""
    from django.shortcuts import redirect
    from utilisateurs.models import Tache

    user = request.user
    if user.role != Utilisateur.Role.PROPRIETAIRE:
        return redirect('dashboard')
    ctx = _sidebar_context(user)

    ctx.update({
        'taches': Tache.objects.filter(assignee_a__in=user.comptes_entreprise())
        .exclude(assignee_a=user).select_related('assignee_a', 'creee_par')
        .order_by('statut', 'date_limite', '-date_creation'),
    })
    return render(request, 'dashboard/taches_equipe.html', ctx)


@login_required
def planning_equipe_view(request):
    """Le Directeur voit le planning agrégé de toute son équipe (tâches par
    employé, rendez-vous partagés de l'entreprise, congés acceptés à venir)
    plutôt qu'un planning personnel — il n'a pas de tâches/RDV qui lui sont
    assignés en propre dans ce système."""
    from django.shortcuts import redirect
    from biens.models import Visite
    from facturation.models import RendezVousPaiement
    from utilisateurs.models import Tache, DemandeConge

    user = request.user
    if user.role != Utilisateur.Role.PROPRIETAIRE:
        return redirect('dashboard')
    ctx = _sidebar_context(user)

    today = timezone.now().date()
    membres = list(user.comptes_entreprise().exclude(id=user.id))
    evenements = []

    for t in Tache.objects.filter(
        assignee_a__in=membres, date_limite__isnull=False
    ).exclude(statut=Tache.Statut.FAIT).select_related('assignee_a'):
        evenements.append({
            'date': t.date_limite, 'type': 'tache', 'label': 'Tâche',
            'titre': t.titre, 'employe': t.assignee_a,
            'lien': f'/dashboard/personnel/{t.assignee_a.id}/voir/',
        })

    visites = Visite.objects.filter(
        bien__proprietaire__in=user.comptes_entreprise(), date_visite__date__gte=today
    ).exclude(statut__in=[Visite.Statut.ANNULEE, Visite.Statut.REFUSEE]).select_related('bien')
    for v in visites:
        evenements.append({
            'date': v.date_visite.date(), 'heure': v.date_visite, 'type': 'visite',
            'label': 'Visite', 'titre': v.bien.titre, 'employe': None, 'lien': '/dashboard/rdv/',
        })

    rdv_paiements = RendezVousPaiement.objects.filter(
        facture__contrat__proprietaire__in=user.comptes_entreprise(),
        statut=RendezVousPaiement.Statut.CONFIRME, date_confirmee__date__gte=today,
    ).select_related('facture')
    for r in rdv_paiements:
        evenements.append({
            'date': r.date_confirmee.date(), 'heure': r.date_confirmee, 'type': 'paiement',
            'label': 'RDV paiement', 'titre': r.facture.numero_facture, 'employe': None, 'lien': '/dashboard/rdv/',
        })

    conges = DemandeConge.objects.filter(
        demandeur__in=membres, statut=DemandeConge.Statut.ACCEPTE, date_fin__gte=today
    ).select_related('demandeur')
    for c in conges:
        evenements.append({
            'date': c.date_debut, 'type': 'conge', 'label': 'Congé',
            'titre': f"jusqu'au {c.date_fin.strftime('%d/%m/%Y')}", 'employe': c.demandeur,
            'lien': '/dashboard/conges/',
        })

    evenements.sort(key=lambda e: (e['date'], e.get('heure') is None))

    ctx.update({'evenements': evenements, 'today': today})
    return render(request, 'dashboard/planning_equipe.html', ctx)


@login_required
def notifications_locataire_view(request):
    """Liste complète des notifications du locataire — jusqu'ici, le lien
    « Tout voir » de la cloche renvoyait vers la page notifications réservée
    aux comptes entreprise, qui redirige tout locataire droit vers
    /mon-espace/ : un aller-retour sans fin qui ne montrait jamais la liste."""
    from django.shortcuts import redirect
    from .models import Notification
    from .services import NotificationService

    user = request.user
    if user.role != Utilisateur.Role.LOCATAIRE:
        return redirect('dashboard_notifications')

    notifications = list(
        Notification.objects.filter(destinataire=user).select_related('expediteur').order_by('-date_creation')[:100]
    )
    nb_non_lues = NotificationService.unread_count(user)

    return render(request, 'notifications_locataire.html', {
        'notifications': notifications,
        'nb_non_lues': nb_non_lues,
    })


@login_required
def notifications_view(request):
    from construction.models import NotificationConstruction
    from .models import Notification
    from django.shortcuts import redirect

    user = request.user
    if user.role == Utilisateur.Role.LOCATAIRE:
        return redirect('mes_notifications_locataire')
    ctx = _sidebar_context(user)

    notifs = []

    # Notifications unifiées (message, visite, devis, réclamation...) —
    # créées via NotificationService.send() au moment de l'action.
    ICON_MAP = {'message': 'message', 'visite': 'rdv'}
    for n in Notification.objects.filter(destinataire=user).select_related('expediteur').order_by('-date_creation')[:30]:
        # Toujours passer par la vue de marquage-lu, avec un `next` de repli
        # vers la liste elle-même si la notification n'a pas de lien propre
        # (paiement, contrat, réservation, mise en demeure...) — sinon
        # cliquer « Voir → » ne marquait jamais ces notifications comme lues.
        notifs.append({
            'id': n.id,
            'type': ICON_MAP.get(n.type_notification, 'autre'),
            'titre': n.titre,
            'detail': n.message[:80],
            'lien': n.lien or '#',
            'mark_url': f'/dashboard/notifications/lire/{n.id}/?next={n.lien or "/dashboard/notifications/"}',
            'date': n.date_creation,
            'lue': n.lue,
        })

    # Notifications construction (modèle séparé) — même correctif : passer
    # par une vue de marquage-lu dédiée avant d'atterrir sur le projet.
    for n in NotificationConstruction.objects.filter(destinataire=user).select_related('projet').order_by('-cree_le')[:20]:
        lien = f'/construction/projet/{n.projet_id}/'
        notifs.append({
            'type': 'construction',
            'titre': n.get_type_display(),
            'detail': n.message[:80],
            'lien': lien,
            'mark_url': f'/dashboard/notifications/construction/lire/{n.id}/?next={lien}',
            'date': n.cree_le,
            'lue': n.lue,
        })

    notifs.sort(key=lambda x: x['date'], reverse=True)
    ctx['notifs'] = notifs
    return render(request, 'dashboard/notifications.html', ctx)


@login_required
def notification_marquer_lue(request, notif_id):
    from django.shortcuts import redirect
    from .services import NotificationService

    NotificationService.mark_read(request.user, notif_id)
    next_url = request.GET.get('next') or '/dashboard/notifications/'
    return redirect(next_url)


@login_required
def notification_construction_marquer_lue(request, notif_id):
    """Équivalent de `notification_marquer_lue` pour les notifications du
    module construction (modèle séparé `NotificationConstruction`) — sans
    cette vue, cliquer « Voir → » sur ce type de notification menait
    directement au projet sans jamais passer par un marquage-lu."""
    from django.shortcuts import redirect
    from .services import NotificationService

    NotificationService.mark_read_construction(request.user, notif_id)
    next_url = request.GET.get('next') or '/dashboard/notifications/'
    return redirect(next_url)


@login_required
def notifications_marquer_toutes_lues(request):
    from django.shortcuts import redirect
    from .services import NotificationService

    if request.method == 'POST':
        NotificationService.mark_all_read(request.user)
    return redirect(request.POST.get('next') or request.GET.get('next') or '/dashboard/notifications/')


@login_required
def notification_supprimer(request, notif_id):
    from django.shortcuts import redirect
    from .services import NotificationService

    if request.method == 'POST':
        NotificationService.delete(request.user, notif_id)
    next_url = request.POST.get('next') or request.GET.get('next') or '/dashboard/notifications/'
    return redirect(next_url)


@login_required
@acces_requis('acces_commercial', 'acces_gestion_locative')
def clients_crm_view(request):
    from messagerie.models import Conversation
    from biens.models import Visite
    from django.shortcuts import redirect

    user = request.user
    if user.role == Utilisateur.Role.LOCATAIRE:
        return redirect('mon_espace_locataire')
    ctx = _sidebar_context(user)

    # Contrats actifs → clients actifs
    contrats_actifs = (
        Contrat.objects
        .filter(proprietaire__in=user.comptes_entreprise(), statut=Contrat.Statut.EN_COURS)
        .select_related('locataire', 'bien')
    )
    clients_contrats = {c.locataire_id: c for c in contrats_actifs if c.locataire}

    # Contrats terminés → anciens clients
    contrats_termines = (
        Contrat.objects
        .filter(proprietaire__in=user.comptes_entreprise(), statut__in=[Contrat.Statut.TERMINE, Contrat.Statut.RESILIE])
        .select_related('locataire', 'bien')
        .order_by('-date_fin')
    )
    clients_anciens = {c.locataire_id: c for c in contrats_termines if c.locataire and c.locataire_id not in clients_contrats}

    # Visites confirmées sans contrat → négociation
    visites_confirmees = (
        Visite.objects
        .filter(bien__proprietaire__in=user.comptes_entreprise(), statut=Visite.Statut.CONFIRMEE)
        .select_related('locataire', 'bien')
    )
    clients_negociation = {
        v.locataire_id: v for v in visites_confirmees
        if v.locataire_id not in clients_contrats
    }

    # Visites en attente → visites programmées
    visites_attente = (
        Visite.objects
        .filter(bien__proprietaire__in=user.comptes_entreprise(), statut=Visite.Statut.EN_ATTENTE)
        .select_related('locataire', 'bien')
        .order_by('date_visite')
    )
    clients_visites = {
        v.locataire_id: v for v in visites_attente
        if v.locataire_id not in clients_contrats and v.locataire_id not in clients_negociation
    }

    # Conversations sans visite ni contrat → prospects
    convs = (
        Conversation.objects
        .filter(proprietaire__in=user.comptes_entreprise())
        .select_related('demandeur', 'bien')
        .order_by('-mis_a_jour_le')
    )
    clients_prospects = {
        conv.demandeur_id: conv for conv in convs
        if conv.demandeur_id not in clients_contrats
        and conv.demandeur_id not in clients_negociation
        and conv.demandeur_id not in clients_visites
        and conv.demandeur_id not in clients_anciens
    }

    nb_prospects = len(clients_prospects)
    nb_visites = len(clients_visites)
    nb_negociation = len(clients_negociation)
    nb_contrats = len(clients_contrats)
    nb_anciens = len(clients_anciens)

    nb_contacts_total = nb_prospects + nb_visites + nb_negociation + nb_contrats + nb_anciens
    nb_en_cours = nb_prospects + nb_visites + nb_negociation
    aujourd_hui = timezone.now()
    nb_signes_ce_mois = Contrat.objects.filter(
        proprietaire__in=user.comptes_entreprise(), statut=Contrat.Statut.EN_COURS,
        date_creation__year=aujourd_hui.year, date_creation__month=aujourd_hui.month,
    ).count()
    taux_conversion = round(100 * nb_contrats / nb_contacts_total) if nb_contacts_total else 0

    ctx.update({
        'clients_contrats': list(clients_contrats.values()),
        'clients_negociation': list(clients_negociation.values()),
        'clients_visites': list(clients_visites.values()),
        'clients_prospects': list(clients_prospects.values()),
        'clients_anciens': list(clients_anciens.values()),
        'nb_prospects': nb_prospects,
        'nb_visites': nb_visites,
        'nb_negociation': nb_negociation,
        'nb_contrats': nb_contrats,
        'nb_anciens': nb_anciens,
        'nb_contacts_total': nb_contacts_total,
        'nb_en_cours': nb_en_cours,
        'nb_signes_ce_mois': nb_signes_ce_mois,
        'taux_conversion': taux_conversion,
    })
    return render(request, 'dashboard/clients.html', ctx)


@login_required
@acces_requis('acces_gestion_locative')
def reclamations_view(request):
    from contrats.models import Reclamation
    from django.shortcuts import redirect

    user = request.user
    if user.role == Utilisateur.Role.LOCATAIRE:
        return redirect('mon_espace_locataire')
    ctx = _sidebar_context(user)

    if request.method == 'POST':
        rec_id = request.POST.get('reclamation_id')
        action = request.POST.get('action')
        reponse = request.POST.get('reponse', '')
        if rec_id:
            rec = Reclamation.objects.filter(id=rec_id, bien__proprietaire__in=user.comptes_entreprise()).first()
            if rec:
                if action == 'resoudre':
                    rec.statut = Reclamation.Statut.RESOLUE
                    if reponse:
                        rec.reponse = reponse
                    rec.save()
                elif action == 'fermer':
                    rec.statut = Reclamation.Statut.FERMEE
                    rec.save()
                elif action == 'repondre' and reponse:
                    rec.reponse = reponse
                    rec.statut = Reclamation.Statut.EN_COURS
                    rec.save()
        return redirect('dashboard_reclamations')

    reclamations = (
        Reclamation.objects
        .filter(bien__proprietaire__in=user.comptes_entreprise())
        .select_related('bien', 'locataire')
        .order_by('-cree_le')
    )
    ctx['reclamations'] = reclamations
    return render(request, 'dashboard/reclamations.html', ctx)


@login_required
@acces_requis('acces_commercial', 'acces_gestion_locative')
def client_detail_view(request, client_id):
    from django.shortcuts import get_object_or_404, redirect
    from messagerie.models import Conversation
    from biens.models import Visite
    from contrats.models import Reclamation

    user = request.user
    if user.role == Utilisateur.Role.LOCATAIRE:
        return redirect('mon_espace_locataire')
    ctx = _sidebar_context(user)
    client = get_object_or_404(Utilisateur, id=client_id)

    conversations = (
        Conversation.objects.filter(proprietaire__in=user.comptes_entreprise(), demandeur=client)
        .select_related('bien').order_by('-mis_a_jour_le')
    )
    visites = (
        Visite.objects.filter(bien__proprietaire__in=user.comptes_entreprise(), locataire=client)
        .select_related('bien').order_by('-date_visite')
    )
    contrats = (
        Contrat.objects.filter(proprietaire__in=user.comptes_entreprise(), locataire=client)
        .select_related('bien').order_by('-date_creation')
    )
    paiements = (
        Paiement.objects.filter(contrat__proprietaire__in=user.comptes_entreprise(), contrat__locataire=client)
        .select_related('contrat__bien').order_by('-mois')
    )
    reclamations = (
        Reclamation.objects.filter(bien__proprietaire__in=user.comptes_entreprise(), locataire=client)
        .select_related('bien').order_by('-cree_le')
    )

    projets_construction = []
    company = ctx['company']
    if company and 'construction' in ctx['types']:
        from construction.models import ProjetConstruction
        projets_construction = list(
            ProjetConstruction.objects.filter(entreprise=company, client=client)
            .order_by('-cree_le')
        )

    ctx.update({
        'client': client,
        'conversations': conversations,
        'visites': visites,
        'contrats': contrats,
        'paiements': paiements,
        'reclamations': reclamations,
        'projets_construction': projets_construction,
    })
    return render(request, 'dashboard/client_detail.html', ctx)


@login_required
@acces_requis('acces_commercial')
def devis_view(request):
    from construction.models import ProjetConstruction
    from django.shortcuts import redirect

    user = request.user
    if user.role == Utilisateur.Role.LOCATAIRE:
        return redirect('mon_espace_locataire')
    ctx = _sidebar_context(user)
    company = ctx['company']

    projets = []
    if company:
        projets = list(
            ProjetConstruction.objects
            .filter(entreprise=company)
            .select_related('client')
            .order_by('-cree_le')
        )

    ctx['projets'] = projets
    return render(request, 'dashboard/devis.html', ctx)


@login_required
def facturation_dashboard_view(request):
    from facturation.models import Facture, RappelPaiement
    from django.db.models import Sum
    from django.shortcuts import redirect
    from django.contrib import messages
    from .services import NotificationService

    user = request.user
    today = timezone.now().date()

    # ── Locataire : ses propres factures ──────────────────────────────────────
    if user.role == Utilisateur.Role.LOCATAIRE:
        factures = (
            Facture.objects
            .filter(contrat__locataire=user)
            .select_related('contrat__bien', 'contrat__proprietaire', 'paiement')
            .order_by('-date_generation')
        )
        total_paye = factures.filter(statut=Facture.Statut.PAYEE).aggregate(t=Sum('montant_total'))['t'] or 0
        total_du = factures.filter(statut__in=[Facture.Statut.GENEREE, Facture.Statut.ENVOYEE]).aggregate(t=Sum('montant_total'))['t'] or 0
        total_retard = factures.filter(
            statut__in=[Facture.Statut.GENEREE, Facture.Statut.ENVOYEE],
            date_echéance__lt=today
        ).aggregate(t=Sum('montant_total'))['t'] or 0

        factures_list = list(factures)
        for f in factures_list:
            f.est_retard = f.date_echéance < today and f.statut not in (Facture.Statut.PAYEE, Facture.Statut.EN_VALIDATION, Facture.Statut.ANNULEE)

        nb_notifs = NotificationService.unread_count(user)
        nb_factures_retard = sum(1 for f in factures_list if f.est_retard)

        # Prochaine échéance à régler (retard prioritaire, puis la plus proche)
        a_payer = [f for f in factures_list if f.statut in (Facture.Statut.GENEREE, Facture.Statut.ENVOYEE)]
        prochaine_echeance = None
        if a_payer:
            prochaine_echeance = sorted(a_payer, key=lambda f: f.date_echéance)[0]

        nb_contrats_actifs = Contrat.objects.filter(locataire=user, statut=Contrat.Statut.EN_COURS).count()

        # Timeline du contrat concerné (celui de la prochaine échéance, sinon le premier contrat actif)
        contrat_ref = prochaine_echeance.contrat if prochaine_echeance else (
            Contrat.objects.filter(locataire=user, statut=Contrat.Statut.EN_COURS).select_related('bien').first()
        )
        timeline = []
        if contrat_ref:
            if contrat_ref.date_signature:
                timeline.append({'titre': 'Contrat signé', 'date': contrat_ref.date_signature, 'attente': False})
            factures_payees = sorted(
                [f for f in factures_list if f.contrat_id == contrat_ref.id and f.statut == Facture.Statut.PAYEE and f.date_paiement],
                key=lambda f: f.date_paiement
            )
            for f in factures_payees:
                mois_label = f.paiement.mois.strftime('%B %Y') if f.paiement else ''
                timeline.append({'titre': f"Loyer de {mois_label} réglé", 'date': f.date_paiement, 'attente': False})
            if prochaine_echeance and prochaine_echeance.contrat_id == contrat_ref.id:
                mois_label = prochaine_echeance.paiement.mois.strftime('%B %Y') if prochaine_echeance.paiement else ''
                timeline.append({'titre': f"Paiement de {mois_label} attendu", 'date': prochaine_echeance.date_echéance, 'attente': True})

        import json
        from facturation.models import MoyenPaiementEnregistre
        moyens_paiement = {
            m.mode_paiement: {'numero': m.numero, 'numero_masque': m.numero_masque()}
            for m in MoyenPaiementEnregistre.objects.filter(utilisateur=user)
        }

        return render(request, 'dashboard/facturation_locataire.html', {
            'factures': factures_list,
            'total_paye': total_paye,
            'total_du': total_du,
            'total_retard': total_retard,
            'today': today,
            'nb_notifs': nb_notifs,
            'nb_factures_retard': nb_factures_retard,
            'prochaine_echeance': prochaine_echeance,
            'nb_contrats_actifs': nb_contrats_actifs,
            'contrat_ref': contrat_ref,
            'timeline': timeline,
            'moyens_paiement_json': json.dumps(moyens_paiement),
        })

    # ── Propriétaire / gestionnaire : toutes les factures de ses contrats ─────
    if not user.a_acces('acces_comptable'):
        messages.error(request, "Vous n'avez pas accès à cette page.")
        return redirect('dashboard_company')
    ctx = _sidebar_context(user)

    if request.method == 'POST':
        action = request.POST.get('action')
        facture_id = request.POST.get('facture_id')
        if facture_id and action == 'marquer_payee':
            facture = (
                Facture.objects
                .filter(id=facture_id, contrat__proprietaire__in=user.comptes_entreprise())
                .select_related('paiement')
                .first()
            )
            if facture and facture.statut != Facture.Statut.PAYEE:
                facture.statut = Facture.Statut.PAYEE
                facture.date_paiement = today
                facture.save()
                p = facture.paiement
                p.statut = Paiement.Statut.RECU
                p.date_paiement = today
                p.montant_recu = p.montant_du
                p.save()
        return redirect('dashboard_facturation')

    factures = (
        Facture.objects
        .filter(contrat__proprietaire__in=user.comptes_entreprise())
        .select_related('contrat__bien', 'contrat__locataire', 'paiement')
        .order_by('-date_generation')
    )

    # Les totaux portent sur toutes les factures (l'archivage ne doit pas
    # fausser la comptabilité, seulement alléger la liste affichée).
    total_encaisse = factures.filter(statut=Facture.Statut.PAYEE).aggregate(t=Sum('montant_total'))['t'] or 0
    total_en_attente = factures.filter(statut__in=[Facture.Statut.GENEREE, Facture.Statut.ENVOYEE]).aggregate(t=Sum('montant_total'))['t'] or 0
    total_retard = factures.filter(
        statut__in=[Facture.Statut.GENEREE, Facture.Statut.ENVOYEE],
        date_echéance__lt=today
    ).aggregate(t=Sum('montant_total'))['t'] or 0
    nb_rappels = RappelPaiement.objects.filter(
        paiement__contrat__proprietaire__in=user.comptes_entreprise(),
        est_envoye=False,
        date_programmee__lte=timezone.now()
    ).count()

    voir_archives = request.GET.get('archives') == '1'
    nb_archives = factures.filter(est_archive=True).count()
    factures_affichees = factures.filter(est_archive=True) if voir_archives else factures.filter(est_archive=False)

    factures_list = list(factures_affichees)
    for f in factures_list:
        f.est_retard = f.date_echéance < today and f.statut not in (Facture.Statut.PAYEE, Facture.Statut.EN_VALIDATION, Facture.Statut.ANNULEE)

    ctx.update({
        'factures': factures_list,
        'total_encaisse': total_encaisse,
        'total_en_attente': total_en_attente,
        'total_retard': total_retard,
        'nb_rappels': nb_rappels,
        'today': today,
        'voir_archives': voir_archives,
        'nb_archives': nb_archives,
    })
    return render(request, 'dashboard/facturation.html', ctx)


MOYENS_PAIEMENT = ['Wave', 'Orange Money', 'MTN MoMo', 'Carte bancaire']

MOYEN_A_MODE_PAIEMENT = {
    'Wave': ('wave', 'WV'),
    'Orange Money': ('orange_money', 'OM'),
    'MTN MoMo': ('mtn', 'MTN'),
    'Carte bancaire': ('carte', 'CB'),
}


def _marquer_facture_payee(facture, payeur, moyen_label, mode_key=None, reference=None):
    """Marque une facture (et son Paiement lié) comme payée, et notifie le
    propriétaire. Partagé entre le flux auto-déclaré (Wave/OM/MTN, faute de
    passerelle réelle pour ces opérateurs) et le flux Stripe réel (carte)."""
    from facturation.models import Facture
    from contrats.models import Paiement
    from django.contrib import messages
    import random

    if facture.statut in (Facture.Statut.PAYEE, Facture.Statut.ANNULEE):
        return False

    today = timezone.now().date()
    facture.statut = Facture.Statut.PAYEE
    facture.date_paiement = today
    if mode_key:
        facture.mode_paiement = mode_key
        facture.reference_transaction = reference or f"{mode_key.upper()}-{random.randint(10000, 99999)}-CI"
    facture.save()
    p = facture.paiement
    p.statut = Paiement.Statut.RECU
    p.date_paiement = today
    p.montant_recu = p.montant_du
    p.save()

    from dashboard.services import NotificationService
    NotificationService.send(
        destinataire=facture.contrat.proprietaire, expediteur=payeur,
        type_notification='paiement',
        titre=f"Paiement reçu — {facture.contrat.bien.titre}",
        message=(
            f"{payeur.get_full_name() or payeur.username} a réglé "
            f"la facture {facture.numero_facture} via {moyen_label}."
        ),
        lien='/dashboard/facturation/',
    )
    return True


def _generer_reference_paiement():
    import random
    annee = timezone.now().year
    return f"PAY-{annee}-{random.randint(100000, 999999)}"


def _declarer_paiement(facture, payeur, moyen_label, mode_key, numero_paiement=''):
    """Le locataire déclare avoir réglé une facture (Wave/Orange Money/MTN
    MoMo — faute de passerelle réelle branchée pour ces opérateurs, contrairement
    à Stripe pour la carte). La facture passe en « en attente de validation »,
    PAS directement payée : le propriétaire doit confirmer la réception avant
    que le paiement soit définitif. Retourne (ok: bool, reference: str)."""
    from facturation.models import Facture

    if facture.statut in (Facture.Statut.PAYEE, Facture.Statut.EN_VALIDATION, Facture.Statut.ANNULEE):
        return False, facture.reference_transaction or ''

    reference = _generer_reference_paiement()
    facture.statut = Facture.Statut.EN_VALIDATION
    facture.mode_paiement = mode_key
    facture.reference_transaction = reference
    facture.numero_paiement_declare = numero_paiement
    facture.date_declaration_paiement = timezone.now()
    facture.save()

    from dashboard.services import NotificationService
    NotificationService.send(
        destinataire=facture.contrat.proprietaire, expediteur=payeur,
        type_notification='paiement',
        titre=f"Paiement déclaré — {facture.contrat.bien.titre}",
        message=(
            f"{payeur.get_full_name() or payeur.username} déclare avoir réglé "
            f"la facture {facture.numero_facture} via {moyen_label} (réf. {reference}). "
            f"Confirmez la réception pour finaliser."
        ),
        lien=f'/dashboard/facturation/{facture.id}/',
    )
    return True, reference


@login_required
def signaler_paiement(request):
    """Le locataire déclare le règlement d'une facture par Wave/Orange
    Money/MTN MoMo — la facture passe en attente de validation par le
    propriétaire (voir `confirmer_reception_paiement`). Le paiement par carte
    passe par Stripe (voir `stripe_creer_session`), pas par cette vue —
    confirmé automatiquement puisque Stripe vérifie le paiement lui-même."""
    from facturation.models import Facture
    from django.contrib import messages
    from django.shortcuts import redirect

    next_url = request.POST.get('next') or '/dashboard/facturation/'

    if request.method != 'POST':
        return redirect(next_url)

    facture = Facture.objects.select_related('contrat__bien', 'contrat__proprietaire', 'paiement').filter(
        id=request.POST.get('facture_id'), contrat__locataire=request.user
    ).first()
    if not facture:
        return redirect(next_url)

    moyen = request.POST.get('moyen_paiement', '').strip()
    if moyen not in MOYENS_PAIEMENT:
        moyen = 'un moyen non précisé'
    mode_key, prefixe = MOYEN_A_MODE_PAIEMENT.get(moyen, (None, None))
    numero_paiement = request.POST.get('numero_paiement', '').strip()

    if mode_key in ('wave', 'orange_money', 'mtn') and numero_paiement and request.POST.get('enregistrer_moyen') == 'on':
        from facturation.models import MoyenPaiementEnregistre
        MoyenPaiementEnregistre.objects.update_or_create(
            utilisateur=request.user, mode_paiement=mode_key, defaults={'numero': numero_paiement}
        )

    ok, reference = _declarer_paiement(facture, request.user, moyen, mode_key, numero_paiement)
    if ok:
        messages.success(request, "Votre paiement a été déclaré. Le propriétaire doit confirmer la réception.")
        return redirect(f'/dashboard/facturation/{facture.id}/?paiement_declare={reference}')

    return redirect(next_url)


@login_required
def demander_rdv_paiement(request):
    """Le locataire choisit de payer en espèces : au lieu de déclarer un
    paiement immédiat, il propose un créneau de rendez-vous en agence. La
    facture reste en l'état (GENEREE/ENVOYEE) tant que le rendez-vous n'a
    pas eu lieu — voir `confirmer_paiement_espece`."""
    from facturation.models import Facture, RendezVousPaiement
    from django.contrib import messages
    from django.shortcuts import redirect
    from datetime import datetime

    next_url = request.POST.get('next') or '/dashboard/facturation/'

    if request.method != 'POST':
        return redirect(next_url)

    facture = Facture.objects.select_related('contrat__bien', 'contrat__proprietaire').filter(
        id=request.POST.get('facture_id'), contrat__locataire=request.user
    ).first()
    if not facture or facture.statut in (Facture.Statut.PAYEE, Facture.Statut.EN_VALIDATION, Facture.Statut.ANNULEE):
        return redirect(next_url)

    date_str = request.POST.get('date_souhaitee', '').strip()
    heure_str = request.POST.get('heure_souhaitee', '').strip()
    message = request.POST.get('message', '').strip()
    try:
        date_demandee = timezone.make_aware(datetime.strptime(f"{date_str} {heure_str or '10:00'}", '%Y-%m-%d %H:%M'))
    except ValueError:
        messages.error(request, "Date ou heure invalide.")
        return redirect(next_url)

    rdv = RendezVousPaiement.objects.create(
        facture=facture, locataire=request.user, date_demandee=date_demandee, message=message,
    )

    from dashboard.services import NotificationService
    NotificationService.send(
        destinataire=facture.contrat.proprietaire, expediteur=request.user,
        type_notification='paiement',
        titre=f"Demande de rendez-vous de paiement — {facture.contrat.bien.titre}",
        message=(
            f"{request.user.get_full_name() or request.user.username} souhaite régler la facture "
            f"{facture.numero_facture} en espèces, le {date_demandee.strftime('%d/%m/%Y à %H:%M')}."
        ),
        lien=f'/dashboard/facturation/{facture.id}/',
    )
    messages.success(request, "Votre demande de rendez-vous a été envoyée à l'entreprise.")
    return redirect(f'/dashboard/facturation/{facture.id}/?rdv_demande={rdv.id}')


@login_required
def repondre_rdv_paiement(request):
    """Le propriétaire répond à une demande de rendez-vous de paiement en
    espèces : il accepte le créneau proposé, en propose un autre, ou refuse
    la demande."""
    from facturation.models import RendezVousPaiement
    from django.contrib import messages
    from django.shortcuts import redirect
    from datetime import datetime

    next_url = request.POST.get('next') or '/dashboard/facturation/'

    if request.method != 'POST':
        return redirect(next_url)

    rdv = RendezVousPaiement.objects.select_related('facture__contrat__bien', 'locataire').filter(
        id=request.POST.get('rdv_id'), facture__contrat__proprietaire__in=request.user.comptes_entreprise()
    ).first()
    if not rdv or rdv.statut not in (RendezVousPaiement.Statut.EN_ATTENTE, RendezVousPaiement.Statut.CONTRE_PROPOSITION):
        return redirect(next_url)

    from dashboard.services import NotificationService
    action = request.POST.get('action')

    if action == 'accepter':
        rdv.date_confirmee = rdv.date_demandee
        rdv.statut = RendezVousPaiement.Statut.CONFIRME
        rdv.save()
        messages.success(request, "Rendez-vous confirmé.")
        NotificationService.send(
            destinataire=rdv.locataire, expediteur=request.user,
            type_notification='paiement',
            titre="Rendez-vous de paiement confirmé",
            message=f"Votre rendez-vous pour la facture {rdv.facture.numero_facture} est confirmé le {rdv.date_confirmee.strftime('%d/%m/%Y à %H:%M')}.",
            lien=f'/dashboard/facturation/{rdv.facture.id}/',
        )
    elif action == 'proposer':
        date_str = request.POST.get('nouvelle_date', '').strip()
        heure_str = request.POST.get('nouvelle_heure', '').strip()
        try:
            date_proposee = timezone.make_aware(datetime.strptime(f"{date_str} {heure_str or '10:00'}", '%Y-%m-%d %H:%M'))
        except ValueError:
            messages.error(request, "Date ou heure invalide.")
            return redirect(next_url)
        rdv.date_proposee = date_proposee
        rdv.statut = RendezVousPaiement.Statut.CONTRE_PROPOSITION
        rdv.save()
        messages.success(request, "Nouveau créneau proposé au locataire.")
        NotificationService.send(
            destinataire=rdv.locataire, expediteur=request.user,
            type_notification='paiement',
            titre="Nouveau créneau proposé",
            message=f"L'entreprise propose un autre créneau pour la facture {rdv.facture.numero_facture} : le {date_proposee.strftime('%d/%m/%Y à %H:%M')}.",
            lien=f'/dashboard/facturation/{rdv.facture.id}/',
        )
    elif action == 'refuser':
        rdv.motif_refus = request.POST.get('motif', '').strip()
        rdv.statut = RendezVousPaiement.Statut.REFUSE
        rdv.save()
        messages.success(request, "Demande de rendez-vous refusée.")
        NotificationService.send(
            destinataire=rdv.locataire, expediteur=request.user,
            type_notification='paiement',
            titre="Demande de rendez-vous refusée",
            message=f"Votre demande de rendez-vous pour la facture {rdv.facture.numero_facture} a été refusée.{(' Motif : ' + rdv.motif_refus) if rdv.motif_refus else ''}",
            lien=f'/dashboard/facturation/{rdv.facture.id}/',
        )

    return redirect(next_url)


@login_required
def repondre_contre_proposition_rdv(request):
    """Le locataire répond à un créneau alternatif proposé par
    l'entreprise : il l'accepte, ou décline la demande."""
    from facturation.models import RendezVousPaiement
    from django.contrib import messages
    from django.shortcuts import redirect

    next_url = request.POST.get('next') or '/dashboard/facturation/'

    if request.method != 'POST':
        return redirect(next_url)

    rdv = RendezVousPaiement.objects.select_related('facture__contrat__bien', 'facture__contrat__proprietaire').filter(
        id=request.POST.get('rdv_id'), locataire=request.user, statut=RendezVousPaiement.Statut.CONTRE_PROPOSITION
    ).first()
    if not rdv:
        return redirect(next_url)

    from dashboard.services import NotificationService
    action = request.POST.get('action')

    if action == 'accepter':
        rdv.date_confirmee = rdv.date_proposee
        rdv.statut = RendezVousPaiement.Statut.CONFIRME
        rdv.save()
        messages.success(request, "Rendez-vous confirmé.")
        NotificationService.send(
            destinataire=rdv.facture.contrat.proprietaire, expediteur=request.user,
            type_notification='paiement',
            titre="Rendez-vous de paiement confirmé",
            message=f"Le locataire a accepté le créneau du {rdv.date_confirmee.strftime('%d/%m/%Y à %H:%M')} pour la facture {rdv.facture.numero_facture}.",
            lien=f'/dashboard/facturation/{rdv.facture.id}/',
        )
    elif action == 'refuser':
        rdv.statut = RendezVousPaiement.Statut.REFUSE
        rdv.save()
        messages.success(request, "Rendez-vous refusé.")
        NotificationService.send(
            destinataire=rdv.facture.contrat.proprietaire, expediteur=request.user,
            type_notification='paiement',
            titre="Créneau refusé",
            message=f"Le locataire n'a pas accepté le créneau proposé pour la facture {rdv.facture.numero_facture}.",
            lien=f'/dashboard/facturation/{rdv.facture.id}/',
        )

    return redirect(next_url)


@login_required
def confirmer_paiement_espece(request):
    """Le jour du rendez-vous, le propriétaire confirme depuis son tableau
    de bord que les espèces ont bien été reçues — réutilise le même
    mécanisme de confirmation que les autres moyens de paiement."""
    from facturation.models import RendezVousPaiement
    from django.contrib import messages
    from django.shortcuts import redirect

    next_url = request.POST.get('next') or '/dashboard/facturation/'

    if request.method != 'POST':
        return redirect(next_url)

    rdv = RendezVousPaiement.objects.select_related('facture__contrat__bien', 'locataire').filter(
        id=request.POST.get('rdv_id'), facture__contrat__proprietaire__in=request.user.comptes_entreprise(), statut=RendezVousPaiement.Statut.CONFIRME
    ).first()
    if not rdv:
        return redirect(next_url)

    if rdv.date_confirmee and timezone.localtime(rdv.date_confirmee).date() > timezone.now().date():
        messages.error(
            request,
            f"Le rendez-vous est prévu le {timezone.localtime(rdv.date_confirmee).strftime('%d/%m/%Y')} — "
            f"vous ne pouvez confirmer la réception des espèces qu'à partir de cette date.",
        )
        return redirect(next_url)

    if _marquer_facture_payee(rdv.facture, request.user, 'Espèces', 'especes', reference=f"RDV-{rdv.id}"):
        rdv.statut = RendezVousPaiement.Statut.HONORE
        rdv.save()
        messages.success(request, "Paiement en espèces confirmé. La quittance est disponible.")

    return redirect(next_url)


@login_required
def confirmer_reception_paiement(request):
    """Le propriétaire confirme (ou signale un problème sur) un paiement
    déclaré par le locataire — bascule EN_VALIDATION -> PAYEE, ou retour à
    GENEREE avec un motif si le paiement n'a en réalité pas été reçu."""
    from facturation.models import Facture
    from django.contrib import messages
    from django.shortcuts import redirect

    next_url = request.POST.get('next') or '/dashboard/facturation/'

    if request.method != 'POST':
        return redirect(next_url)

    facture = Facture.objects.select_related('contrat__bien', 'contrat__locataire', 'paiement').filter(
        id=request.POST.get('facture_id'), contrat__proprietaire__in=request.user.comptes_entreprise()
    ).first()
    if not facture or facture.statut != Facture.Statut.EN_VALIDATION:
        return redirect(next_url)

    action = request.POST.get('action')
    from dashboard.services import NotificationService

    if action == 'confirmer':
        moyen_label = dict(Facture.ModePaiement.choices).get(facture.mode_paiement, facture.mode_paiement or 'paiement déclaré')
        if _marquer_facture_payee(facture, request.user, moyen_label, facture.mode_paiement, facture.reference_transaction):
            messages.success(request, "Réception du paiement confirmée. La quittance est disponible.")
        if facture.contrat.locataire:
            NotificationService.send(
                destinataire=facture.contrat.locataire, expediteur=request.user,
                type_notification='paiement',
                titre="Paiement confirmé",
                message=f"{request.user.get_full_name() or request.user.username} a confirmé la réception de votre paiement ({facture.numero_facture}). Votre quittance est disponible.",
                lien=f'/dashboard/facturation/{facture.id}/',
            )
    elif action == 'rejeter':
        motif = request.POST.get('motif', '').strip()
        facture.statut = Facture.Statut.GENEREE
        facture.motif_rejet_paiement = motif
        facture.mode_paiement = None
        facture.reference_transaction = ''
        facture.save()
        messages.success(request, "Le locataire a été informé du problème.")
        if facture.contrat.locataire:
            NotificationService.send(
                destinataire=facture.contrat.locataire, expediteur=request.user,
                type_notification='paiement',
                titre="Problème avec votre paiement déclaré",
                message=f"{request.user.get_full_name() or request.user.username} signale un problème sur le paiement de {facture.numero_facture}"
                        + (f" : {motif}" if motif else ".") + " Merci de le régler à nouveau.",
                lien=f'/dashboard/facturation/{facture.id}/',
            )

    return redirect(next_url)


@login_required
@acces_requis('acces_comptable')
def centre_validation_paiements(request):
    """Centre de validation des paiements côté propriétaire/gestionnaire :
    liste groupée des factures dont le paiement a été déclaré par le
    locataire et attend confirmation, plus un historique des paiements
    récemment confirmés ou rejetés pour référence."""
    from django.shortcuts import redirect
    from facturation.models import Facture

    user = request.user
    if user.role == Utilisateur.Role.LOCATAIRE:
        return redirect('mon_espace_locataire')
    ctx = _sidebar_context(user)

    factures_qs = Facture.objects.filter(contrat__proprietaire__in=user.comptes_entreprise()).select_related(
        'contrat__bien', 'contrat__locataire', 'paiement'
    )

    a_valider = list(factures_qs.filter(statut=Facture.Statut.EN_VALIDATION).order_by('date_declaration_paiement'))
    confirmes_recemment = list(
        factures_qs.filter(statut=Facture.Statut.PAYEE).order_by('-date_paiement')[:10]
    )
    rejetes_recemment = list(
        factures_qs.exclude(motif_rejet_paiement='').order_by('-date_modification')[:5]
    )

    ctx.update({
        'active_page': 'validation_paiements',
        'a_valider': a_valider,
        'confirmes_recemment': confirmes_recemment,
        'rejetes_recemment': rejetes_recemment,
        'nb_a_valider': len(a_valider),
    })
    return render(request, 'dashboard/centre_validation_paiements.html', ctx)


@login_required
def stripe_creer_session(request):
    """Crée une session Stripe Checkout pour payer une facture par carte
    bancaire, et redirige le locataire vers la page de paiement hébergée par
    Stripe. XOF est une devise « zéro décimale » chez Stripe — le montant est
    transmis tel quel, sans le multiplier par 100 (contrairement à EUR/USD)."""
    from facturation.models import Facture
    from django.contrib import messages
    from django.shortcuts import redirect
    from django.conf import settings
    import stripe

    next_url = request.POST.get('next') or '/dashboard/facturation/'

    if request.method != 'POST':
        return redirect(next_url)

    facture = Facture.objects.select_related('contrat__bien', 'paiement').filter(
        id=request.POST.get('facture_id'), contrat__locataire=request.user
    ).first()
    if not facture or facture.statut in (Facture.Statut.PAYEE, Facture.Statut.ANNULEE):
        return redirect(next_url)

    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, "Le paiement par carte n'est pas configuré pour le moment.")
        return redirect(next_url)

    stripe.api_key = settings.STRIPE_SECRET_KEY
    success_url = request.build_absolute_uri(
        f'/dashboard/facturation/stripe/succes/?facture_id={facture.id}&session_id={{CHECKOUT_SESSION_ID}}'
    )
    cancel_url = request.build_absolute_uri(next_url)

    try:
        session = stripe.checkout.Session.create(
            mode='payment',
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'xof',
                    'product_data': {'name': f"Facture {facture.numero_facture} — {facture.contrat.bien.titre}"},
                    'unit_amount': int(facture.montant_total),
                },
                'quantity': 1,
            }],
            customer_email=request.user.email or None,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={'facture_id': str(facture.id)},
        )
    except Exception as e:
        messages.error(request, f"Impossible de créer la session de paiement : {e}")
        return redirect(next_url)

    return redirect(session.url)


@login_required
def stripe_paiement_reussi(request):
    """Retour de Stripe Checkout après un paiement carte réussi. Revérifie
    l'état du paiement directement auprès de Stripe (jamais confiance dans les
    seuls paramètres d'URL) avant de marquer la facture payée."""
    from facturation.models import Facture
    from django.contrib import messages
    from django.conf import settings
    from django.shortcuts import redirect
    import stripe

    facture = Facture.objects.select_related('contrat__bien', 'contrat__proprietaire', 'paiement').filter(
        id=request.GET.get('facture_id'), contrat__locataire=request.user
    ).first()
    session_id = request.GET.get('session_id')

    if facture and session_id and settings.STRIPE_SECRET_KEY:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except Exception:
            session = None
        session_facture_id = session.metadata['facture_id'] if session and 'facture_id' in session.metadata else None
        if session and session.payment_status == 'paid' and session_facture_id == str(facture.id):
            if _marquer_facture_payee(facture, request.user, 'Carte bancaire', 'carte', session.payment_intent):
                messages.success(request, "Paiement par carte confirmé. La facture est marquée payée.")
            else:
                messages.info(request, "Cette facture était déjà marquée payée.")
        else:
            messages.error(request, "Le paiement n'a pas pu être confirmé auprès de Stripe.")

    return redirect('/dashboard/facturation/')


def _build_facture_pdf(facture, buffer):
    """Écrit le PDF d'une facture/quittance dans `buffer` (fichier-like).

    Inclut, quand les données sont disponibles :
    - le numéro et le QR code de certification FNE (Facture Normalisée
      Électronique, DGI Côte d'Ivoire) si la facture a été certifiée ;
    - les mentions NCC/RCCM en pied de page, obligatoires sous OHADA/SYSCOHADA
      pour tout document commercial, indépendamment de la certification FNE.
    """
    from facturation.models import Facture
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Titre', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#185FA5'))
    sub_style = ParagraphStyle('Sous', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#6b7280'), spaceAfter=16)
    footer_style = ParagraphStyle('Pied', parent=styles['Normal'], fontSize=8.5, textColor=colors.HexColor('#9aa0a6'), alignment=TA_CENTER)
    fne_style = ParagraphStyle('Fne', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#155A38'), alignment=TA_CENTER)

    bien = facture.contrat.bien
    entreprise = getattr(facture.contrat.proprietaire, 'company', None)
    elements = [
        Paragraph(f"Facture {facture.numero_facture}", title_style),
        Paragraph(f"{bien.titre} — {facture.contrat.locataire.get_full_name() if facture.contrat.locataire else '—'}", sub_style),
    ]

    data = [
        ['Description', 'Montant'],
        ['Loyer', f"{facture.montant_loyer:,.0f} FCFA".replace(',', ' ')],
    ]
    if facture.montant_charges:
        data.append(['Charges', f"{facture.montant_charges:,.0f} FCFA".replace(',', ' ')])
    if facture.montant_autres:
        data.append(['Autres frais', f"{facture.montant_autres:,.0f} FCFA".replace(',', ' ')])
    if facture.montant_taxe:
        data.append(['Taxe', f"{facture.montant_taxe:,.0f} FCFA".replace(',', ' ')])
    data.append(['Total', f"{facture.montant_total:,.0f} FCFA".replace(',', ' ')])

    table = Table(data, colWidths=[110*mm, 50*mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#185FA5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#185FA5')),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 10*mm))

    statut_label = dict(Facture.Statut.choices).get(facture.statut, facture.statut)
    elements.append(Paragraph(f"Échéance : {facture.date_echéance.strftime('%d/%m/%Y')}", styles['Normal']))
    if facture.date_paiement:
        elements.append(Paragraph(f"Payée le : {facture.date_paiement.strftime('%d/%m/%Y')}", styles['Normal']))
    if facture.mode_paiement:
        mode_label = dict(Facture.ModePaiement.choices).get(facture.mode_paiement, facture.mode_paiement)
        ref = f" — réf. {facture.reference_transaction}" if facture.reference_transaction else ""
        elements.append(Paragraph(f"Mode de paiement : {mode_label}{ref}", styles['Normal']))
    elements.append(Paragraph(f"Statut : {statut_label}", styles['Normal']))

    # Certification FNE — numéro + QR code (uniquement si réellement certifiée,
    # jamais de numéro/QR fabriqué pour une facture non certifiée par la DGI).
    if facture.fne_certifiee and facture.fne_reference:
        elements.append(Spacer(1, 10*mm))
        elements.append(Paragraph(f"Facture Normalisée Électronique n° {facture.fne_reference}", fne_style))
        if facture.fne_token:
            try:
                import qrcode
                from io import BytesIO
                qr_buf = BytesIO()
                qrcode.make(facture.fne_token).save(qr_buf, format='PNG')
                qr_buf.seek(0)
                qr_img = Image(qr_buf, width=28*mm, height=28*mm)
                qr_img.hAlign = 'CENTER'
                elements.append(qr_img)
            except Exception:
                pass

    # Mentions légales OHADA/SYSCOHADA (pied de page) : NCC et RCCM de
    # l'entreprise, affichées dès qu'elles sont renseignées — indépendamment
    # de la certification FNE, qui est une exigence distincte.
    if entreprise and (entreprise.numero_ncc or entreprise.numero_rccm):
        mentions = []
        if entreprise.numero_ncc:
            mentions.append(f"NCC {entreprise.numero_ncc}")
        if entreprise.numero_rccm:
            mentions.append(f"RCCM {entreprise.numero_rccm}")
        elements.append(Spacer(1, 8*mm))
        elements.append(Paragraph(" — ".join(mentions), footer_style))

    doc.build(elements)


@login_required
def facture_detail(request, facture_id):
    """Fiche détaillée d'une facture : montants, statut, contrat, actions
    (payer/signaler une difficulté côté locataire, marquer payée côté propriétaire)."""
    from facturation.models import Facture
    from django.http import Http404, HttpResponseForbidden
    from django.shortcuts import redirect
    from django.contrib import messages

    facture = Facture.objects.select_related(
        'contrat__bien', 'contrat__locataire', 'contrat__proprietaire', 'paiement'
    ).filter(id=facture_id).first()
    if not facture:
        raise Http404('Facture non trouvée')

    user = request.user
    if user.id != facture.contrat.locataire_id and not user.meme_entreprise(facture.contrat.proprietaire) and not user.is_staff:
        return HttpResponseForbidden('Accès refusé')

    est_locataire = user.id == facture.contrat.locataire_id
    est_proprietaire = user.meme_entreprise(facture.contrat.proprietaire) or user.is_staff

    if request.method == 'POST' and est_proprietaire and request.POST.get('action') == 'marquer_payee':
        if facture.statut != Facture.Statut.PAYEE:
            today = timezone.now().date()
            facture.statut = Facture.Statut.PAYEE
            facture.date_paiement = today
            facture.save()
            p = facture.paiement
            p.statut = Paiement.Statut.RECU
            p.date_paiement = today
            p.montant_recu = p.montant_du
            p.save()
            messages.success(request, "Facture marquée comme payée.")
        return redirect('facture_detail', facture_id=facture.id)

    today = timezone.now().date()
    est_retard = facture.date_echéance < today and facture.statut not in (Facture.Statut.PAYEE, Facture.Statut.EN_VALIDATION, Facture.Statut.ANNULEE)

    jours_retard_paiement = None
    if facture.statut == Facture.Statut.PAYEE and facture.date_paiement and facture.date_paiement > facture.date_echéance:
        jours_retard_paiement = (facture.date_paiement - facture.date_echéance).days

    rdv_paiement = facture.rendez_vous_paiement.order_by('-date_creation').first()

    paiement = facture.paiement
    jours_retard = (today - paiement.date_limite).days if est_retard and paiement.date_limite else 0
    mise_en_demeure = paiement.mises_en_demeure.order_by('-date_creation').first()
    mise_en_demeure_recommandee = (
        est_retard and jours_retard >= facture.contrat.jours_avant_mise_en_demeure and not mise_en_demeure
    )

    from contrats.escalade import echelle_recouvrement
    etape_recouvrement = echelle_recouvrement(paiement) if est_proprietaire else None

    rdv_jour_arrive = bool(
        rdv_paiement and rdv_paiement.date_confirmee and timezone.localtime(rdv_paiement.date_confirmee).date() <= today
    )

    return render(request, 'dashboard/facture_detail.html', {
        'facture': facture,
        'contrat': facture.contrat,
        'est_locataire': est_locataire,
        'est_proprietaire': est_proprietaire,
        'est_retard': est_retard,
        'jours_retard_paiement': jours_retard_paiement,
        'moyens_paiement': MOYENS_PAIEMENT,
        'rdv_paiement': rdv_paiement,
        'paiement': paiement,
        'jours_retard': jours_retard,
        'mise_en_demeure': mise_en_demeure,
        'mise_en_demeure_recommandee': mise_en_demeure_recommandee,
        'etape_recouvrement': etape_recouvrement,
        'rdv_jour_arrive': rdv_jour_arrive,
    })


@login_required
def facture_archiver(request, facture_id):
    """Le propriétaire archive (ou désarchive) une facture déjà close
    (payée ou annulée) pour alléger sa liste sans toucher aux données —
    interdit sur une facture encore en attente de paiement."""
    from facturation.models import Facture
    from django.http import Http404
    from django.shortcuts import redirect
    from django.contrib import messages

    facture = Facture.objects.filter(id=facture_id, contrat__proprietaire__in=request.user.comptes_entreprise()).first()
    if not facture:
        raise Http404('Facture non trouvée')
    if facture.statut not in (Facture.Statut.PAYEE, Facture.Statut.ANNULEE):
        return redirect('facture_detail', facture_id=facture.id)

    if request.method == 'POST':
        facture.est_archive = not facture.est_archive
        facture.save(update_fields=['est_archive'])
        messages.success(request, "Facture archivée." if facture.est_archive else "Facture désarchivée.")

    return redirect('facture_detail', facture_id=facture.id)


@login_required
def facture_pdf(request, facture_id):
    """Génère (ou sert) la facture/quittance en PDF."""
    from facturation.models import Facture
    from django.http import HttpResponse, Http404
    from django.shortcuts import redirect

    facture = Facture.objects.select_related(
        'contrat__bien', 'contrat__locataire', 'contrat__proprietaire', 'paiement'
    ).filter(id=facture_id).first()
    if not facture:
        raise Http404('Facture non trouvée')

    user = request.user
    if user.id != facture.contrat.locataire_id and not user.meme_entreprise(facture.contrat.proprietaire) and not user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('Accès refusé')

    if facture.fichier_pdf:
        return redirect(facture.fichier_pdf.url)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{facture.numero_facture}.pdf"'
    _build_facture_pdf(facture, response)
    return response


@login_required
def factures_zip(request):
    """Télécharge un zip contenant les PDF de toutes les factures du locataire
    (ou seulement les payées si ?filtre=payees)."""
    from facturation.models import Facture
    from django.http import HttpResponse
    from django.shortcuts import redirect
    import io
    import zipfile

    if request.user.role != Utilisateur.Role.LOCATAIRE:
        return redirect('dashboard_facturation')

    factures = Facture.objects.filter(contrat__locataire=request.user).select_related(
        'contrat__bien', 'contrat__locataire', 'paiement'
    )
    filtre = request.GET.get('filtre')
    if filtre == 'payees':
        factures = factures.filter(statut=Facture.Statut.PAYEE)
        zip_name = 'quittances.zip'
    else:
        zip_name = 'factures.zip'

    if not factures.exists():
        return redirect('dashboard_facturation')

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for facture in factures:
            pdf_buffer = io.BytesIO()
            _build_facture_pdf(facture, pdf_buffer)
            zf.writestr(f"{facture.numero_facture}.pdf", pdf_buffer.getvalue())

    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{zip_name}"'
    return response


TYPES_DEMANDE_PAIEMENT = {
    'je_ne_peux_pas_payer': "ne peut pas payer à temps",
    'report_echeance': "demande un report d'échéance",
    'paiement_echelonne': "souhaite payer en plusieurs fois",
    'autre': "signale un problème concernant ce paiement",
}


@login_required
def signaler_probleme_paiement(request):
    """Le locataire explique une difficulté de paiement au propriétaire
    (report, paiement échelonné…) via un message dans leur conversation."""
    from facturation.models import Facture
    from django.contrib import messages
    from django.shortcuts import redirect
    from messagerie.models import Conversation, Message

    next_url = request.POST.get('next') or '/dashboard/facturation/'

    if request.method != 'POST':
        return redirect(next_url)

    facture = Facture.objects.select_related('contrat__bien', 'contrat__proprietaire').filter(
        id=request.POST.get('facture_id'), contrat__locataire=request.user
    ).first()
    if not facture:
        return redirect(next_url)

    type_demande = request.POST.get('type_demande', 'autre')
    texte = request.POST.get('message', '').strip()
    bien = facture.contrat.bien
    proprietaire = facture.contrat.proprietaire

    conv, _ = Conversation.objects.get_or_create(
        bien=bien, demandeur=request.user,
        defaults={'proprietaire': proprietaire}
    )
    action_label = TYPES_DEMANDE_PAIEMENT.get(type_demande, TYPES_DEMANDE_PAIEMENT['autre'])
    contenu = f"Concernant la facture {facture.numero_facture} : {request.user.get_full_name() or request.user.username} {action_label}."
    if texte:
        contenu += f"\n\n{texte}"
    Message.objects.create(conversation=conv, expediteur=request.user, contenu=contenu)
    conv.mis_a_jour_le = timezone.now()
    conv.save(update_fields=['mis_a_jour_le'])

    from dashboard.services import NotificationService
    NotificationService.send(
        destinataire=proprietaire, expediteur=request.user,
        type_notification='message',
        titre=f"Difficulté de paiement — {bien.titre}",
        message=contenu,
        lien=f'/chat/{conv.id}/',
    )
    messages.success(request, "Le propriétaire a été informé. Vous recevrez sa réponse dans vos messages.")

    return redirect(next_url)


@login_required
def contrats_dashboard_view(request):
    from django.db.models import Sum

    user = request.user
    today = timezone.now().date()

    # ── Locataire : ses propres contrats ──────────────────────────────────────
    if user.role == Utilisateur.Role.LOCATAIRE:
        contrats = (
            Contrat.objects
            .filter(locataire=user)
            .select_related('bien', 'proprietaire', 'proprietaire__company')
            .order_by('-date_creation')
        )
        retard_ids = set(Paiement.objects.filter(
            contrat__locataire=user,
            statut__in=[Paiement.Statut.RETARD_MINEUR, Paiement.Statut.RETARD_MAJEUR, Paiement.Statut.IMPAYE]
        ).values_list('contrat_id', flat=True))

        contrats_list = list(contrats)
        for c in contrats_list:
            c.en_retard = c.id in retard_ids

        en_cours = [c for c in contrats_list if c.statut == Contrat.Statut.EN_COURS]
        total_loyer = sum(c.prix_mensuel for c in en_cours)

        from facturation.models import Facture as Fac
        from .services import NotificationService
        nb_notifs = NotificationService.unread_count(user)
        nb_factures_retard = Fac.objects.filter(
            contrat__locataire=user,
            statut__in=[Fac.Statut.GENEREE, Fac.Statut.ENVOYEE],
            date_echéance__lt=today
        ).count()

        return render(request, 'dashboard/contrats_locataire.html', {
            'contrats': contrats_list,
            'nb_en_cours': len(en_cours),
            'total_loyer': total_loyer,
            'nb_termines': sum(1 for c in contrats_list if c.statut == Contrat.Statut.TERMINE),
            'today': today,
            'nb_notifs': nb_notifs,
            'nb_factures_retard': nb_factures_retard,
        })

    # ── Propriétaire / gestionnaire ───────────────────────────────────────────
    if not user.a_acces('acces_gestion_locative'):
        from django.contrib import messages
        from django.shortcuts import redirect
        messages.error(request, "Vous n'avez pas accès à cette page.")
        return redirect('dashboard_company')
    ctx = _sidebar_context(user)

    contrats = (
        Contrat.objects
        .filter(proprietaire__in=user.comptes_entreprise())
        .select_related('bien', 'locataire')
        .order_by('-date_creation')
    )

    en_cours = contrats.filter(statut=Contrat.Statut.EN_COURS)
    total_loyers = en_cours.aggregate(t=Sum('prix_mensuel'))['t'] or 0
    nb_termines = contrats.filter(statut=Contrat.Statut.TERMINE).count()
    nb_resilies = contrats.filter(statut=Contrat.Statut.RESILIE).count()

    retard_ids = set(Paiement.objects.filter(
        contrat__proprietaire__in=user.comptes_entreprise(),
        statut__in=[Paiement.Statut.RETARD_MINEUR, Paiement.Statut.RETARD_MAJEUR, Paiement.Statut.IMPAYE]
    ).values_list('contrat_id', flat=True))

    contrats_list = list(contrats)
    for c in contrats_list:
        c.en_retard = c.id in retard_ids

    ctx.update({
        'contrats': contrats_list,
        'nb_en_cours': en_cours.count(),
        'total_loyers': total_loyers,
        'nb_termines': nb_termines,
        'nb_resilies': nb_resilies,
        'today': today,
    })
    return render(request, 'dashboard/contrats.html', ctx)


@login_required
def export_contrats_csv(request):
    """Export CSV des contrats du propriétaire connecté."""
    import csv
    from django.http import HttpResponse
    from django.shortcuts import redirect

    user = request.user
    if user.role not in (Utilisateur.Role.PROPRIETAIRE, Utilisateur.Role.GESTIONNAIRE):
        return redirect('dashboard')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="contrats.csv"'
    response.write('﻿')  # BOM pour un affichage correct des accents dans Excel
    writer = csv.writer(response)
    writer.writerow(['Numéro', 'Bien', 'Locataire', 'Statut', 'Date début', 'Date fin', 'Loyer mensuel', 'Dépôt de garantie'])
    contrats = (
        Contrat.objects.filter(proprietaire__in=user.comptes_entreprise())
        .select_related('bien', 'locataire')
        .order_by('-date_creation')
    )
    for c in contrats:
        writer.writerow([
            c.numero_contrat,
            c.bien.titre,
            c.locataire.get_full_name() if c.locataire else '',
            c.get_statut_display(),
            c.date_debut, c.date_fin,
            c.prix_mensuel, c.prix_depot_garantie,
        ])
    return response


@login_required
def export_paiements_csv(request):
    """Export CSV des paiements liés aux contrats du propriétaire connecté."""
    import csv
    from django.http import HttpResponse
    from django.shortcuts import redirect

    user = request.user
    if user.role not in (Utilisateur.Role.PROPRIETAIRE, Utilisateur.Role.GESTIONNAIRE):
        return redirect('dashboard')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="paiements.csv"'
    response.write('﻿')
    writer = csv.writer(response)
    writer.writerow(['Contrat', 'Bien', 'Locataire', 'Mois', 'Montant dû', 'Montant reçu', 'Statut', 'Date limite', 'Date paiement'])
    paiements = (
        Paiement.objects.filter(contrat__proprietaire__in=user.comptes_entreprise())
        .select_related('contrat__bien', 'contrat__locataire')
        .order_by('-mois')
    )
    for p in paiements:
        writer.writerow([
            p.contrat.numero_contrat,
            p.contrat.bien.titre,
            p.contrat.locataire.get_full_name() if p.contrat.locataire else '',
            p.mois, p.montant_du, p.montant_recu,
            p.get_statut_display(),
            p.date_limite, p.date_paiement or '',
        ])
    return response


@login_required
def rapport_mensuel_pdf(request):
    """Génère le rapport mensuel du propriétaire connecté en PDF."""
    from django.http import HttpResponse
    from django.shortcuts import redirect
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    user = request.user
    if user.role not in (Utilisateur.Role.PROPRIETAIRE, Utilisateur.Role.GESTIONNAIRE):
        return redirect('dashboard')

    mois_str = request.GET.get('mois')
    if mois_str:
        mois = timezone.datetime.strptime(mois_str, '%Y-%m').date().replace(day=1)
    else:
        mois = timezone.now().date().replace(day=1)

    contrats_actifs = Contrat.objects.filter(
        proprietaire__in=user.comptes_entreprise(),
        statut=Contrat.Statut.EN_COURS,
        date_debut__lte=timezone.now().date(),
        date_fin__gte=timezone.now().date(),
    )
    nombre_proprietes = Bien.objects.filter(proprietaire__in=user.comptes_entreprise()).count()
    nombre_contrats_actifs = contrats_actifs.count()
    nombre_locataires = contrats_actifs.values('locataire').distinct().count()

    paiements = Paiement.objects.filter(contrat__proprietaire__in=user.comptes_entreprise(), mois=mois)
    revenu_attendu = paiements.aggregate(Sum('montant_du'))['montant_du__sum'] or 0
    revenu_recu = paiements.filter(statut=Paiement.Statut.RECU).aggregate(Sum('montant_recu'))['montant_recu__sum'] or 0
    montant_impaye = paiements.filter(
        statut__in=[Paiement.Statut.IMPAYE, Paiement.Statut.RETARD_MAJEUR]
    ).aggregate(Sum('montant_du'))['montant_du__sum'] or 0
    taux_collecte = (revenu_recu / revenu_attendu * 100) if revenu_attendu else 0

    response = HttpResponse(content_type='application/pdf')
    filename = f"rapport_{mois.strftime('%Y-%m')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    doc = SimpleDocTemplate(response, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitreRapport', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#166534'))
    sub_style = ParagraphStyle('SousTitre', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#6b7280'), spaceAfter=16)

    company_name = user.company.name if getattr(user, 'company', None) else user.get_full_name() or user.username
    elements = [
        Paragraph('Rapport mensuel', title_style),
        Paragraph(f"{company_name} — {mois.strftime('%B %Y')}", sub_style),
    ]

    kpi_data = [
        ['Indicateur', 'Valeur'],
        ['Propriétés', str(nombre_proprietes)],
        ['Contrats actifs', str(nombre_contrats_actifs)],
        ['Locataires', str(nombre_locataires)],
        ['Revenu attendu', f"{revenu_attendu:,.0f} FCFA".replace(',', ' ')],
        ['Revenu reçu', f"{revenu_recu:,.0f} FCFA".replace(',', ' ')],
        ['Montant impayé', f"{montant_impaye:,.0f} FCFA".replace(',', ' ')],
        ['Taux de collecte', f"{taux_collecte:.1f} %"],
    ]
    kpi_table = Table(kpi_data, colWidths=[90*mm, 60*mm])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#166534')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
    ]))
    elements.append(kpi_table)
    elements.append(Spacer(1, 20*mm))

    contrats_list = list(
        Contrat.objects.filter(proprietaire__in=user.comptes_entreprise(), statut=Contrat.Statut.EN_COURS)
        .select_related('bien', 'locataire')
    )
    if contrats_list:
        elements.append(Paragraph('Contrats en cours', styles['Heading2']))
        contrat_data = [['Bien', 'Locataire', 'Loyer mensuel']]
        for c in contrats_list:
            contrat_data.append([
                c.bien.titre[:40],
                c.locataire.get_full_name() if c.locataire else '—',
                f"{c.prix_mensuel:,.0f} FCFA".replace(',', ' '),
            ])
        contrat_table = Table(contrat_data, colWidths=[70*mm, 50*mm, 40*mm])
        contrat_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9.5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(contrat_table)

    doc.build(elements)
    return response
