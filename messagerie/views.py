from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Q
from .models import Conversation, Message
from biens.models import Bien, Visite
from contrats.models import Contrat, Paiement
from dashboard.services import NotificationService


def _est_participant(conv, user):
    return user == conv.demandeur or user == conv.proprietaire or user.is_staff


def _est_proprietaire_bien(conv, user):
    return user == conv.proprietaire or user.is_staff


def _conversations_sidebar(user, exclude_conv_id=None):
    """Liste des conversations de l'utilisateur (tous rôles confondus), pour le
    volet gauche de la messagerie. Réutilisé par `mes_conversations` et
    `conversation_detail` pour ne pas dupliquer le calcul."""
    convs = (
        Conversation.objects
        .filter(Q(demandeur=user) | Q(proprietaire=user))
        .select_related('bien', 'demandeur', 'proprietaire')
        .order_by('-mis_a_jour_le')
    )
    data = []
    for conv in convs:
        dernier = conv.messages.order_by('-cree_le').first()
        nb_non_lus = conv.messages.filter(lu=False).exclude(expediteur=user).count()
        interlocuteur = conv.proprietaire if user == conv.demandeur else conv.demandeur
        nom_affiche = getattr(getattr(interlocuteur, 'company', None), 'name', None) or interlocuteur.get_full_name() or interlocuteur.username
        if conv.bien:
            sujet_lieu = conv.bien.titre
            categorie = 'ventes' if conv.bien.transaction_type in ('vente',) else 'locations' if conv.bien.transaction_type in ('location', 'both') else None
        elif conv.projet:
            sujet_lieu = f"Projet {conv.projet.get_type_projet_display()}"
            categorie = None
        else:
            sujet_lieu = ''
            categorie = None
        data.append({
            'conv': conv,
            'dernier': dernier,
            'nb_non_lus': nb_non_lus,
            'interlocuteur': interlocuteur,
            'nom_affiche': nom_affiche,
            'sujet_lieu': sujet_lieu,
            'categorie': categorie,
            'verifie': bool(interlocuteur.documents_verifies),
            'avatar_class': f'b{(conv.id % 4) + 1}',
        })
    return data


@login_required
def nouvelle_conversation(request, bien_id):
    bien = get_object_or_404(Bien, id=bien_id)
    user = request.user
    if user == bien.proprietaire:
        return redirect('biens_ui:detail', pk=bien_id)
    conv, _ = Conversation.objects.get_or_create(
        bien=bien,
        demandeur=user,
        defaults={'proprietaire': bien.proprietaire},
    )
    return redirect('messagerie:conversation', conv_id=conv.id)


@login_required
def conversation_detail(request, conv_id):
    conv = get_object_or_404(Conversation, id=conv_id)
    user = request.user
    if not _est_participant(conv, user):
        return HttpResponseForbidden('Accès refusé')

    if request.method == 'POST':
        contenu = request.POST.get('contenu', '').strip()
        if contenu:
            msg = Message.objects.create(conversation=conv, expediteur=user, contenu=contenu)
            conv.mis_a_jour_le = timezone.now()
            conv.save(update_fields=['mis_a_jour_le'])
            destinataire = conv.proprietaire if user == conv.demandeur else conv.demandeur
            NotificationService.send(
                destinataire=destinataire,
                expediteur=user,
                type_notification='message',
                titre=f"Nouveau message de {user.get_full_name() or user.username}",
                message=contenu[:120],
                lien=f'/chat/{conv.id}/',
            )
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'ok': True,
                    'id': msg.id,
                    'contenu': msg.contenu,
                    'heure': msg.cree_le.strftime('%H:%M'),
                })
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': False})
        return redirect('messagerie:conversation', conv_id=conv_id)

    conv.messages.filter(lu=False).exclude(expediteur=user).update(lu=True)
    messages_list = conv.messages.select_related('expediteur').all()
    interlocuteur = conv.proprietaire if user == conv.demandeur else conv.demandeur

    # Visites liées (seulement si conversation de type bien)
    visites = []
    if conv.bien:
        visites = list(Visite.objects.filter(
            bien=conv.bien, locataire=conv.demandeur
        ).order_by('-date_visite'))

    sujet = conv.sujet

    return render(request, 'messagerie/conversation.html', {
        'conv': conv,
        'sujet': sujet,
        'bien': conv.bien,
        'projet': conv.projet,
        'messages': messages_list,
        'interlocuteur': interlocuteur,
        'visites': visites,
        'est_proprietaire': _est_proprietaire_bien(conv, user),
        'conversations_sidebar': _conversations_sidebar(user),
        'avatar_class': f'b{(conv.id % 4) + 1}',
        'phase_choices': Conversation.Phase.choices,
    })


@login_required
def api_nouveaux_messages(request, conv_id):
    conv = get_object_or_404(Conversation, id=conv_id)
    user = request.user
    if not _est_participant(conv, user):
        return JsonResponse({'error': 'Accès refusé'}, status=403)

    since_str = request.GET.get('since', '')
    try:
        from datetime import datetime
        since = datetime.fromisoformat(since_str.replace('Z', '+00:00'))
        qs = conv.messages.filter(cree_le__gt=since).select_related('expediteur')
    except (ValueError, TypeError):
        qs = conv.messages.none()

    conv.messages.filter(lu=False).exclude(expediteur=user).update(lu=True)

    data = [{
        'id': m.id,
        'nom': m.expediteur.get_full_name() or m.expediteur.username,
        'moi': m.expediteur_id == user.id,
        'contenu': m.contenu,
        'heure': m.cree_le.strftime('%H:%M'),
        'iso': m.cree_le.isoformat(),
    } for m in qs]

    return JsonResponse({'messages': data})


@login_required
def mes_conversations(request):
    convs_data = _conversations_sidebar(request.user)
    nb_non_lus_total = sum(1 for item in convs_data if item['nb_non_lus'])
    return render(request, 'messagerie/mes_conversations.html', {
        'convs_data': convs_data,
        'nb_non_lus_total': nb_non_lus_total,
    })


@login_required
def changer_phase(request, conv_id):
    """Permet au propriétaire de changer la phase d'une conversation."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    conv = get_object_or_404(Conversation, id=conv_id)
    if not _est_proprietaire_bien(conv, request.user):
        return JsonResponse({'error': 'Accès refusé'}, status=403)
    phase = request.POST.get('phase', '')
    phases_valides = [p[0] for p in Conversation.Phase.choices]
    if phase not in phases_valides:
        return JsonResponse({'error': 'Phase invalide'}, status=400)
    conv.phase = phase
    conv.save(update_fields=['phase'])
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'phase': phase, 'label': conv.get_phase_display()})
    return redirect('messagerie:conversation', conv_id=conv_id)


@login_required
def gerer_visite(request, visite_id):
    """Permet au propriétaire de confirmer ou refuser une visite."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    visite = get_object_or_404(Visite, id=visite_id)
    user = request.user
    if user != visite.bien.proprietaire and not user.is_staff:
        return JsonResponse({'error': 'Accès refusé'}, status=403)
    action = request.POST.get('action', '')
    if action == 'confirmer':
        visite.statut = Visite.Statut.CONFIRMEE
        visite.save(update_fields=['statut'])
        # Envoyer un message dans la conversation si elle existe
        conv = Conversation.objects.filter(bien=visite.bien, demandeur=visite.locataire).first()
        if conv:
            Message.objects.create(
                conversation=conv,
                expediteur=user,
                contenu=f"Votre visite du {visite.date_visite.strftime('%d/%m/%Y à %H:%M')} est confirmée. À bientôt !"
            )
            conv.mis_a_jour_le = timezone.now()
            conv.save(update_fields=['mis_a_jour_le'])
        NotificationService.send(
            destinataire=visite.locataire,
            expediteur=user,
            type_notification='visite',
            titre="Visite confirmée",
            message=f"{visite.bien.titre} — {visite.date_visite.strftime('%d/%m/%Y à %H:%M')}",
            lien=f'/biens/{visite.bien_id}/',
        )
    elif action == 'refuser':
        visite.statut = Visite.Statut.REFUSEE
        visite.save(update_fields=['statut'])
        conv = Conversation.objects.filter(bien=visite.bien, demandeur=visite.locataire).first()
        if conv:
            Message.objects.create(
                conversation=conv,
                expediteur=user,
                contenu=f"Nous ne pouvons pas confirmer la visite du {visite.date_visite.strftime('%d/%m/%Y')}. N'hésitez pas à proposer une autre date."
            )
            conv.mis_a_jour_le = timezone.now()
            conv.save(update_fields=['mis_a_jour_le'])
        NotificationService.send(
            destinataire=visite.locataire,
            expediteur=user,
            type_notification='visite',
            titre="Visite non confirmée",
            message=f"{visite.bien.titre} — {visite.date_visite.strftime('%d/%m/%Y')}",
            lien=f'/biens/{visite.bien_id}/',
        )
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/chat/'
    return redirect(next_url)


@login_required
def fiche_client(request, user_id, conv_id):
    """Fiche client visible par le propriétaire depuis une conversation."""
    from utilisateurs.models import Utilisateur
    conv = get_object_or_404(Conversation, id=conv_id)
    if not _est_proprietaire_bien(conv, request.user):
        return HttpResponseForbidden('Accès refusé')
    client = get_object_or_404(Utilisateur, id=user_id)
    # Contrats du client sur les biens du proprietaire
    contrats = (
        Contrat.objects
        .filter(locataire=client, proprietaire=conv.proprietaire)
        .select_related('bien')
        .order_by('-date_debut')
    )
    # Visites du client
    visites = (
        Visite.objects
        .filter(locataire=client, bien__proprietaire=conv.proprietaire)
        .select_related('bien')
        .order_by('-date_visite')[:10]
    )
    # Toutes les conversations de ce client avec ce proprietaire
    autres_convs = (
        Conversation.objects
        .filter(demandeur=client, proprietaire=conv.proprietaire)
        .select_related('bien')
        .order_by('-mis_a_jour_le')
    )
    return render(request, 'messagerie/fiche_client.html', {
        'client': client,
        'conv': conv,
        'contrats': contrats,
        'visites': visites,
        'autres_convs': autres_convs,
    })


@login_required
def dashboard_messages(request):
    """Vue Messages complète pour le propriétaire / gestionnaire dans le dashboard."""
    from utilisateurs.models import Utilisateur
    user = request.user
    if user.role not in (Utilisateur.Role.PROPRIETAIRE, Utilisateur.Role.GESTIONNAIRE) and not user.is_staff:
        return HttpResponseForbidden('Réservé aux entreprises')

    convs = (
        Conversation.objects
        .filter(proprietaire=user)
        .select_related('bien', 'demandeur', 'proprietaire')
        .order_by('-mis_a_jour_le')
    )
    convs_data = []
    for conv in convs:
        dernier = conv.messages.order_by('-cree_le').first()
        nb_non_lus = conv.messages.filter(lu=False).exclude(expediteur=user).count()
        convs_data.append({
            'conv': conv,
            'dernier': dernier,
            'nb_non_lus': nb_non_lus,
            'interlocuteur': conv.demandeur,
        })

    # Visites en attente de confirmation
    visites_en_attente = (
        Visite.objects
        .filter(bien__proprietaire=user, statut=Visite.Statut.EN_ATTENTE)
        .select_related('bien', 'locataire')
        .order_by('date_visite')
    )

    return render(request, 'messagerie/dashboard_messages.html', {
        'convs_data': convs_data,
        'visites_en_attente': visites_en_attente,
        'nb_non_lus_total': sum(c['nb_non_lus'] for c in convs_data),
    })
