from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import MessageAssistant
from .tools import executer_outil, chercher_biens_data, chercher_aide, chercher_entreprises_data

# Actions du menu guidé — appellent directement les fonctions de tools.py,
# sans passer par le LLM (rapide, fiable, « données réelles uniquement »).
# Le nom d'action exposé au client ne correspond pas forcément 1:1 au nom de
# l'outil interne, pour ne pas exposer la surface complète des outils LLM.
ACTIONS_LOCATAIRE = {
    'paiement': ('mon_prochain_paiement', {}),
    'aide_contrat': ('chercher_aide', {'mot_cle': 'contrat'}),
    'aide_construction': ('chercher_aide', {'mot_cle': 'construction'}),
}
ACTIONS_ENTREPRISE = {
    'retard': ('paiements_en_retard', {'jours_min': 1}),
    'rdv': ('rdv_du_jour', {}),
    'devis': ('chercher_devis', {}),
}


@login_required
def historique(request):
    msgs = MessageAssistant.objects.filter(utilisateur=request.user).order_by('date_creation')[:50]
    return JsonResponse({
        'messages': [{'role': m.role, 'contenu': m.contenu} for m in msgs],
    })


@login_required
def chat(request):
    """Question libre : recherche dans le centre d'aide par mots-clés —
    aucune IA externe, uniquement les données de l'application."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode invalide'}, status=405)

    contenu = (request.POST.get('message') or '').strip()
    if not contenu:
        return JsonResponse({'error': 'Message vide'}, status=400)

    MessageAssistant.objects.create(utilisateur=request.user, role=MessageAssistant.Role.USER, contenu=contenu)

    reponse = chercher_aide(request.user, contenu)

    MessageAssistant.objects.create(utilisateur=request.user, role=MessageAssistant.Role.ASSISTANT, contenu=reponse)

    return JsonResponse({'reponse': reponse})


@login_required
def vider(request):
    """Supprime l'historique de conversation de l'utilisateur — appelé à la
    fermeture du widget pour repartir de zéro à la prochaine ouverture."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode invalide'}, status=405)
    MessageAssistant.objects.filter(utilisateur=request.user).delete()
    return JsonResponse({'ok': True})


@login_required
def action(request):
    """Menu guidé à boutons : appelle directement une fonction de tools.py
    (données de l'application, aucun appel au LLM)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode invalide'}, status=405)

    from utilisateurs.models import Utilisateur
    est_entreprise = request.user.role in (Utilisateur.Role.PROPRIETAIRE, Utilisateur.Role.GESTIONNAIRE)
    actions = ACTIONS_ENTREPRISE if est_entreprise else ACTIONS_LOCATAIRE

    cle = request.POST.get('action')
    if cle not in actions:
        return JsonResponse({'error': 'Action inconnue'}, status=400)

    nom_outil, args_fixes = actions[cle]
    resultat = executer_outil(nom_outil, args_fixes, request.user)
    return JsonResponse({'texte': resultat})


@login_required
def recherche_logement(request):
    """Étape finale du parcours guidé « Trouver un logement » : renvoie une
    liste structurée (pas de texte généré) pour affichage en cartes."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode invalide'}, status=405)

    ville = (request.POST.get('ville') or '').strip()
    budget_str = (request.POST.get('budget') or '').strip()
    try:
        budget_max = float(budget_str) if budget_str else None
    except ValueError:
        budget_max = None

    biens = chercher_biens_data(request.user, budget_max=budget_max, ville=ville or None)
    return JsonResponse({'biens': biens})


@login_required
def recherche_client(request):
    """Étape finale du parcours guidé côté entreprise « Rechercher un client »."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode invalide'}, status=405)

    nom = (request.POST.get('nom') or '').strip()
    if not nom:
        return JsonResponse({'error': 'Nom manquant'}, status=400)

    resultat = executer_outil('chercher_client', {'nom': nom}, request.user)
    return JsonResponse({'texte': resultat})


@login_required
def recherche_entreprise(request):
    """Étape finale du parcours guidé « Contacter une entreprise » (locataire) :
    renvoie une liste d'entreprises correspondant au nom saisi, chacune avec
    un lien direct pour démarrer une vraie conversation (pas juste ouvrir
    l'annuaire dans un nouvel onglet)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode invalide'}, status=405)

    nom = (request.POST.get('nom') or '').strip()
    if not nom:
        return JsonResponse({'error': 'Nom manquant'}, status=400)

    entreprises = chercher_entreprises_data(request.user, nom)
    return JsonResponse({'entreprises': entreprises})
