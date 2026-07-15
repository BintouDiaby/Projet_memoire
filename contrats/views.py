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
        if user.role in ('proprietaire', 'gestionnaire'):
            return Contrat.objects.filter(proprietaire__in=user.comptes_entreprise())
        elif user.role == 'locataire':
            return Contrat.objects.filter(locataire=user)
        elif user.is_staff or user.role == 'admin':
            return Contrat.objects.all()
        return Contrat.objects.none()
    
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
        if user.role in ('proprietaire', 'gestionnaire'):
            return Paiement.objects.filter(contrat__proprietaire__in=user.comptes_entreprise())
        elif user.role == 'locataire':
            return Paiement.objects.filter(contrat__locataire=user)
        elif user.is_staff or user.role == 'admin':
            return Paiement.objects.all()
        return Paiement.objects.none()
    
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
        contrats = contrats.filter(proprietaire__in=user.comptes_entreprise())

    voir_archives = request.GET.get('archives') == '1'
    nb_archives = contrats.filter(est_archive=True).count()
    contrats = contrats.filter(est_archive=True) if voir_archives else contrats.filter(est_archive=False)
    contrats = contrats.order_by('-date_creation')[:50]
    return render(request, 'contrats/list.html', {
        'contrats': contrats, 'title': 'Contrats',
        'voir_archives': voir_archives, 'nb_archives': nb_archives,
    })


@login_required
def ui_detail(request, pk):
    from django.http import Http404, HttpResponseForbidden

    contrat = Contrat.objects.select_related('bien', 'locataire', 'proprietaire').filter(id=pk).first()
    if not contrat:
        raise Http404('Contrat non trouvé')

    user = request.user
    if user.id != contrat.locataire_id and not user.meme_entreprise(contrat.proprietaire) and not user.is_staff:
        return HttpResponseForbidden('Accès refusé')

    etats = {e.type_etat: e for e in contrat.etats_des_lieux.all()}

    return render(request, 'contrats/detail.html', {
        'contrat': contrat,
        'est_locataire': user == contrat.locataire,
        'est_proprietaire': user.meme_entreprise(contrat.proprietaire),
        'etat_entree': etats.get('entree'),
        'etat_sortie': etats.get('sortie'),
        'articles_contrat': contrat.texte_contrat_signe or contrat.texte_articles_actuel,
    })


@login_required
def contrat_pdf(request, contrat_id):
    """Télécharge le PDF du contrat (récapitulatif + articles), accessible
    au locataire comme au propriétaire — pas besoin de passer par le zip
    global de /parametres/."""
    from django.http import Http404, HttpResponseForbidden, HttpResponse
    import io

    contrat = Contrat.objects.select_related('bien', 'locataire', 'proprietaire').filter(id=contrat_id).first()
    if not contrat:
        raise Http404('Contrat non trouvé')
    if request.user.id != contrat.locataire_id and not request.user.meme_entreprise(contrat.proprietaire) and not request.user.is_staff:
        return HttpResponseForbidden('Accès refusé')

    buffer = io.BytesIO()
    _build_contrat_pdf(contrat, buffer)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{contrat.numero_contrat}.pdf"'
    return response


@login_required
def contrat_rappeler(request, contrat_id):
    """Le propriétaire rappelle un contrat déjà envoyé (mais pas encore
    signé) pour le corriger : repasse en brouillon, efface l'envoi et le
    texte figé, prévient le locataire, puis renvoie vers la complétion."""
    from django.http import Http404, HttpResponseForbidden
    from django.contrib import messages
    from dashboard.services import NotificationService

    contrat = Contrat.objects.select_related('bien', 'locataire').filter(id=contrat_id).first()
    if not contrat:
        raise Http404('Contrat non trouvé')
    if not request.user.meme_entreprise(contrat.proprietaire) and not request.user.is_staff:
        return HttpResponseForbidden('Réservé au propriétaire.')
    if contrat.statut != Contrat.Statut.EN_ATTENTE_SIGNATURE:
        return redirect('contrats_ui:detail', pk=contrat.id)

    if request.method == 'POST':
        contrat.statut = Contrat.Statut.BROUILLON
        contrat.date_envoi_signature = None
        contrat.texte_contrat_signe = ''
        contrat.save()
        messages.success(request, "Contrat rappelé — vous pouvez le corriger avant de le renvoyer.")
        if contrat.locataire:
            NotificationService.send(
                destinataire=contrat.locataire, expediteur=request.user,
                type_notification='contrat',
                titre=f"Contrat rappelé — {contrat.bien.titre}",
                message="Le propriétaire a rappelé ce contrat pour le corriger. Vous recevrez une nouvelle version à signer.",
                lien=f'/contrats/{contrat.id}/',
            )
        return redirect('contrats_ui:completer', contrat_id=contrat.id)

    return redirect('contrats_ui:detail', pk=contrat.id)


@login_required
def contrat_supprimer(request, contrat_id):
    """Supprime un contrat — uniquement possible tant qu'il est en brouillon
    (jamais envoyé, jamais signé, aucun paiement ni facture ne peut lui être
    rattaché à ce stade). Au-delà, on rappelle le contrat (voir
    `contrat_rappeler`) plutôt que de détruire un engagement réel."""
    from django.http import Http404, HttpResponseForbidden

    contrat = Contrat.objects.select_related('bien').filter(id=contrat_id).first()
    if not contrat:
        raise Http404('Contrat non trouvé')
    if not request.user.meme_entreprise(contrat.proprietaire) and not request.user.is_staff:
        return HttpResponseForbidden('Réservé au propriétaire.')
    if contrat.statut != Contrat.Statut.BROUILLON:
        return redirect('contrats_ui:detail', pk=contrat.id)

    if request.method == 'POST':
        contrat.delete()
        return redirect('contrats_ui:list')
    return render(request, 'contrats/confirm_delete.html', {'contrat': contrat})


@login_required
def contrat_resilier(request, contrat_id):
    """Résiliation anticipée d'un contrat en cours (ou suspendu), à
    l'initiative du propriétaire, avec motif obligatoire. Distinct d'une fin
    de contrat naturelle à échéance (statut TERMINE)."""
    from django.http import Http404, HttpResponseForbidden
    from dashboard.services import NotificationService

    contrat = Contrat.objects.select_related('bien', 'locataire').filter(id=contrat_id).first()
    if not contrat:
        raise Http404('Contrat non trouvé')
    if not request.user.meme_entreprise(contrat.proprietaire) and not request.user.is_staff:
        return HttpResponseForbidden('Réservé au propriétaire.')
    if contrat.statut not in (Contrat.Statut.EN_COURS, Contrat.Statut.SUSPENDU):
        return redirect('contrats_ui:detail', pk=contrat.id)

    if request.method == 'POST':
        motif = request.POST.get('motif', '').strip()
        if not motif:
            messages.error(request, "Merci d'indiquer un motif de résiliation.")
            return redirect('contrats_ui:detail', pk=contrat.id)

        contrat.statut = Contrat.Statut.RESILIE
        contrat.date_resiliation = timezone.now()
        contrat.motif_resiliation = motif
        contrat.save(update_fields=['statut', 'date_resiliation', 'motif_resiliation'])

        if contrat.locataire:
            NotificationService.send(
                destinataire=contrat.locataire,
                type_notification='contrat',
                titre=f"Contrat résilié — {contrat.bien.titre}",
                message=f"Votre contrat {contrat.numero_contrat} a été résilié. Motif : {motif}",
                lien=f'/contrats/{contrat.id}/',
            )
        messages.success(request, "Le contrat a été résilié.")

    return redirect('contrats_ui:detail', pk=contrat.id)


@login_required
def contrat_archiver(request, contrat_id):
    """Archive (ou désarchive) un contrat déjà terminé/résilié : le masque
    des listes actives sans toucher à ses données. Volontairement interdit
    sur un contrat encore en cours ou en attente — l'archivage est un
    rangement, pas une façon de faire disparaître un engagement actif."""
    from django.http import Http404, HttpResponseForbidden
    from django.contrib import messages

    contrat = Contrat.objects.filter(id=contrat_id).first()
    if not contrat:
        raise Http404('Contrat non trouvé')
    if not request.user.meme_entreprise(contrat.proprietaire) and not request.user.is_staff:
        return HttpResponseForbidden('Réservé au propriétaire.')
    if contrat.statut not in (Contrat.Statut.TERMINE, Contrat.Statut.RESILIE):
        return redirect('contrats_ui:detail', pk=contrat.id)

    if request.method == 'POST':
        contrat.est_archive = not contrat.est_archive
        contrat.save(update_fields=['est_archive'])
        messages.success(request, "Contrat archivé." if contrat.est_archive else "Contrat désarchivé.")

    return redirect('contrats_ui:detail', pk=contrat.id)


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
    if user.id != contrat.locataire_id and not user.meme_entreprise(contrat.proprietaire) and not user.is_staff:
        return HttpResponseForbidden('Accès refusé')

    est_locataire = user == contrat.locataire
    est_proprietaire = user.meme_entreprise(contrat.proprietaire) or user.is_staff
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

    # Frise visuelle du contrat : 5 étapes calculées à partir de la facture la
    # plus récente (aucun état « quittance envoyée » distinct n'existe dans le
    # modèle — la quittance est simplement disponible dès que la facture est PAYEE).
    f_actu = facture_actuelle
    date_paiement_dt = None
    if f_actu and f_actu.date_paiement:
        date_paiement_dt = timezone.make_aware(timezone.datetime.combine(f_actu.date_paiement, timezone.datetime.min.time()))

    frise_etapes = [
        {'cle': 'signe', 'label': 'Contrat signé', 'fait': bool(contrat.date_signature), 'date': contrat.date_signature},
        {'cle': 'facture', 'label': 'Facture générée', 'fait': bool(f_actu), 'date': f_actu.date_generation if f_actu else None},
        {'cle': 'paiement', 'label': 'Paiement effectué',
         'fait': bool(f_actu and f_actu.statut in (Facture.Statut.EN_VALIDATION, Facture.Statut.PAYEE)),
         'date': f_actu.date_declaration_paiement if f_actu else None},
        {'cle': 'confirme', 'label': 'Paiement confirmé', 'fait': bool(f_actu and f_actu.statut == Facture.Statut.PAYEE), 'date': date_paiement_dt},
        {'cle': 'quittance', 'label': 'Quittance disponible', 'fait': bool(f_actu and f_actu.statut == Facture.Statut.PAYEE), 'date': date_paiement_dt},
    ]
    en_cours_trouve = False
    for etape in frise_etapes:
        if not etape['fait'] and not en_cours_trouve:
            etape['en_cours'] = True
            en_cours_trouve = True
        else:
            etape['en_cours'] = False

    # Centre des échéances : calendrier mensuel, identique pour le locataire
    # et le propriétaire — statut réel par mois (payé / en attente / en
    # retard / rendez-vous espèces prévu / à venir), sur une fenêtre glissante
    # autour d'aujourd'hui plutôt que toute la durée du bail (souvent longue).
    def _ajouter_mois(d, n):
        mois_total = d.month - 1 + n
        annee = d.year + mois_total // 12
        mois = mois_total % 12 + 1
        return d.replace(year=annee, month=mois, day=1)

    def _premier_du_mois_suivant(d):
        return _ajouter_mois(d, 1)

    paiements_par_mois = {p.mois: p for p in paiements}
    factures_par_mois = {f.paiement.mois: f for f in factures if f.paiement_id}

    mois_actuel = today.replace(day=1)
    debut_fenetre = max(_ajouter_mois(mois_actuel, -2), contrat.date_debut.replace(day=1))
    fin_fenetre = min(_ajouter_mois(mois_actuel, 3), contrat.date_fin.replace(day=1))

    echeances = []
    mois_cur = debut_fenetre
    while mois_cur <= fin_fenetre:
        p = paiements_par_mois.get(mois_cur)
        f = factures_par_mois.get(mois_cur)
        entree = {'mois': mois_cur, 'est_mois_courant': mois_cur == today.replace(day=1)}

        rdv_confirme = None
        if f:
            rdv_confirme = f.rendez_vous_paiement.filter(statut='confirme').order_by('-date_confirmee').first()

        if p and p.statut == Paiement.Statut.RECU:
            entree.update(icone='✔', statut='paye', texte='Payé')
        elif f and f.statut == Facture.Statut.EN_VALIDATION:
            entree.update(icone='🟡', statut='validation', texte='Paiement déclaré — en attente de confirmation')
        elif rdv_confirme:
            from django.utils.formats import date_format
            entree.update(
                icone='🟠', statut='rdv',
                texte=f"Rendez-vous prévu le {date_format(timezone.localtime(rdv_confirme.date_confirmee), 'j F')} à {timezone.localtime(rdv_confirme.date_confirmee).strftime('%H:%M')}",
            )
        elif p and p.statut in (Paiement.Statut.RETARD_MINEUR, Paiement.Statut.RETARD_MAJEUR, Paiement.Statut.IMPAYE):
            jours_retard = (today - p.date_limite).days
            entree.update(icone='🔴', statut='retard', texte=f"En retard de {jours_retard} jour{'s' if jours_retard > 1 else ''}")
        elif p:
            entree.update(icone='🟡', statut='attente', texte='En attente de paiement')
        else:
            entree.update(icone='⏳', statut='a_venir', texte='À venir')
        echeances.append(entree)
        mois_cur = _premier_du_mois_suivant(mois_cur)

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
        'frise_etapes': frise_etapes,
        'echeances': echeances,
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
    if not request.user.meme_entreprise(contrat.proprietaire) and not request.user.is_staff:
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
    if not request.user.meme_entreprise(contrat.proprietaire) and not request.user.is_staff:
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
def envoyer_mise_en_demeure(request, paiement_id):
    """Le propriétaire envoie une mise en demeure formelle au locataire pour
    un paiement en retard : une lettre qui accorde un dernier délai de
    régularisation, jamais une saisine de la justice. Décision humaine,
    jamais automatique — voir contrats.escalade qui se contente de la
    recommander."""
    from django.http import Http404, HttpResponseForbidden
    from datetime import datetime
    from .models import Paiement, MiseEnDemeure
    from dashboard.services import NotificationService

    paiement = Paiement.objects.select_related('contrat__bien', 'contrat__locataire', 'contrat__proprietaire').filter(id=paiement_id).first()
    if not paiement:
        raise Http404('Paiement non trouvé')
    contrat = paiement.contrat
    if not request.user.meme_entreprise(contrat.proprietaire) and not request.user.is_staff:
        return HttpResponseForbidden('Réservé au propriétaire.')

    next_url = request.POST.get('next') or '/dashboard/facturation/'

    if request.method == 'POST':
        date_str = request.POST.get('date_limite_regularisation', '').strip()
        try:
            date_limite = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Date limite de régularisation invalide.")
            return redirect(next_url)

        mise = MiseEnDemeure.objects.create(
            paiement=paiement, contrat=contrat,
            objet=request.POST.get('objet', '').strip() or 'Mise en demeure pour non-paiement',
            date_limite_regularisation=date_limite,
            envoi_application=request.POST.get('envoi_application') == 'on',
            envoi_email=request.POST.get('envoi_email') == 'on',
            envoi_pdf=request.POST.get('envoi_pdf') == 'on',
            message_complementaire=request.POST.get('message_complementaire', '').strip(),
        )
        messages.success(request, "Mise en demeure envoyée au locataire.")

        facture_liee = getattr(paiement, 'facture', None)
        lien_lettre = f'/dashboard/facturation/{facture_liee.id}/' if facture_liee else '/mes-notifications/'

        if contrat.locataire and mise.envoi_application:
            NotificationService.send(
                destinataire=contrat.locataire, expediteur=request.user,
                type_notification='mise_en_demeure',
                titre=f"Mise en demeure — {contrat.bien.titre}",
                message=mise.texte_lettre(),
                lien=lien_lettre,
            )
        if contrat.locataire and mise.envoi_email and contrat.locataire.email:
            from django.core.mail import send_mail
            from django.conf import settings
            try:
                send_mail(
                    subject=f"Mise en demeure — {contrat.bien.titre}",
                    message=mise.texte_lettre(),
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                    recipient_list=[contrat.locataire.email],
                    fail_silently=True,
                )
            except Exception:
                pass
    return redirect(next_url)


@login_required
def gerer_mise_en_demeure(request, mise_id):
    """Le propriétaire gère la suite d'une mise en demeure une fois son délai
    expiré : accorder un délai supplémentaire, clôturer le dossier (situation
    réglée à l'amiable), ou marquer le dossier prêt pour une procédure
    contentieuse. L'application ne saisit jamais la justice elle-même —
    ce statut est un simple repère interne pour le propriétaire."""
    from django.http import Http404, HttpResponseForbidden
    from datetime import datetime
    from .models import MiseEnDemeure
    from dashboard.services import NotificationService

    mise = MiseEnDemeure.objects.select_related('contrat__bien', 'contrat__locataire').filter(id=mise_id).first()
    if not mise:
        raise Http404('Mise en demeure non trouvée')
    contrat = mise.contrat
    if not request.user.meme_entreprise(contrat.proprietaire) and not request.user.is_staff:
        return HttpResponseForbidden('Réservé au propriétaire.')

    next_url = request.POST.get('next') or '/dashboard/facturation/'

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delai_supplementaire':
            date_str = request.POST.get('nouvelle_date_limite', '').strip()
            try:
                nouvelle_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, "Date invalide.")
                return redirect(next_url)
            mise.date_limite_regularisation = nouvelle_date
            mise.statut = MiseEnDemeure.Statut.DELAI_SUPPLEMENTAIRE
            mise.date_resolution = None
            mise.save(update_fields=['date_limite_regularisation', 'statut', 'date_resolution'])
            messages.success(request, "Délai supplémentaire accordé.")
            if contrat.locataire:
                facture_liee = getattr(mise.paiement, 'facture', None)
                NotificationService.send(
                    destinataire=contrat.locataire, expediteur=request.user,
                    type_notification='mise_en_demeure',
                    titre=f"Délai supplémentaire accordé — {contrat.bien.titre}",
                    message=f"Un délai supplémentaire vous est accordé pour régulariser votre situation, jusqu'au {nouvelle_date.strftime('%d %B %Y')}.",
                    lien=f'/dashboard/facturation/{facture_liee.id}/' if facture_liee else '/mes-notifications/',
                )
        elif action == 'cloturer':
            mise.statut = MiseEnDemeure.Statut.CLOTUREE
            mise.date_resolution = timezone.now()
            mise.save(update_fields=['statut', 'date_resolution'])
            messages.success(request, "Dossier clôturé.")
        elif action == 'procedure':
            mise.statut = MiseEnDemeure.Statut.PROCEDURE
            mise.date_resolution = timezone.now()
            mise.save(update_fields=['statut', 'date_resolution'])
            messages.success(request, "Dossier marqué prêt pour une procédure contentieuse.")
    return redirect(next_url)


@login_required
def mise_en_demeure_pdf(request, mise_id):
    """Télécharge la lettre de mise en demeure en PDF."""
    from django.http import Http404, HttpResponseForbidden, HttpResponse
    from .models import MiseEnDemeure
    import io

    mise = MiseEnDemeure.objects.select_related('contrat__bien', 'contrat__locataire', 'contrat__proprietaire').filter(id=mise_id).first()
    if not mise:
        raise Http404('Mise en demeure non trouvée')
    if request.user.id != mise.contrat.locataire_id and not request.user.meme_entreprise(mise.contrat.proprietaire) and not request.user.is_staff:
        return HttpResponseForbidden('Accès refusé')

    buffer = io.BytesIO()
    _build_mise_en_demeure_pdf(mise, buffer)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="mise-en-demeure-{mise.contrat.numero_contrat}.pdf"'
    return response


@login_required
def preparer_dossier_juridique(request, contrat_id):
    """Compile le dossier complet d'un contrat en situation d'impayé :
    contrat signé, historique des paiements, factures impayées,
    notifications, mises en demeure, messages échangés — prêt si le
    propriétaire décide d'engager une procédure. Ne prend aucune décision."""
    from django.http import Http404, HttpResponseForbidden
    from facturation.models import Facture
    from messagerie.models import Conversation
    from dashboard.models import Notification

    contrat = Contrat.objects.select_related('bien', 'locataire', 'proprietaire').filter(id=contrat_id).first()
    if not contrat:
        raise Http404('Contrat non trouvé')
    if not request.user.meme_entreprise(contrat.proprietaire) and not request.user.is_staff:
        return HttpResponseForbidden('Réservé au propriétaire.')

    paiements = list(Paiement.objects.filter(contrat=contrat).order_by('-mois'))
    factures_impayees = list(
        Facture.objects.filter(contrat=contrat)
        .exclude(statut__in=[Facture.Statut.PAYEE, Facture.Statut.ANNULEE, Facture.Statut.BROUILLON])
        .select_related('paiement').order_by('-date_generation')
    )
    mises_en_demeure = list(contrat.mises_en_demeure.order_by('-date_creation'))

    notifications = []
    if contrat.locataire:
        notifications = list(
            Notification.objects.filter(
                destinataire=contrat.proprietaire, type_notification__in=['paiement', 'mise_en_demeure']
            ).order_by('-date_creation')[:30]
        )

    conv = Conversation.objects.filter(bien=contrat.bien, demandeur=contrat.locataire).first() if contrat.locataire else None
    messages_echanges = list(conv.messages.select_related('expediteur').order_by('cree_le')) if conv else []

    return render(request, 'contrats/dossier_juridique.html', {
        'contrat': contrat,
        'paiements': paiements,
        'factures_impayees': factures_impayees,
        'mises_en_demeure': mises_en_demeure,
        'notifications': notifications,
        'messages_echanges': messages_echanges,
    })


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

    biens_qs = Bien.objects.filter(proprietaire__in=user.comptes_entreprise()).order_by('titre')

    # Locataires "connus" du propriétaire : quelqu'un qui a déjà écrit,
    # demandé une visite ou eu un contrat avec lui — pas tous les locataires
    # de la plateforme.
    locataire_ids = set(Conversation.objects.filter(proprietaire__in=user.comptes_entreprise()).values_list('demandeur_id', flat=True))
    locataire_ids |= set(Visite.objects.filter(bien__proprietaire__in=user.comptes_entreprise()).values_list('locataire_id', flat=True))
    locataire_ids |= set(Contrat.objects.filter(proprietaire__in=user.comptes_entreprise()).exclude(locataire=None).values_list('locataire_id', flat=True))
    locataires_qs = Utilisateur.objects.filter(id__in=locataire_ids).order_by('first_name', 'last_name')

    if request.method == 'POST':
        form = ContratCreationForm(request.POST)
        form.fields['bien'].queryset = biens_qs
        form.fields['locataire'].queryset = locataires_qs
        if form.is_valid():
            contrat = form.save(commit=False)
            contrat.proprietaire = user
            contrat.statut = Contrat.Statut.EN_ATTENTE_SIGNATURE
            contrat.date_envoi_signature = timezone.now()
            contrat.generer_numero()
            contrat.texte_contrat_signe = contrat.texte_articles_actuel
            contrat.save()
            _notifier_contrat_a_signer(contrat)
            messages.success(request, f"Contrat {contrat.numero_contrat} envoyé au locataire pour signature.")
            return redirect('/dashboard/contrats/')
    else:
        form = ContratCreationForm()
        form.fields['bien'].queryset = biens_qs
        form.fields['locataire'].queryset = locataires_qs

    ctx = _sidebar_context(user)
    ctx.update({'form': form, 'has_biens': biens_qs.exists(), 'has_locataires': locataires_qs.exists()})
    return render(request, 'dashboard/contrat_nouveau.html', ctx)


def _notifier_contrat_a_signer(contrat):
    from dashboard.services import NotificationService

    if not contrat.locataire:
        return
    NotificationService.send(
        destinataire=contrat.locataire, expediteur=contrat.proprietaire,
        type_notification='contrat',
        titre=f"Contrat à signer — {contrat.bien.titre}",
        message=(
            f"{contrat.proprietaire.get_full_name() or contrat.proprietaire.username} vous a envoyé "
            f"le contrat {contrat.numero_contrat} pour signature."
        ),
        lien=f'/contrats/{contrat.id}/',
    )


@login_required
def contrat_completer(request, contrat_id):
    """Le propriétaire complète un contrat brouillon (créé automatiquement à
    la confirmation d'une réservation, ou laissé en brouillon) puis l'envoie
    au locataire pour signature."""
    from django.http import Http404, HttpResponseForbidden
    from django.contrib import messages
    from biens.models import Bien
    from utilisateurs.models import Utilisateur
    from dashboard.views import _sidebar_context
    from .forms import ContratCreationForm

    contrat = Contrat.objects.select_related('bien', 'locataire').filter(id=contrat_id).first()
    if not contrat:
        raise Http404('Contrat non trouvé')

    user = request.user
    if not user.meme_entreprise(contrat.proprietaire) and not user.is_staff:
        return HttpResponseForbidden('Réservé au propriétaire.')
    if contrat.statut != Contrat.Statut.BROUILLON:
        return redirect('contrats_ui:detail', pk=contrat.id)

    biens_qs = Bien.objects.filter(proprietaire=contrat.proprietaire).order_by('titre')
    locataires_qs = Utilisateur.objects.filter(id=contrat.locataire_id) if contrat.locataire_id else Utilisateur.objects.none()

    if request.method == 'POST':
        form = ContratCreationForm(request.POST, instance=contrat)
        form.fields['bien'].queryset = biens_qs
        form.fields['locataire'].queryset = locataires_qs
        form.fields['locataire'].disabled = True
        if form.is_valid():
            contrat = form.save(commit=False)
            contrat.statut = Contrat.Statut.EN_ATTENTE_SIGNATURE
            contrat.date_envoi_signature = timezone.now()
            contrat.texte_contrat_signe = contrat.texte_articles_actuel
            contrat.save()
            _notifier_contrat_a_signer(contrat)
            messages.success(request, "Contrat envoyé au locataire pour signature.")
            return redirect('contrats_ui:detail', pk=contrat.id)
    else:
        form = ContratCreationForm(instance=contrat)
        form.fields['bien'].queryset = biens_qs
        form.fields['locataire'].queryset = locataires_qs
        form.fields['locataire'].disabled = True

    ctx = _sidebar_context(user)
    ctx.update({'form': form, 'contrat': contrat, 'completer': True, 'has_biens': True, 'has_locataires': True})
    return render(request, 'dashboard/contrat_nouveau.html', ctx)


@login_required
def contrat_signer(request):
    """Le locataire signe électroniquement (clic-à-clic) un contrat qui lui a
    été envoyé — le contrat ne passe EN_COURS qu'à ce moment précis."""
    from django.http import Http404, HttpResponseForbidden
    from django.contrib import messages
    from dashboard.services import NotificationService

    contrat = Contrat.objects.select_related('bien', 'proprietaire').filter(id=request.POST.get('contrat_id')).first()
    if not contrat:
        raise Http404('Contrat non trouvé')
    if request.user != contrat.locataire:
        return HttpResponseForbidden('Réservé au locataire concerné.')

    if request.method == 'POST' and contrat.statut == Contrat.Statut.EN_ATTENTE_SIGNATURE:
        contrat.statut = Contrat.Statut.EN_COURS
        contrat.date_signature = timezone.now()
        contrat.save()
        messages.success(request, "Contrat signé — bienvenue !")
        NotificationService.send(
            destinataire=contrat.proprietaire, expediteur=request.user,
            type_notification='contrat',
            titre=f"Contrat signé — {contrat.bien.titre}",
            message=f"{request.user.get_full_name() or request.user.username} a signé le contrat {contrat.numero_contrat}.",
            lien=f'/contrats/{contrat.id}/',
        )

    return redirect('contrats_ui:detail', pk=contrat.id)


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


def _build_mise_en_demeure_pdf(mise, buffer):
    """Écrit la lettre de mise en demeure en PDF dans `buffer`."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=25*mm, bottomMargin=25*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Titre', parent=styles['Title'], fontSize=16, textColor=colors.HexColor('#B4441F'))
    meta_style = ParagraphStyle('Meta', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#6b7280'), spaceAfter=4)
    body_style = ParagraphStyle('Corps', parent=styles['Normal'], fontSize=11, leading=16, spaceAfter=10)

    contrat = mise.contrat
    company = getattr(contrat.proprietaire, 'company', None)

    elements = [
        Paragraph(mise.objet, title_style),
        Spacer(1, 4*mm),
        Paragraph(f"Entreprise : {company.name if company else contrat.proprietaire.get_full_name() or contrat.proprietaire.username}", meta_style),
        Paragraph(f"Contrat : {contrat.numero_contrat} — {contrat.bien.titre}", meta_style),
        Paragraph(f"Date d'envoi : {mise.date_creation.strftime('%d/%m/%Y')}", meta_style),
        Spacer(1, 8*mm),
    ]
    for paragraphe in mise.texte_lettre().split('\n\n'):
        elements.append(Paragraph(paragraphe.replace('\n', '<br/>'), body_style))

    doc.build(elements)


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
    elements.append(Spacer(1, 8*mm))

    article_title_style = ParagraphStyle('ArticleTitre', parent=styles['Heading3'], fontSize=11.5, textColor=colors.HexColor('#111827'), spaceBefore=8, spaceAfter=2)
    article_body_style = ParagraphStyle('ArticleTexte', parent=styles['Normal'], fontSize=9.5, textColor=colors.HexColor('#374151'), leading=13)

    texte_articles = contrat.texte_contrat_signe or contrat.texte_articles_actuel
    for bloc in texte_articles.split('\n\n'):
        lignes = bloc.split('\n', 1)
        titre = lignes[0]
        corps = lignes[1] if len(lignes) > 1 else ''
        elements.append(Paragraph(titre, article_title_style))
        if corps:
            elements.append(Paragraph(corps.replace('\n', '<br/>'), article_body_style))

    if contrat.statut == Contrat.Statut.EN_COURS and contrat.date_signature:
        elements.append(Spacer(1, 8*mm))
        elements.append(Paragraph(
            f"Signé électroniquement par {contrat.locataire.get_full_name() or contrat.locataire.username} le {contrat.date_signature.strftime('%d/%m/%Y à %H:%M')}.",
            ParagraphStyle('Signature', parent=styles['Normal'], fontSize=9.5, textColor=colors.HexColor('#15803D'))
        ))

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
