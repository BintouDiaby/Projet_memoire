from django.shortcuts import render, redirect
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.contrib import messages
from .models import Contrat, Paiement, DocumentContrat, Reclamation, EtatDesLieux
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


@login_required
def ui_list(request):
    """Liste des contrats de l'utilisateur connecté (locataire ou propriétaire)."""
    from utilisateurs.models import Utilisateur

    user = request.user
    contrats = Contrat.objects.select_related('bien', 'locataire', 'proprietaire')

    if user.is_staff:
        pass  # l'admin voit tout
    elif user.role == Utilisateur.Role.LOCATAIRE:
        contrats = contrats.filter(locataire=user)
    else:
        contrats = contrats.filter(proprietaire=user)

    contrats = contrats.order_by('-date_creation')[:50]
    return render(request, 'contrats/list.html', {'contrats': contrats, 'title': 'Contrats'})


@login_required
def ui_detail(request, pk):
    from django.http import Http404, HttpResponseForbidden

    contrat = Contrat.objects.select_related('bien', 'locataire', 'proprietaire').filter(id=pk).first()
    if not contrat:
        raise Http404('Contrat non trouvé')

    user = request.user
    if user.id not in (contrat.locataire_id, contrat.proprietaire_id) and not user.is_staff:
        return HttpResponseForbidden('Accès refusé')

    etats = {e.type_etat: e for e in contrat.etats_des_lieux.all()}

    return render(request, 'contrats/detail.html', {
        'contrat': contrat,
        'est_locataire': user == contrat.locataire,
        'est_proprietaire': user == contrat.proprietaire,
        'etat_entree': etats.get('entree'),
        'etat_sortie': etats.get('sortie'),
    })


@login_required
def contrat_suivi(request, pk):
    """Centre de suivi du contrat : aperçu, facture actuelle, paiements,
    messages, réclamations et visites — tout organisé autour du contrat."""
    from django.http import Http404, HttpResponseForbidden
    from facturation.models import Facture
    from messagerie.models import Conversation
    from biens.models import Visite

    contrat = Contrat.objects.select_related(
        'bien', 'locataire', 'proprietaire', 'proprietaire__company'
    ).filter(id=pk).first()
    if not contrat:
        raise Http404('Contrat non trouvé')

    user = request.user
    if user.id not in (contrat.locataire_id, contrat.proprietaire_id) and not user.is_staff:
        return HttpResponseForbidden('Accès refusé')

    est_locataire = user == contrat.locataire
    est_proprietaire = user == contrat.proprietaire or user.is_staff
    today = timezone.now().date()

    factures = list(
        Facture.objects.filter(contrat=contrat).select_related('paiement').order_by('-date_generation')
    )
    facture_actuelle = factures[0] if factures else None
    prochaine_echeance = next(
        (f for f in sorted(factures, key=lambda f: f.date_echéance)
         if f.statut in (Facture.Statut.GENEREE, Facture.Statut.ENVOYEE)),
        None
    )

    paiements = list(Paiement.objects.filter(contrat=contrat).order_by('-mois'))
    nb_paiements_payes = sum(1 for p in paiements if p.statut == Paiement.Statut.RECU)
    nb_paiements_total = contrat.nombre_mois_minimum or len(paiements) or 1
    nb_paiements_restants = max(nb_paiements_total - nb_paiements_payes, 0)
    progression_pct = round(100 * nb_paiements_payes / nb_paiements_total) if nb_paiements_total else 0

    conv = Conversation.objects.filter(bien=contrat.bien, demandeur=contrat.locataire).first() if contrat.locataire else None
    dernier_message = conv.messages.order_by('-cree_le').first() if conv else None

    reclamations = []
    if contrat.locataire:
        reclamations = list(
            Reclamation.objects.filter(bien=contrat.bien, locataire=contrat.locataire).order_by('-cree_le')
        )

    visites = []
    if contrat.locataire:
        visites = list(
            Visite.objects.filter(bien=contrat.bien, locataire=contrat.locataire).order_by('-date_visite')
        )

    # Journal d'activité : fusion chronologique d'événements réels
    journal = []
    if contrat.date_signature:
        journal.append({'type': 'done', 'icon': '✓', 'texte': 'Contrat signé', 'date': contrat.date_signature})
    for f in factures:
        journal.append({'type': 'done', 'icon': '📄', 'texte': f"Facture générée — {f.numero_facture}", 'date': f.date_generation})
        if f.statut == Facture.Statut.PAYEE and f.date_paiement:
            moyen = f" via {f.get_mode_paiement_display()}" if f.mode_paiement else ''
            date_paiement_dt = timezone.make_aware(timezone.datetime.combine(f.date_paiement, timezone.datetime.min.time()))
            journal.append({
                'type': 'pay', 'icon': '💳',
                'texte': f"Paiement effectué{moyen} — {f.numero_facture}",
                'date': date_paiement_dt,
            })
    if conv:
        for m in conv.messages.order_by('-cree_le')[:5]:
            qui = m.expediteur.get_full_name() or m.expediteur.username
            journal.append({'type': 'msg', 'icon': '💬', 'texte': f"Message de {qui}", 'date': m.cree_le})
    journal.sort(key=lambda j: j['date'], reverse=True)
    journal = journal[:10]

    return render(request, 'contrats/suivi.html', {
        'contrat': contrat,
        'est_locataire': est_locataire,
        'est_proprietaire': est_proprietaire,
        'facture_actuelle': facture_actuelle,
        'prochaine_echeance': prochaine_echeance,
        'paiements': paiements,
        'nb_paiements_payes': nb_paiements_payes,
        'nb_paiements_total': nb_paiements_total,
        'nb_paiements_restants': nb_paiements_restants,
        'progression_pct': progression_pct,
        'conv': conv,
        'dernier_message': dernier_message,
        'reclamations': reclamations,
        'visites': visites,
        'journal': journal,
        'today': today,
    })


@login_required
def etat_des_lieux_creer(request, contrat_id, type_etat):
    """Le propriétaire réalise l'état des lieux d'entrée ou de sortie d'un contrat."""
    from django.http import Http404, HttpResponseForbidden

    if type_etat not in ('entree', 'sortie'):
        raise Http404('Type invalide')

    contrat = Contrat.objects.filter(id=contrat_id).first()
    if not contrat:
        raise Http404('Contrat non trouvé')
    if request.user != contrat.proprietaire and not request.user.is_staff:
        return HttpResponseForbidden('Réservé au propriétaire.')

    if request.method == 'POST':
        EtatDesLieux.objects.update_or_create(
            contrat=contrat, type_etat=type_etat,
            defaults={
                'etat_general': request.POST.get('etat_general', EtatDesLieux.EtatGeneral.BON),
                'observations': request.POST.get('observations', '').strip(),
                'realise_par': request.user,
            }
        )
        messages.success(request, f"État des lieux {'d’entrée' if type_etat == 'entree' else 'de sortie'} enregistré.")
    return redirect('contrats_ui:detail', pk=contrat_id)


@login_required
def caution_traiter(request, contrat_id):
    """Le propriétaire enregistre le traitement de la caution (remboursée/retenue)."""
    from django.http import Http404, HttpResponseForbidden
    from django.utils import timezone as tz

    contrat = Contrat.objects.filter(id=contrat_id).first()
    if not contrat:
        raise Http404('Contrat non trouvé')
    if request.user != contrat.proprietaire and not request.user.is_staff:
        return HttpResponseForbidden('Réservé au propriétaire.')

    if request.method == 'POST':
        statut = request.POST.get('statut_caution')
        if statut in (Contrat.StatutCaution.REMBOURSEE, Contrat.StatutCaution.RETENUE):
            contrat.statut_caution = statut
            contrat.montant_caution_rembourse = request.POST.get('montant_caution_rembourse') or 0
            contrat.motif_retenue_caution = request.POST.get('motif_retenue_caution', '').strip()
            contrat.date_remboursement_caution = tz.now().date()
            contrat.save(update_fields=[
                'statut_caution', 'montant_caution_rembourse',
                'motif_retenue_caution', 'date_remboursement_caution',
            ])
            messages.success(request, "Caution mise à jour.")
    return redirect('contrats_ui:detail', pk=contrat_id)


@login_required
def ui_mes_locations(request):
    """Ancienne page « Mes locations » (liste Bootstrap nue, sans styles ni
    KPI) — remplacée par la page « Mes contrats » réellement maintenue.
    Conservée en redirection pour ne pas casser un lien externe/favori."""
    return redirect('dashboard_contrats')


@login_required
def contrats_nouveau(request):
    """Créer un nouveau contrat de location (propriétaire/gestionnaire)."""
    from django.contrib import messages
    from biens.models import Bien
    from messagerie.models import Conversation
    from biens.models import Visite
    from utilisateurs.models import Utilisateur
    from dashboard.views import _sidebar_context
    from .forms import ContratCreationForm

    user = request.user
    if user.role not in (Utilisateur.Role.PROPRIETAIRE, Utilisateur.Role.GESTIONNAIRE):
        messages.error(request, "Seuls les comptes propriétaire/gestionnaire peuvent créer un contrat.")
        return redirect('dashboard')

    biens_qs = Bien.objects.filter(proprietaire=user).order_by('titre')

    # Locataires "connus" du propriétaire : quelqu'un qui a déjà écrit,
    # demandé une visite ou eu un contrat avec lui — pas tous les locataires
    # de la plateforme.
    locataire_ids = set(Conversation.objects.filter(proprietaire=user).values_list('demandeur_id', flat=True))
    locataire_ids |= set(Visite.objects.filter(bien__proprietaire=user).values_list('locataire_id', flat=True))
    locataire_ids |= set(Contrat.objects.filter(proprietaire=user).exclude(locataire=None).values_list('locataire_id', flat=True))
    locataires_qs = Utilisateur.objects.filter(id__in=locataire_ids).order_by('first_name', 'last_name')

    if request.method == 'POST':
        form = ContratCreationForm(request.POST)
        form.fields['bien'].queryset = biens_qs
        form.fields['locataire'].queryset = locataires_qs
        if form.is_valid():
            contrat = form.save(commit=False)
            contrat.proprietaire = user
            contrat.statut = Contrat.Statut.EN_COURS
            contrat.date_signature = timezone.now()
            contrat.generer_numero()
            contrat.save()
            messages.success(request, f"Contrat {contrat.numero_contrat} créé avec succès.")
            return redirect('/dashboard/contrats/')
    else:
        form = ContratCreationForm()
        form.fields['bien'].queryset = biens_qs
        form.fields['locataire'].queryset = locataires_qs

    ctx = _sidebar_context(user)
    ctx.update({'form': form, 'has_biens': biens_qs.exists(), 'has_locataires': locataires_qs.exists()})
    return render(request, 'dashboard/contrat_nouveau.html', ctx)


@login_required
def reclamation_creer(request, bien_id):
    """Le locataire signale un problème sur un bien qu'il loue (ou a loué)."""
    from django.http import Http404, HttpResponseForbidden
    from django.contrib import messages
    from biens.models import Bien
    from dashboard.services import NotificationService
    from .forms import ReclamationForm

    user = request.user
    bien = Bien.objects.select_related('proprietaire').filter(id=bien_id).first()
    if not bien:
        raise Http404('Bien non trouvé')

    a_un_contrat = Contrat.objects.filter(bien=bien, locataire=user).exists()
    if not a_un_contrat:
        return HttpResponseForbidden("Vous devez avoir loué ce bien pour signaler un problème.")

    if request.method == 'POST':
        form = ReclamationForm(request.POST)
        if form.is_valid():
            reclamation = form.save(commit=False)
            reclamation.bien = bien
            reclamation.locataire = user
            reclamation.save()
            NotificationService.send(
                destinataire=bien.proprietaire,
                expediteur=user,
                type_notification='reclamation',
                titre=f"Réclamation — {bien.titre}",
                message=reclamation.titre,
                lien='/dashboard/reclamations/',
            )
            messages.success(request, "Votre signalement a été envoyé au propriétaire.")
            return redirect('/contrats/mes-reclamations/')
    else:
        form = ReclamationForm()

    return render(request, 'contrats/reclamation_form.html', {'form': form, 'bien': bien})


@login_required
def mes_reclamations(request):
    """Le locataire suit le statut de ses réclamations et lit la réponse du propriétaire."""
    from biens.models import Bien

    reclamations = (
        Reclamation.objects.filter(locataire=request.user)
        .select_related('bien', 'bien__proprietaire__company')
        .order_by('-cree_le')
    )
    biens_eligibles = (
        Bien.objects.filter(contrats__locataire=request.user)
        .distinct()
        .order_by('titre')
    )
    return render(request, 'contrats/mes_reclamations.html', {
        'reclamations': reclamations,
        'biens_eligibles': biens_eligibles,
    })


def _build_contrat_pdf(contrat, buffer):
    """Écrit un récapitulatif PDF du contrat dans `buffer`."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Titre', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#185FA5'))
    sub_style = ParagraphStyle('Sous', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#6b7280'), spaceAfter=16)

    elements = [
        Paragraph(f"Contrat {contrat.numero_contrat}", title_style),
        Paragraph(f"{contrat.bien.titre} — {contrat.locataire.get_full_name() if contrat.locataire else '—'}", sub_style),
    ]

    data = [
        ['Champ', 'Valeur'],
        ['Bien', contrat.bien.titre],
        ['Propriétaire', contrat.proprietaire.get_full_name() or contrat.proprietaire.username],
        ['Locataire', contrat.locataire.get_full_name() if contrat.locataire else '—'],
        ['Statut', contrat.get_statut_display()],
        ['Date de début', contrat.date_debut.strftime('%d/%m/%Y')],
        ['Date de fin', contrat.date_fin.strftime('%d/%m/%Y')],
        ['Loyer mensuel', f"{contrat.prix_mensuel:,.0f} FCFA".replace(',', ' ')],
        ['Dépôt de garantie', f"{contrat.prix_depot_garantie:,.0f} FCFA".replace(',', ' ')],
    ]
    table = Table(data, colWidths=[60*mm, 100*mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#185FA5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 6*mm))
    if contrat.conditions_speciales:
        elements.append(Paragraph(f"Conditions particulières : {contrat.conditions_speciales}", styles['Normal']))

    doc.build(elements)


@login_required
def mes_contrats_zip(request):
    """Télécharge un zip contenant un récapitulatif PDF de chaque contrat du locataire."""
    from django.http import HttpResponse
    import io
    import zipfile

    if request.user.role != 'locataire':
        return redirect('dashboard')

    contrats = Contrat.objects.filter(locataire=request.user).select_related('bien', 'locataire', 'proprietaire')
    if not contrats.exists():
        return redirect('parametres')

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for contrat in contrats:
            pdf_buffer = io.BytesIO()
            _build_contrat_pdf(contrat, pdf_buffer)
            zf.writestr(f"{contrat.numero_contrat}.pdf", pdf_buffer.getvalue())

    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="contrats.zip"'
    return response
