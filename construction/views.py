from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from .models import ProfilConstruction, RealisationConstruction, ProjetConstruction, EtapeChantier, PhotoChantier, NotificationConstruction
from utilisateurs.models import Company, Utilisateur
from messagerie.models import Conversation, Message


def _get_contact_user(company):
    """Retourne le premier utilisateur proprietaire associé à la company."""
    return company.users.filter(role=Utilisateur.Role.PROPRIETAIRE).first() or company.users.first()


def _notifier(destinataire, projet, type_notif, message):
    """Crée une notification construction et envoie un message dans la conversation."""
    if not destinataire:
        return
    NotificationConstruction.objects.create(
        destinataire=destinataire,
        projet=projet,
        type=type_notif,
        message=message,
    )
    conv = Conversation.objects.filter(projet=projet, demandeur=projet.client).first()
    if conv:
        expediteur = projet.client if destinataire != projet.client else _get_contact_user(projet.entreprise)
        if expediteur:
            Message.objects.create(conversation=conv, expediteur=expediteur, contenu=message)
            conv.mis_a_jour_le = timezone.now()
            conv.save(update_fields=['mis_a_jour_le'])


# ─── Page publique : liste des entreprises de construction ───────────────────

def liste_entreprises(request):
    data = []
    for c in Company.objects.prefetch_related('realisations').order_by('name'):
        if 'construction' in (c.types or []):
            profil = getattr(c, 'profil_construction', None)
            data.append({'company': c, 'profil': profil})
    return render(request, 'construction/liste.html', {'entreprises': data})


# ─── Profil d'une entreprise de construction ────────────────────────────────

def profil_entreprise(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    if 'construction' not in (company.types or []):
        from django.http import Http404
        raise Http404('Cette entreprise ne propose pas de service de construction')
    profil = getattr(company, 'profil_construction', None)
    realisations = company.realisations.all()[:12]

    conversation_existante = None
    if request.user.is_authenticated:
        conversation_existante = (
            Conversation.objects.filter(projet__entreprise=company, demandeur=request.user)
            .order_by('-mis_a_jour_le').first()
        )

    return render(request, 'construction/profil_entreprise.html', {
        'company': company,
        'profil': profil,
        'realisations': realisations,
        'conversation_existante': conversation_existante,
    })


# ─── Formulaire de demande de devis ─────────────────────────────────────────

@login_required
def demande_devis(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    terrain_lie = None
    terrain_id = request.GET.get('terrain')
    if terrain_id:
        from biens.models import Bien
        terrain_lie = Bien.objects.filter(id=terrain_id, type_bien='terrain').first()

    if request.method == 'POST':
        type_projet = request.POST.get('type_projet', '').strip()
        superficie = request.POST.get('superficie', '').strip() or None
        a_terrain = request.POST.get('a_terrain') == 'oui'
        localisation = request.POST.get('localisation', '').strip()
        budget = request.POST.get('budget', '').strip() or None
        description = request.POST.get('description', '').strip()

        if not type_projet or not description:
            return render(request, 'construction/demande_devis.html', {
                'company': company, 'profil': getattr(company, 'profil_construction', None),
                'terrain_lie': terrain_lie, 'erreur': 'Veuillez remplir tous les champs obligatoires.',
                'post': request.POST,
            })

        projet = ProjetConstruction.objects.create(
            client=request.user,
            entreprise=company,
            type_projet=type_projet,
            superficie=superficie,
            a_terrain=a_terrain,
            localisation_terrain=localisation,
            budget_estime=budget,
            description=description,
            terrain_lie=terrain_lie,
        )
        projet.creer_etapes_par_defaut()

        # Créer la conversation associée
        contact = _get_contact_user(company)
        if contact:
            conv, _ = Conversation.objects.get_or_create(
                projet=projet,
                demandeur=request.user,
                defaults={'proprietaire': contact, 'phase': Conversation.Phase.COMMERCIAL}
            )
            intro = (
                f"Bonjour, je souhaite vous soumettre une demande de devis pour un(e) "
                f"{projet.get_type_projet_display()}"
                f"{f' à {localisation}' if localisation else ''}.\n\n"
                f"{description}"
            )
            Message.objects.create(conversation=conv, expediteur=request.user, contenu=intro)
            conv.mis_a_jour_le = timezone.now()
            conv.save(update_fields=['mis_a_jour_le'])
            # Notification pour l'entreprise
            NotificationConstruction.objects.create(
                destinataire=contact,
                projet=projet,
                type=NotificationConstruction.Type.NOUVEAU_DEVIS,
                message=f"Nouveau devis reçu de {request.user.get_full_name() or request.user.username} "
                        f"pour un(e) {projet.get_type_projet_display()}"
                        f"{f' à {localisation}' if localisation else ''}.",
            )

        return redirect('construction:projet_detail', projet_id=projet.id)

    return render(request, 'construction/demande_devis.html', {
        'company': company,
        'profil': getattr(company, 'profil_construction', None),
        'terrain_lie': terrain_lie,
        'types': ProjetConstruction.TypeProjet.choices,
    })


# ─── Mes projets (client) ────────────────────────────────────────────────────

@login_required
def mes_projets(request):
    projets = (
        ProjetConstruction.objects
        .filter(client=request.user)
        .select_related('entreprise')
        .prefetch_related('etapes')
        .order_by('-cree_le')
    )
    return render(request, 'construction/mes_projets.html', {'projets': projets})


# ─── Détail d'un projet (client + entreprise) ───────────────────────────────

@login_required
def projet_detail(request, projet_id):
    projet = get_object_or_404(ProjetConstruction, id=projet_id)
    user = request.user
    contact = _get_contact_user(projet.entreprise)
    est_entreprise = (contact and user == contact) or user.is_staff
    est_client = user == projet.client

    if not est_entreprise and not est_client:
        return HttpResponseForbidden('Accès refusé')

    # Conversation associée
    conv = Conversation.objects.filter(projet=projet, demandeur=projet.client).first()

    etapes = projet.etapes.all()
    photos = projet.photos_chantier.select_related('ajoute_par', 'etape').all()

    return render(request, 'construction/projet_detail.html', {
        'projet': projet,
        'etapes': etapes,
        'photos': photos,
        'conv': conv,
        'est_entreprise': est_entreprise,
        'est_client': est_client,
    })


# ─── Dashboard construction (côté entreprise) ───────────────────────────────

@login_required
def dashboard_construction(request):
    user = request.user
    company = getattr(user, 'company', None)
    if not company or 'construction' not in (company.types or []):
        return HttpResponseForbidden('Votre entreprise ne propose pas de service de construction')

    projets = (
        ProjetConstruction.objects
        .filter(entreprise=company)
        .select_related('client')
        .prefetch_related('etapes')
        .order_by('-cree_le')
    )
    nb_en_attente = projets.filter(statut=ProjetConstruction.Statut.EN_ATTENTE).count()
    nb_en_cours   = projets.filter(statut=ProjetConstruction.Statut.EN_COURS).count()
    nb_termines   = projets.filter(statut=ProjetConstruction.Statut.TERMINE).count()

    # Notifications non lues
    notifs = (
        NotificationConstruction.objects
        .filter(destinataire=user, lue=False)
        .select_related('projet', 'projet__client')
        .order_by('-cree_le')[:15]
    )
    nb_notifs = NotificationConstruction.objects.filter(destinataire=user, lue=False).count()

    # RDV à venir (projets avec date_rdv dans le futur)
    from django.utils.timezone import now
    rdv_a_venir = (
        projets
        .filter(date_rdv__gte=now())
        .order_by('date_rdv')[:10]
    )

    return render(request, 'construction/dashboard.html', {
        'projets': projets,
        'company': company,
        'profil': getattr(company, 'profil_construction', None),
        'nb_en_attente': nb_en_attente,
        'nb_en_cours': nb_en_cours,
        'nb_termines': nb_termines,
        'notifs': notifs,
        'nb_notifs': nb_notifs,
        'rdv_a_venir': rdv_a_venir,
    })


@login_required
def marquer_notifs_lues(request):
    if request.method == 'POST':
        NotificationConstruction.objects.filter(destinataire=request.user, lue=False).update(lue=True)
    return redirect(request.POST.get('next', '/construction/dashboard/'))


@login_required
def gerer_rdv(request, projet_id):
    """Propose ou modifie la date de RDV d'un projet (entreprise ET client)."""
    projet = get_object_or_404(ProjetConstruction, id=projet_id)
    user = request.user
    contact = _get_contact_user(projet.entreprise)
    est_entreprise = (contact and user == contact) or user.is_staff
    est_client = user == projet.client

    if not est_entreprise and not est_client:
        return HttpResponseForbidden()

    if request.method == 'POST':
        date_str = request.POST.get('date_rdv', '').strip()
        notes    = request.POST.get('notes_rdv', '').strip()

        from datetime import datetime
        try:
            from django.utils import timezone as tz
            dt = datetime.fromisoformat(date_str)
            if dt.tzinfo is None:
                import zoneinfo
                try:
                    dt = dt.replace(tzinfo=zoneinfo.ZoneInfo('Africa/Abidjan'))
                except Exception:
                    dt = tz.make_aware(dt)
            projet.date_rdv = dt
        except (ValueError, TypeError):
            projet.date_rdv = None

        projet.notes_rdv = notes
        projet.rdv_confirme = False
        projet.save(update_fields=['date_rdv', 'notes_rdv', 'rdv_confirme'])

        if projet.date_rdv:
            date_fmt = projet.date_rdv.strftime('%d/%m/%Y à %H:%M')
            if est_entreprise:
                msg = f"RDV proposé le {date_fmt}. {notes}"
                destinataire = projet.client
                type_notif = NotificationConstruction.Type.RDV_PROPOSE
            else:
                msg = f"Le client souhaite modifier le RDV : {date_fmt}. {notes}"
                destinataire = contact
                type_notif = NotificationConstruction.Type.RDV_MODIFIE

            _notifier(destinataire, projet, type_notif, msg.strip())

        return redirect('construction:projet_detail', projet_id=projet.id)

    return redirect('construction:projet_detail', projet_id=projet.id)


@login_required
def confirmer_rdv(request, projet_id):
    """Le client accepte formellement la date de RDV proposée."""
    projet = get_object_or_404(ProjetConstruction, id=projet_id)
    user = request.user
    est_client = user == projet.client

    if not est_client:
        return HttpResponseForbidden()

    if request.method == 'POST' and projet.date_rdv and not projet.rdv_confirme:
        projet.rdv_confirme = True
        projet.save(update_fields=['rdv_confirme'])

        contact = _get_contact_user(projet.entreprise)
        date_fmt = projet.date_rdv.strftime('%d/%m/%Y à %H:%M')
        _notifier(
            contact, projet, NotificationConstruction.Type.RDV_CONFIRME,
            f"Le client a confirmé le rendez-vous du {date_fmt}."
        )

    return redirect('construction:projet_detail', projet_id=projet.id)


@login_required
def annuler_rdv(request, projet_id):
    """Annule le rendez-vous programmé (entreprise OU client)."""
    projet = get_object_or_404(ProjetConstruction, id=projet_id)
    user = request.user
    contact = _get_contact_user(projet.entreprise)
    est_entreprise = (contact and user == contact) or user.is_staff
    est_client = user == projet.client

    if not est_entreprise and not est_client:
        return HttpResponseForbidden()

    if request.method == 'POST' and projet.date_rdv:
        date_fmt = projet.date_rdv.strftime('%d/%m/%Y à %H:%M')
        projet.date_rdv = None
        projet.notes_rdv = ''
        projet.rdv_confirme = False
        projet.save(update_fields=['date_rdv', 'notes_rdv', 'rdv_confirme'])

        if est_entreprise:
            destinataire = projet.client
            message = f"Le rendez-vous du {date_fmt} a été annulé par l'entreprise."
        else:
            destinataire = contact
            message = f"Le rendez-vous du {date_fmt} a été annulé par le client."

        _notifier(destinataire, projet, NotificationConstruction.Type.RDV_ANNULE, message)

    return redirect('construction:projet_detail', projet_id=projet.id)


# ─── Mettre à jour le statut d'une étape ────────────────────────────────────

@login_required
def mettre_a_jour_etape(request, etape_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Methode invalide'}, status=405)
    etape = get_object_or_404(EtapeChantier, id=etape_id)
    projet = etape.projet
    user = request.user
    contact = _get_contact_user(projet.entreprise)
    if not (user == contact or user.is_staff):
        return JsonResponse({'error': 'Acces refuse'}, status=403)

    nouveau_statut = request.POST.get('statut', '')
    statuts_valides = [s[0] for s in EtapeChantier.StatutEtape.choices]
    if nouveau_statut not in statuts_valides:
        return JsonResponse({'error': 'Statut invalide'}, status=400)

    etape.statut = nouveau_statut
    if nouveau_statut == EtapeChantier.StatutEtape.TERMINE:
        from django.utils.timezone import now
        etape.date_reelle = now().date()
    etape.save()
    projet.recalculer_avancement()

    # Notifier le client via la conversation
    conv = Conversation.objects.filter(projet=projet, demandeur=projet.client).first()
    if conv:
        label = dict(EtapeChantier.StatutEtape.choices).get(nouveau_statut, nouveau_statut)
        Message.objects.create(
            conversation=conv,
            expediteur=user,
            contenu=f"Mise a jour chantier : l'etape \"{etape.nom}\" est maintenant \"{label}\". Avancement global : {projet.pourcentage_avancement}%."
        )
        conv.mis_a_jour_le = timezone.now()
        conv.save(update_fields=['mis_a_jour_le'])

    next_url = request.POST.get('next') or f'/construction/projet/{projet.id}/'
    return redirect(next_url)


# ─── Changer le statut global du projet ─────────────────────────────────────

@login_required
def changer_statut_projet(request, projet_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Methode invalide'}, status=405)
    projet = get_object_or_404(ProjetConstruction, id=projet_id)
    user = request.user
    contact = _get_contact_user(projet.entreprise)
    est_entreprise = (contact and user == contact) or user.is_staff
    est_client = user == projet.client
    if not est_entreprise and not est_client:
        return HttpResponseForbidden()

    nouveau_statut = request.POST.get('statut', '')
    statuts_valides = [s[0] for s in ProjetConstruction.Statut.choices]
    if nouveau_statut not in statuts_valides:
        return redirect(f'/construction/projet/{projet_id}/')

    projet.statut = nouveau_statut
    projet.save(update_fields=['statut'])

    conv = Conversation.objects.filter(projet=projet, demandeur=projet.client).first()
    if conv:
        label = dict(ProjetConstruction.Statut.choices).get(nouveau_statut, nouveau_statut)
        Message.objects.create(
            conversation=conv,
            expediteur=user,
            contenu=f"Le statut du projet a ete mis a jour : {label}."
        )
        conv.mis_a_jour_le = timezone.now()
        conv.save(update_fields=['mis_a_jour_le'])

    return redirect(f'/construction/projet/{projet_id}/')
