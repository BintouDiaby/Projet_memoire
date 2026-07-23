from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from .models import ProfilConstruction, RealisationConstruction, ProjetConstruction, EtapeChantier, PhotoChantier, NotificationConstruction, Devis
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


# ─── Premier contact : le client se dit intéressé, avant tout devis ─────────
# Un devis détaillé ne peut plus être demandé directement — le client doit
# d'abord obtenir un rendez-vous avec l'entreprise, et que celle-ci le
# marque comme terminé (voir terminer_rdv), avant que demande_devis ne
# s'ouvre pour ce projet.

@login_required
def demander_contact_construction(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    if 'construction' not in (company.types or []):
        from django.http import Http404
        raise Http404('Cette entreprise ne propose pas de service de construction')

    if request.method != 'POST':
        return redirect('construction:profil_entreprise', company_id=company.id)

    projet = ProjetConstruction.objects.create(client=request.user, entreprise=company)
    projet.creer_etapes_par_defaut()

    contact = _get_contact_user(company)
    if contact:
        conv, _ = Conversation.objects.get_or_create(
            projet=projet,
            demandeur=request.user,
            defaults={'proprietaire': contact, 'phase': Conversation.Phase.COMMERCIAL}
        )
        intro = (
            f"Bonjour, je suis intéressé(e) par vos services de construction. "
            f"Pouvez-vous me proposer un rendez-vous pour en discuter ?"
        )
        Message.objects.create(conversation=conv, expediteur=request.user, contenu=intro)
        conv.mis_a_jour_le = timezone.now()
        conv.save(update_fields=['mis_a_jour_le'])
        NotificationConstruction.objects.create(
            destinataire=contact,
            projet=projet,
            type=NotificationConstruction.Type.NOUVEAU_DEVIS,
            message=f"{request.user.get_full_name() or request.user.username} est intéressé(e) "
                    f"et souhaite un rendez-vous avant de vous soumettre son projet.",
        )

    messages.success(request, "Votre demande de contact a été envoyée — l'entreprise va vous proposer un rendez-vous.")
    return redirect('construction:projet_detail', projet_id=projet.id)


# ─── Formulaire de demande de devis (débloqué après le RDV) ────────────────

@login_required
def demande_devis(request, projet_id):
    projet = get_object_or_404(ProjetConstruction, id=projet_id)
    if request.user != projet.client:
        return HttpResponseForbidden('Réservé au client de ce projet.')
    if not projet.rdv_termine:
        messages.error(request, "Le rendez-vous doit d'abord avoir lieu avant de pouvoir demander un devis détaillé.")
        return redirect('construction:projet_detail', projet_id=projet.id)

    company = projet.entreprise
    terrain_lie = projet.terrain_lie
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
                'projet': projet, 'company': company, 'profil': getattr(company, 'profil_construction', None),
                'terrain_lie': terrain_lie, 'erreur': 'Veuillez remplir tous les champs obligatoires.',
                'post': request.POST,
            })

        projet.type_projet = type_projet
        projet.superficie = superficie
        projet.a_terrain = a_terrain
        projet.localisation_terrain = localisation
        projet.budget_estime = budget
        projet.description = description
        projet.terrain_lie = terrain_lie
        projet.save()

        contact = _get_contact_user(company)
        if contact:
            conv, _ = Conversation.objects.get_or_create(
                projet=projet,
                demandeur=request.user,
                defaults={'proprietaire': contact, 'phase': Conversation.Phase.COMMERCIAL}
            )
            intro = (
                f"Suite à notre rendez-vous, voici ma demande de devis pour un(e) "
                f"{projet.get_type_projet_display()}"
                f"{f' à {localisation}' if localisation else ''}.\n\n"
                f"{description}"
            )
            Message.objects.create(conversation=conv, expediteur=request.user, contenu=intro)
            conv.mis_a_jour_le = timezone.now()
            conv.save(update_fields=['mis_a_jour_le'])
            NotificationConstruction.objects.create(
                destinataire=contact,
                projet=projet,
                type=NotificationConstruction.Type.NOUVEAU_DEVIS,
                message=f"Demande de devis détaillée reçue de {request.user.get_full_name() or request.user.username} "
                        f"pour un(e) {projet.get_type_projet_display()}"
                        f"{f' à {localisation}' if localisation else ''}.",
            )

        return redirect('construction:projet_detail', projet_id=projet.id)

    return render(request, 'construction/demande_devis.html', {
        'projet': projet,
        'company': company,
        'profil': getattr(company, 'profil_construction', None),
        'terrain_lie': terrain_lie,
        'types': ProjetConstruction.TypeProjet.choices,
    })


# ─── L'entreprise marque le rendez-vous comme terminé ───────────────────────

@login_required
def terminer_rdv(request, projet_id):
    """Débloque le formulaire de devis détaillé pour le client une fois le
    rendez-vous effectivement passé. Le client doit d'abord avoir confirmé
    le rendez-vous — une entreprise ne peut pas le clore unilatéralement
    avant que le client ne l'ait accepté."""
    projet = get_object_or_404(ProjetConstruction, id=projet_id)
    contact = _get_contact_user(projet.entreprise)
    est_entreprise = (contact and request.user == contact) or request.user.is_staff
    if not est_entreprise:
        return HttpResponseForbidden('Réservé à l\'entreprise.')

    if request.method == 'POST' and projet.rdv_confirme and not projet.rdv_termine:
        projet.rdv_termine = True
        projet.save(update_fields=['rdv_termine'])
        _notifier(
            projet.client, projet, NotificationConstruction.Type.RDV_TERMINE,
            "Le rendez-vous est terminé — vous pouvez maintenant nous soumettre votre demande de devis détaillée."
        )

    return redirect('construction:projet_detail', projet_id=projet.id)


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

    devis_historique = list(projet.devis.all())
    devis_actuel = devis_historique[0] if devis_historique else None
    peut_preparer_devis = est_entreprise and (devis_actuel is None or devis_actuel.statut in (Devis.Statut.REFUSE, Devis.Statut.EXPIRE))
    peut_repondre_devis = est_client and devis_actuel is not None and devis_actuel.statut == Devis.Statut.ENVOYE

    return render(request, 'construction/projet_detail.html', {
        'projet': projet,
        'etapes': etapes,
        'photos': photos,
        'conv': conv,
        'est_entreprise': est_entreprise,
        'est_client': est_client,
        'devis_historique': devis_historique,
        'devis_actuel': devis_actuel,
        'peut_preparer_devis': peut_preparer_devis,
        'peut_repondre_devis': peut_repondre_devis,
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
    for n in notifs:
        n.mark_url = f"/dashboard/notifications/construction/lire/{n.id}/?next=/construction/projet/{n.projet_id}/"

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


# ─── Profil construction (description, spécialités/services, réalisations) ──

@login_required
def gerer_profil(request):
    """Page entreprise pour éditer le profil construction (description,
    spécialités) et gérer les réalisations affichées publiquement."""
    user = request.user
    company = getattr(user, 'company', None)
    if not company or 'construction' not in (company.types or []):
        return HttpResponseForbidden('Votre entreprise ne propose pas de service de construction')

    profil, _ = ProfilConstruction.objects.get_or_create(company=company)

    if request.method == 'POST' and request.POST.get('action') == 'profil':
        profil.description = request.POST.get('description', '').strip()
        annee = request.POST.get('annee_creation', '').strip()
        profil.annee_creation = int(annee) if annee.isdigit() else None
        specialites_raw = request.POST.get('specialites', '')
        profil.specialites = [s.strip() for s in specialites_raw.split(',') if s.strip()]
        profil.adresse = request.POST.get('adresse', '').strip()
        profil.telephone = request.POST.get('telephone', '').strip()
        profil.site_web = request.POST.get('site_web', '').strip()
        profil.save()
        return redirect('construction:gerer_profil')

    realisations = company.realisations.all()
    return render(request, 'construction/gerer_profil.html', {
        'company': company,
        'profil': profil,
        'realisations': realisations,
        'types': ProjetConstruction.TypeProjet.choices,
    })


@login_required
def realisation_ajouter(request):
    user = request.user
    company = getattr(user, 'company', None)
    if not company or 'construction' not in (company.types or []):
        return HttpResponseForbidden()

    if request.method == 'POST':
        titre = request.POST.get('titre', '').strip()
        if titre:
            annee = request.POST.get('annee', '').strip()
            RealisationConstruction.objects.create(
                company=company,
                titre=titre,
                description=request.POST.get('description', '').strip(),
                photo=request.FILES.get('photo'),
                annee=int(annee) if annee.isdigit() else None,
                localisation=request.POST.get('localisation', '').strip(),
                type_projet=request.POST.get('type_projet', '').strip(),
                ordre=company.realisations.count(),
            )

    return redirect('construction:gerer_profil')


@login_required
def realisation_modifier(request, realisation_id):
    user = request.user
    company = getattr(user, 'company', None)
    realisation = get_object_or_404(RealisationConstruction, id=realisation_id, company=company)

    if request.method == 'POST':
        titre = request.POST.get('titre', '').strip()
        if titre:
            realisation.titre = titre
            realisation.description = request.POST.get('description', '').strip()
            if request.FILES.get('photo'):
                realisation.photo = request.FILES.get('photo')
            annee = request.POST.get('annee', '').strip()
            realisation.annee = int(annee) if annee.isdigit() else None
            realisation.localisation = request.POST.get('localisation', '').strip()
            realisation.type_projet = request.POST.get('type_projet', '').strip()
            realisation.save()

    return redirect('construction:gerer_profil')


@login_required
def realisation_supprimer(request, realisation_id):
    user = request.user
    company = getattr(user, 'company', None)
    realisation = get_object_or_404(RealisationConstruction, id=realisation_id, company=company)
    if request.method == 'POST':
        realisation.delete()
    return redirect('construction:gerer_profil')


# ─── Devis ───────────────────────────────────────────────────────────────────

@login_required
def devis_preparer(request, projet_id):
    """L'entreprise chiffre et envoie un devis au client."""
    projet = get_object_or_404(ProjetConstruction, id=projet_id)
    user = request.user
    contact = _get_contact_user(projet.entreprise)
    est_entreprise = (contact and user == contact) or user.is_staff
    if not est_entreprise:
        return HttpResponseForbidden()

    devis_en_cours = projet.devis.filter(statut=Devis.Statut.ENVOYE).exists()
    if devis_en_cours:
        return redirect('construction:projet_detail', projet_id=projet.id)

    if request.method == 'POST':
        montant = request.POST.get('montant', '').strip()
        detail = request.POST.get('detail', '').strip()
        try:
            validite_jours = int(request.POST.get('validite_jours', '30') or 30)
        except ValueError:
            validite_jours = 30

        if not montant or not detail:
            return redirect('construction:projet_detail', projet_id=projet.id)

        devis = Devis.objects.create(
            projet=projet, montant=montant, detail=detail,
            validite_jours=validite_jours, cree_par=user,
        )
        projet.statut = ProjetConstruction.Statut.DEVIS_ENVOYE
        projet.save(update_fields=['statut'])

        from django.contrib.humanize.templatetags.humanize import intcomma
        _notifier(
            projet.client, projet, NotificationConstruction.Type.NOUVEAU_DEVIS,
            f"Un devis de {intcomma(int(devis.montant))} FCFA vous a été envoyé pour votre projet "
            f"{projet.get_type_projet_display()}. Valable {validite_jours} jours."
        )

    return redirect('construction:projet_detail', projet_id=projet.id)


@login_required
def devis_repondre(request, devis_id):
    """Le client accepte ou refuse le devis reçu."""
    devis = get_object_or_404(Devis, id=devis_id)
    projet = devis.projet
    user = request.user
    if user != projet.client:
        return HttpResponseForbidden()

    if request.method == 'POST' and devis.statut == Devis.Statut.ENVOYE:
        action = request.POST.get('action')
        contact = _get_contact_user(projet.entreprise)

        if action == 'accepter':
            devis.statut = Devis.Statut.ACCEPTE
            devis.date_reponse = timezone.now()
            devis.save(update_fields=['statut', 'date_reponse'])
            projet.devis.filter(statut=Devis.Statut.ENVOYE).exclude(id=devis.id).update(statut=Devis.Statut.EXPIRE)
            projet.statut = ProjetConstruction.Statut.ACCEPTE
            projet.save(update_fields=['statut'])
            _notifier(
                contact, projet, NotificationConstruction.Type.STATUT_CHANGE,
                f"{user.get_full_name() or user.username} a accepté le devis."
            )
        elif action == 'refuser':
            devis.statut = Devis.Statut.REFUSE
            devis.motif_refus = request.POST.get('motif_refus', '').strip()
            devis.date_reponse = timezone.now()
            devis.save(update_fields=['statut', 'motif_refus', 'date_reponse'])
            projet.statut = ProjetConstruction.Statut.EN_ATTENTE
            projet.save(update_fields=['statut'])
            msg = f"{user.get_full_name() or user.username} a refusé le devis."
            if devis.motif_refus:
                msg += f" Motif : {devis.motif_refus}"
            _notifier(contact, projet, NotificationConstruction.Type.STATUT_CHANGE, msg)

    return redirect('construction:projet_detail', projet_id=projet.id)


@login_required
def devis_pdf(request, devis_id):
    """Télécharge le devis en PDF."""
    from django.http import HttpResponse
    import io

    devis = Devis.objects.select_related('projet__client', 'projet__entreprise').filter(id=devis_id).first()
    if not devis:
        from django.http import Http404
        raise Http404('Devis non trouvé')
    projet = devis.projet
    contact = _get_contact_user(projet.entreprise)
    if request.user not in (projet.client, contact) and not request.user.is_staff:
        return HttpResponseForbidden('Accès refusé')

    buffer = io.BytesIO()
    _build_devis_pdf(devis, buffer)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="devis-projet-{projet.id}.pdf"'
    return response


def _build_devis_pdf(devis, buffer):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=25*mm, bottomMargin=25*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Titre', parent=styles['Title'], fontSize=16, textColor=colors.HexColor('#185FA5'))
    meta_style = ParagraphStyle('Meta', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#6b7280'), spaceAfter=4)
    body_style = ParagraphStyle('Corps', parent=styles['Normal'], fontSize=11, leading=16, spaceAfter=10)
    montant_style = ParagraphStyle('Montant', parent=styles['Title'], fontSize=20, textColor=colors.HexColor('#3B6D11'))

    projet = devis.projet
    company = projet.entreprise

    elements = [
        Paragraph(f"Devis — {projet.get_type_projet_display()}", title_style),
        Spacer(1, 4*mm),
        Paragraph(f"Entreprise : {company.name}", meta_style),
        Paragraph(f"Client : {projet.client.get_full_name() or projet.client.username}", meta_style),
        Paragraph(f"Date d'émission : {devis.date_creation.strftime('%d/%m/%Y')}", meta_style),
        Paragraph(f"Valable jusqu'au : {devis.date_limite_validite.strftime('%d/%m/%Y')}", meta_style),
        Spacer(1, 8*mm),
        Paragraph(f"{int(devis.montant):,}".replace(',', ' ') + " FCFA", montant_style),
        Spacer(1, 8*mm),
        Paragraph("Détail des prestations", styles['Heading3']),
    ]
    for paragraphe in devis.detail.split('\n\n'):
        elements.append(Paragraph(paragraphe.replace('\n', '<br/>'), body_style))

    doc.build(elements)


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
