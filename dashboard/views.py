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
        Contrat.objects.filter(proprietaire=user, statut=Contrat.Statut.EN_COURS)
        .select_related('locataire', 'bien')
    )
    clients_contrats = {c.locataire_id: c for c in contrats_actifs if c.locataire}

    contrats_termines = (
        Contrat.objects.filter(proprietaire=user, statut__in=[Contrat.Statut.TERMINE, Contrat.Statut.RESILIE])
        .select_related('locataire', 'bien').order_by('-date_fin')
    )
    clients_anciens = {
        c.locataire_id: c for c in contrats_termines
        if c.locataire and c.locataire_id not in clients_contrats
    }

    visites_confirmees = (
        Visite.objects.filter(bien__proprietaire=user, statut=Visite.Statut.CONFIRMEE)
        .select_related('locataire', 'bien')
    )
    clients_negociation = {
        v.locataire_id: v for v in visites_confirmees if v.locataire_id not in clients_contrats
    }

    visites_attente = (
        Visite.objects.filter(bien__proprietaire=user, statut=Visite.Statut.EN_ATTENTE)
        .select_related('locataire', 'bien').order_by('date_visite')
    )
    clients_visites = {
        v.locataire_id: v for v in visites_attente
        if v.locataire_id not in clients_contrats and v.locataire_id not in clients_negociation
    }

    convs = (
        Conversation.objects.filter(proprietaire=user)
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

    biens_qs = Bien.objects.filter(proprietaire=user)
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
        for conv in Conversation.objects.filter(proprietaire=user)
    )
    nb_rdv_en_attente = Visite.objects.filter(
        bien__proprietaire=user, statut=Visite.Statut.EN_ATTENTE
    ).count()
    nb_reclamations_ouvertes = Reclamation.objects.filter(
        bien__proprietaire=user, statut=Reclamation.Statut.OUVERTE
    ).count()
    nb_devis_en_attente = 0
    nb_notifs = NotificationService.unread_count(user)
    if 'construction' in types and company:
        nb_devis_en_attente = ProjetConstruction.objects.filter(
            entreprise=company, statut=ProjetConstruction.Statut.EN_ATTENTE
        ).count()
        nb_notifs += NotificationConstruction.objects.filter(
            destinataire=user, lue=False
        ).count()

    # ── Cartes statistiques ──
    nb_clients = (
        Contrat.objects.filter(proprietaire=user).exclude(locataire=None)
        .values('locataire').distinct().count()
    )
    nb_paiements = Paiement.objects.filter(contrat__proprietaire=user).count()
    nb_conversations = Conversation.objects.filter(proprietaire=user).count()
    nb_rdv_total = Visite.objects.filter(bien__proprietaire=user).exclude(
        statut__in=[Visite.Statut.ANNULEE, Visite.Statut.REFUSEE]
    ).count()

    # ── Aperçus (messages / rendez-vous / devis) — les pages dédiées ont le détail ──
    messages_recents = [
        {'conv': conv, 'dernier': conv.dernier_message(), 'nb_non_lus': conv.nb_non_lus_pour(user)}
        for conv in Conversation.objects.filter(proprietaire=user).select_related('demandeur', 'bien').order_by('-mis_a_jour_le')[:4]
    ]
    rdv_prochains = list(
        Visite.objects.filter(bien__proprietaire=user, date_visite__gte=timezone.now())
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
                (Contrat.objects.filter(proprietaire=user, statut=Contrat.Statut.EN_COURS).count(), 'contrats actifs'),
            ],
        })
    if 'vente' in types:
        modules_data.append({
            'key': 'vente', 'label': 'Vente',
            'metrics': [
                (biens_qs.filter(transaction_type__in=['vente', 'both']).exclude(type_bien='terrain').count(), 'biens en vente'),
                (Visite.objects.filter(bien__proprietaire=user, bien__transaction_type__in=['vente', 'both']).count(), 'visites programmées'),
            ],
        })
    if 'terrain' in types:
        modules_data.append({
            'key': 'terrain', 'label': 'Terrains',
            'metrics': [
                (biens_qs.filter(type_bien='terrain').count(), 'parcelles'),
                (Visite.objects.filter(bien__proprietaire=user, bien__type_bien='terrain').count(), 'visites'),
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
    for c in Contrat.objects.filter(proprietaire=user).select_related('bien').order_by('-date_creation')[:5]:
        activites.append({'type': 'contrat', 'titre': f"Contrat {c.get_statut_display().lower()} — {c.bien.titre}", 'date': c.date_creation})
    for p in Paiement.objects.filter(contrat__proprietaire=user, statut=Paiement.Statut.RECU, date_paiement__isnull=False).select_related('contrat__bien').order_by('-date_paiement')[:5]:
        activites.append({
            'type': 'paiement', 'titre': f"Paiement reçu — {p.contrat.bien.titre}",
            'date': timezone.make_aware(timezone.datetime.combine(p.date_paiement, timezone.datetime.min.time())),
        })
    for m in Message.objects.filter(conversation__proprietaire=user).exclude(expediteur=user).select_related('expediteur').order_by('-cree_le')[:5]:
        activites.append({'type': 'message', 'titre': f"Message reçu de {m.expediteur.get_full_name() or m.expediteur.username}", 'date': m.cree_le})
    for v in Visite.objects.filter(bien__proprietaire=user).select_related('bien').order_by('-date_reservation')[:5]:
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
            if Contrat.objects.filter(proprietaire=user).exists():
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
    biens_count = Bien.objects.filter(proprietaire=user).count()

    try:
        prof = user.proprietaire_profile
        documents_verifies = bool(prof.certification)
    except Exception:
        documents_verifies = False

    nb_messages_non_lus = sum(
        conv.messages.filter(lu=False).exclude(expediteur=user).count()
        for conv in Conversation.objects.filter(proprietaire=user)
    )
    nb_rdv_en_attente = Visite.objects.filter(
        bien__proprietaire=user, statut=Visite.Statut.EN_ATTENTE
    ).count()
    nb_reservations_en_attente = Reservation.objects.filter(
        bien__proprietaire=user, statut=Reservation.Statut.EN_ATTENTE
    ).count()
    nb_reclamations_ouvertes = Reclamation.objects.filter(
        bien__proprietaire=user, statut=Reclamation.Statut.OUVERTE
    ).count()
    nb_devis_en_attente = 0
    nb_notifs = NotificationService.unread_count(user)
    if 'construction' in types and company:
        nb_devis_en_attente = ProjetConstruction.objects.filter(
            entreprise=company, statut=ProjetConstruction.Statut.EN_ATTENTE
        ).count()
        nb_notifs += NotificationConstruction.objects.filter(
            destinataire=user, lue=False
        ).count()

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
    }


@login_required
def mes_biens(request):
    """Liste des biens du propriétaire connecté (distincte de /biens/, qui est
    la vitrine publique de tous les biens disponibles sur la plateforme)."""
    from django.shortcuts import redirect

    user = request.user
    if user.role == Utilisateur.Role.LOCATAIRE:
        return redirect('mon_espace_locataire')
    ctx = _sidebar_context(user)

    mes_biens_qs = (
        Bien.objects.filter(proprietaire=user)
        .order_by('-date_creation')
    )

    ctx.update({'active_page': 'biens', 'mes_biens': mes_biens_qs})
    return render(request, 'dashboard/mes_biens.html', ctx)


@login_required
def rdv_view(request):
    from biens.models import Visite
    from construction.models import ProjetConstruction
    from django.utils import timezone
    from django.shortcuts import redirect

    user = request.user
    if user.role == Utilisateur.Role.LOCATAIRE:
        return redirect('mon_espace_locataire')
    ctx = _sidebar_context(user)

    visites = (
        Visite.objects
        .filter(bien__proprietaire=user)
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

    ctx.update({
        'visites': visites,
        'rdv_construction': rdv_construction,
        'today': timezone.now(),
    })
    return render(request, 'dashboard/rdv.html', ctx)


@login_required
def notifications_view(request):
    from construction.models import NotificationConstruction
    from .models import Notification
    from django.shortcuts import redirect

    user = request.user
    if user.role == Utilisateur.Role.LOCATAIRE:
        return redirect('mon_espace_locataire')
    ctx = _sidebar_context(user)

    notifs = []

    # Notifications unifiées (message, visite, devis, réclamation...) —
    # créées via NotificationService.send() au moment de l'action.
    ICON_MAP = {'message': 'message', 'visite': 'rdv'}
    for n in Notification.objects.filter(destinataire=user).select_related('expediteur').order_by('-date_creation')[:30]:
        notifs.append({
            'type': ICON_MAP.get(n.type_notification, 'autre'),
            'titre': n.titre,
            'detail': n.message[:80],
            'lien': n.lien or '#',
            'mark_url': f'/dashboard/notifications/lire/{n.id}/?next={n.lien}' if n.lien else None,
            'date': n.date_creation,
            'lue': n.lue,
        })

    # Notifications construction (système séparé, déjà branché sur son propre dashboard)
    for n in NotificationConstruction.objects.filter(destinataire=user).select_related('projet').order_by('-cree_le')[:20]:
        notifs.append({
            'type': 'construction',
            'titre': n.get_type_display(),
            'detail': n.message[:80],
            'lien': f'/construction/projet/{n.projet_id}/',
            'mark_url': None,
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
def notifications_marquer_toutes_lues(request):
    from django.shortcuts import redirect
    from .services import NotificationService

    if request.method == 'POST':
        NotificationService.mark_all_read(request.user)
    return redirect('/dashboard/notifications/')


@login_required
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
        .filter(proprietaire=user, statut=Contrat.Statut.EN_COURS)
        .select_related('locataire', 'bien')
    )
    clients_contrats = {c.locataire_id: c for c in contrats_actifs if c.locataire}

    # Contrats terminés → anciens clients
    contrats_termines = (
        Contrat.objects
        .filter(proprietaire=user, statut__in=[Contrat.Statut.TERMINE, Contrat.Statut.RESILIE])
        .select_related('locataire', 'bien')
        .order_by('-date_fin')
    )
    clients_anciens = {c.locataire_id: c for c in contrats_termines if c.locataire and c.locataire_id not in clients_contrats}

    # Visites confirmées sans contrat → négociation
    visites_confirmees = (
        Visite.objects
        .filter(bien__proprietaire=user, statut=Visite.Statut.CONFIRMEE)
        .select_related('locataire', 'bien')
    )
    clients_negociation = {
        v.locataire_id: v for v in visites_confirmees
        if v.locataire_id not in clients_contrats
    }

    # Visites en attente → visites programmées
    visites_attente = (
        Visite.objects
        .filter(bien__proprietaire=user, statut=Visite.Statut.EN_ATTENTE)
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
        .filter(proprietaire=user)
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

    ctx.update({
        'clients_contrats': list(clients_contrats.values()),
        'clients_negociation': list(clients_negociation.values()),
        'clients_visites': list(clients_visites.values()),
        'clients_prospects': list(clients_prospects.values()),
        'clients_anciens': list(clients_anciens.values()),
        'nb_prospects': len(clients_prospects),
        'nb_visites': len(clients_visites),
        'nb_negociation': len(clients_negociation),
        'nb_contrats': len(clients_contrats),
        'nb_anciens': len(clients_anciens),
    })
    return render(request, 'dashboard/clients.html', ctx)


@login_required
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
            rec = Reclamation.objects.filter(id=rec_id, bien__proprietaire=user).first()
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
        .filter(bien__proprietaire=user)
        .select_related('bien', 'locataire')
        .order_by('-cree_le')
    )
    ctx['reclamations'] = reclamations
    return render(request, 'dashboard/reclamations.html', ctx)


@login_required
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
        Conversation.objects.filter(proprietaire=user, demandeur=client)
        .select_related('bien').order_by('-mis_a_jour_le')
    )
    visites = (
        Visite.objects.filter(bien__proprietaire=user, locataire=client)
        .select_related('bien').order_by('-date_visite')
    )
    contrats = (
        Contrat.objects.filter(proprietaire=user, locataire=client)
        .select_related('bien').order_by('-date_creation')
    )
    paiements = (
        Paiement.objects.filter(contrat__proprietaire=user, contrat__locataire=client)
        .select_related('contrat__bien').order_by('-mois')
    )
    reclamations = (
        Reclamation.objects.filter(bien__proprietaire=user, locataire=client)
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
            f.est_retard = f.date_echéance < today and f.statut not in (Facture.Statut.PAYEE, Facture.Statut.ANNULEE)

        from facturation.models import Notification as Notif
        nb_notifs = Notif.objects.filter(
            utilisateur=user,
            statut__in=[Notif.Statut.EN_ATTENTE, Notif.Statut.ENVOYEE]
        ).count()
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
        })

    # ── Propriétaire / gestionnaire : toutes les factures de ses contrats ─────
    ctx = _sidebar_context(user)

    if request.method == 'POST':
        action = request.POST.get('action')
        facture_id = request.POST.get('facture_id')
        if facture_id and action == 'marquer_payee':
            facture = (
                Facture.objects
                .filter(id=facture_id, contrat__proprietaire=user)
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
        .filter(contrat__proprietaire=user)
        .select_related('contrat__bien', 'contrat__locataire', 'paiement')
        .order_by('-date_generation')
    )

    total_encaisse = factures.filter(statut=Facture.Statut.PAYEE).aggregate(t=Sum('montant_total'))['t'] or 0
    total_en_attente = factures.filter(statut__in=[Facture.Statut.GENEREE, Facture.Statut.ENVOYEE]).aggregate(t=Sum('montant_total'))['t'] or 0
    total_retard = factures.filter(
        statut__in=[Facture.Statut.GENEREE, Facture.Statut.ENVOYEE],
        date_echéance__lt=today
    ).aggregate(t=Sum('montant_total'))['t'] or 0
    nb_rappels = RappelPaiement.objects.filter(
        paiement__contrat__proprietaire=user,
        est_envoye=False,
        date_programmee__lte=timezone.now()
    ).count()

    factures_list = list(factures)
    for f in factures_list:
        f.est_retard = f.date_echéance < today and f.statut not in (Facture.Statut.PAYEE, Facture.Statut.ANNULEE)

    ctx.update({
        'factures': factures_list,
        'total_encaisse': total_encaisse,
        'total_en_attente': total_en_attente,
        'total_retard': total_retard,
        'nb_rappels': nb_rappels,
        'today': today,
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


@login_required
def signaler_paiement(request):
    """Le locataire règle une facture par Wave/Orange Money/MTN MoMo. Faute de
    passerelle réelle branchée pour ces opérateurs, la confirmation du moyen
    choisi vaut paiement — la facture est marquée payée immédiatement et le
    propriétaire est notifié. Le paiement par carte passe par Stripe (voir
    `stripe_creer_session`), pas par cette vue."""
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

    if _marquer_facture_payee(facture, request.user, moyen, mode_key):
        messages.success(request, "Votre paiement a été enregistré. La facture est marquée payée.")

    return redirect(next_url)


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
    """Écrit le PDF d'une facture/quittance dans `buffer` (fichier-like)."""
    from facturation.models import Facture
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Titre', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#185FA5'))
    sub_style = ParagraphStyle('Sous', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#6b7280'), spaceAfter=16)

    bien = facture.contrat.bien
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
    if user.id not in (facture.contrat.locataire_id, facture.contrat.proprietaire_id) and not user.is_staff:
        return HttpResponseForbidden('Accès refusé')

    est_locataire = user.id == facture.contrat.locataire_id
    est_proprietaire = user.id == facture.contrat.proprietaire_id or user.is_staff

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
    est_retard = facture.date_echéance < today and facture.statut not in (Facture.Statut.PAYEE, Facture.Statut.ANNULEE)

    jours_retard_paiement = None
    if facture.statut == Facture.Statut.PAYEE and facture.date_paiement and facture.date_paiement > facture.date_echéance:
        jours_retard_paiement = (facture.date_paiement - facture.date_echéance).days

    return render(request, 'dashboard/facture_detail.html', {
        'facture': facture,
        'contrat': facture.contrat,
        'est_locataire': est_locataire,
        'est_proprietaire': est_proprietaire,
        'est_retard': est_retard,
        'jours_retard_paiement': jours_retard_paiement,
        'moyens_paiement': MOYENS_PAIEMENT,
    })


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
    if user.id not in (facture.contrat.locataire_id, facture.contrat.proprietaire_id) and not user.is_staff:
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

        from facturation.models import Facture as Fac, Notification as Notif
        nb_notifs = Notif.objects.filter(
            utilisateur=user,
            statut__in=[Notif.Statut.EN_ATTENTE, Notif.Statut.ENVOYEE]
        ).count()
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
    ctx = _sidebar_context(user)

    contrats = (
        Contrat.objects
        .filter(proprietaire=user)
        .select_related('bien', 'locataire')
        .order_by('-date_creation')
    )

    en_cours = contrats.filter(statut=Contrat.Statut.EN_COURS)
    total_loyers = en_cours.aggregate(t=Sum('prix_mensuel'))['t'] or 0
    nb_termines = contrats.filter(statut=Contrat.Statut.TERMINE).count()
    nb_resilies = contrats.filter(statut=Contrat.Statut.RESILIE).count()

    retard_ids = set(Paiement.objects.filter(
        contrat__proprietaire=user,
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

    user = request.user
    if user.role not in (Utilisateur.Role.PROPRIETAIRE, Utilisateur.Role.GESTIONNAIRE):
        return redirect('dashboard')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="contrats.csv"'
    response.write('﻿')  # BOM pour un affichage correct des accents dans Excel
    writer = csv.writer(response)
    writer.writerow(['Numéro', 'Bien', 'Locataire', 'Statut', 'Date début', 'Date fin', 'Loyer mensuel', 'Dépôt de garantie'])
    contrats = (
        Contrat.objects.filter(proprietaire=user)
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

    user = request.user
    if user.role not in (Utilisateur.Role.PROPRIETAIRE, Utilisateur.Role.GESTIONNAIRE):
        return redirect('dashboard')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="paiements.csv"'
    response.write('﻿')
    writer = csv.writer(response)
    writer.writerow(['Contrat', 'Bien', 'Locataire', 'Mois', 'Montant dû', 'Montant reçu', 'Statut', 'Date limite', 'Date paiement'])
    paiements = (
        Paiement.objects.filter(contrat__proprietaire=user)
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
        proprietaire=user,
        statut=Contrat.Statut.EN_COURS,
        date_debut__lte=timezone.now().date(),
        date_fin__gte=timezone.now().date(),
    )
    nombre_proprietes = Bien.objects.filter(proprietaire=user).count()
    nombre_contrats_actifs = contrats_actifs.count()
    nombre_locataires = contrats_actifs.values('locataire').distinct().count()

    paiements = Paiement.objects.filter(contrat__proprietaire=user, mois=mois)
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
        Contrat.objects.filter(proprietaire=user, statut=Contrat.Statut.EN_COURS)
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
