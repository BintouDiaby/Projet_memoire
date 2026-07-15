"""Outils que l'assistant IA peut appeler, strictement scopés à
`request.user` — jamais de requête non filtrée sur les modèles métier.
Deux jeux de outils : `TOOLS_LOCATAIRE` (chercher un logement, comprendre
une facture...) et `TOOLS_ENTREPRISE` (retrouver un client, un contrat,
les paiements en retard, les RDV du jour, un devis...)."""
from django.utils import timezone
from django.utils.formats import date_format


def _fcfa(montant):
    return f"{montant:,.0f}".replace(',', ' ') + " FCFA"


# ─── Outils côté locataire ───────────────────────────────────────────────────

def _biens_qs(budget_max=None, ville=None, chambres=None, type_bien=None):
    from biens.models import Bien

    qs = Bien.objects.filter(statut=Bien.Statut.DISPONIBLE)
    if budget_max:
        qs = qs.filter(prix_mensuel__lte=budget_max)
    if ville:
        qs = qs.filter(ville__icontains=ville)
    if chambres:
        qs = qs.filter(nombre_chambres__gte=chambres)
    if type_bien:
        qs = qs.filter(type_bien=type_bien)
    return qs.order_by('prix_mensuel')[:8]


def chercher_biens_data(user, budget_max=None, ville=None, chambres=None, type_bien=None):
    """Version « données brutes » de chercher_biens, pour le parcours guidé
    (menu à boutons) qui affiche des cartes sans passer par le LLM."""
    qs = _biens_qs(budget_max, ville, chambres, type_bien)
    return [
        {
            'id': b.id,
            'titre': b.titre,
            'type_bien': b.get_type_bien_display(),
            'prix_mensuel': float(b.prix_mensuel),
            'ville': b.ville,
            'commune': b.commune,
            'chambres': b.nombre_chambres,
            'photo': b.photo_principale.url if b.photo_principale else '',
            'url': f'/biens/{b.id}/',
        }
        for b in qs
    ]


def chercher_biens(user, budget_max=None, ville=None, chambres=None, type_bien=None):
    qs = _biens_qs(budget_max, ville, chambres, type_bien)

    if not qs:
        return "Aucun bien disponible ne correspond à ces critères."
    lignes = []
    for b in qs:
        lignes.append(
            f"- {b.titre} — {b.get_type_bien_display()} — {_fcfa(b.prix_mensuel)}/mois — "
            f"{b.ville}{', ' + b.commune if b.commune else ''} — {b.nombre_chambres} chambre(s) — /biens/{b.id}/"
        )
    return "\n".join(lignes)


def expliquer_facture(user, numero_facture):
    from facturation.models import Facture

    facture = Facture.objects.filter(
        numero_facture=numero_facture, contrat__locataire=user
    ).select_related('contrat__bien', 'paiement').first()
    if not facture:
        return "Aucune facture avec ce numéro n'a été trouvée sur votre compte."

    p = facture.paiement
    return (
        f"Facture {facture.numero_facture} — {facture.contrat.bien.titre}\n"
        f"Montant total : {_fcfa(facture.montant_total)}\n"
        f"Statut : {facture.get_statut_display()}\n"
        f"Échéance : {facture.date_echéance.strftime('%d/%m/%Y')}\n"
        f"Retard éventuel : {p.get_statut_display() if p else 'N/A'}"
    )


def mon_prochain_paiement(user):
    from contrats.models import Contrat, Paiement

    contrats = Contrat.objects.filter(locataire=user, statut=Contrat.Statut.EN_COURS)
    if not contrats:
        return "Vous n'avez aucun contrat de location en cours."

    today = timezone.now().date()
    lignes = []
    for c in contrats:
        p = Paiement.objects.filter(
            contrat=c, mois__lte=today.replace(day=1)
        ).exclude(statut=Paiement.Statut.RECU).order_by('mois').first()
        if p:
            lignes.append(
                f"- {c.bien.titre} : {_fcfa(p.montant_du)} dû pour {date_format(p.mois, 'F Y')}, échéance le {p.date_limite.strftime('%d/%m/%Y')}, statut {p.get_statut_display()}"
            )
    if not lignes:
        return "Tous vos paiements sont à jour."
    return "\n".join(lignes)


_MOTS_VIDES = {
    'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'et', 'ou', 'est', 'sont',
    'je', 'tu', 'il', 'elle', 'on', 'nous', 'vous', 'ils', 'elles', 'ce', 'cette',
    'que', 'qui', 'quoi', 'comment', 'pourquoi', 'pour', 'avec', 'dans', 'sur',
    'mon', 'ma', 'mes', 'votre', 'vos', 'a', 'au', 'aux', 'se', 'sa', 'son',
}


def chercher_aide(user, mot_cle):
    """Recherche dans la FAQ par recouvrement de mots — pas d'IA, purement
    des données de l'application. Tolère une phrase complète (pas seulement
    un mot-clé isolé) en comptant les mots significatifs en commun."""
    from immobilier_config.faq_data import FAQ_CATEGORIES
    import re

    mots_requete = {m for m in re.findall(r'\w+', mot_cle.lower()) if len(m) > 2 and m not in _MOTS_VIDES}
    if not mots_requete:
        return "Reformulez votre question avec quelques mots-clés (ex : « paiement », « visite », « contrat »)."

    scores = []
    for cat in FAQ_CATEGORIES:
        for q, a in cat['questions']:
            mots_texte = set(re.findall(r'\w+', (q + ' ' + a).lower()))
            score = len(mots_requete & mots_texte)
            if score:
                scores.append((score, q, a))

    if not scores:
        return (
            "Aucune réponse trouvée dans le centre d'aide pour cette question. "
            "Contactez votre propriétaire ou l'entreprise concernée via la messagerie, "
            "ou consultez le centre d'aide complet sur /aide/."
        )
    scores.sort(key=lambda t: t[0], reverse=True)
    return "\n\n".join(f"Q: {q}\nR: {a}" for _, q, a in scores[:3])


TOOLS_LOCATAIRE = [
    {
        'name': 'chercher_biens',
        'description': "Cherche des biens à louer disponibles selon un budget, une ville, un nombre de chambres minimum et/ou un type de bien.",
        'input_schema': {
            'type': 'object',
            'properties': {
                'budget_max': {'type': 'number', 'description': 'Budget maximum en FCFA par mois'},
                'ville': {'type': 'string', 'description': 'Ville recherchée'},
                'chambres': {'type': 'integer', 'description': 'Nombre de chambres minimum'},
                'type_bien': {'type': 'string', 'description': "Type de bien (ex: villa, appartement, studio, terrain...)"},
            },
        },
    },
    {
        'name': 'expliquer_facture',
        'description': "Donne le détail d'une facture du locataire connecté à partir de son numéro.",
        'input_schema': {
            'type': 'object',
            'properties': {'numero_facture': {'type': 'string', 'description': 'Numéro de la facture, ex: FAC-6-202606'}},
            'required': ['numero_facture'],
        },
    },
    {
        'name': 'mon_prochain_paiement',
        'description': "Indique le prochain paiement dû du locataire connecté, pour chacun de ses contrats actifs.",
        'input_schema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'chercher_aide',
        'description': "Cherche une réponse dans le centre d'aide (FAQ) de la plateforme à partir d'un mot-clé.",
        'input_schema': {
            'type': 'object',
            'properties': {'mot_cle': {'type': 'string', 'description': 'Mot-clé ou sujet de la question'}},
            'required': ['mot_cle'],
        },
    },
]


# ─── Outils côté entreprise (propriétaire / gestionnaire) ───────────────────

def chercher_client(user, nom):
    from contrats.models import Contrat

    company = getattr(user, 'company', None)
    if not company:
        return "Aucune entreprise associée à ce compte."

    contrats = Contrat.objects.filter(
        proprietaire__company=company, locataire__isnull=False
    ).filter(
        locataire__first_name__icontains=nom
    ).select_related('locataire', 'bien').distinct()[:5]
    if not contrats:
        contrats = Contrat.objects.filter(
            proprietaire__company=company, locataire__isnull=False, locataire__username__icontains=nom
        ).select_related('locataire', 'bien').distinct()[:5]
    if not contrats:
        return f"Aucun client nommé « {nom} » trouvé parmi vos contrats."

    lignes = []
    for c in contrats:
        lignes.append(
            f"- {c.locataire.get_full_name() or c.locataire.username} — contrat {c.numero_contrat} — "
            f"{c.bien.titre} — statut {c.get_statut_display()}"
        )
    return "\n".join(lignes)


def chercher_contrat(user, recherche):
    from contrats.models import Contrat
    from django.db.models import Q

    company = getattr(user, 'company', None)
    if not company:
        return "Aucune entreprise associée à ce compte."

    contrats = Contrat.objects.filter(proprietaire__company=company).filter(
        Q(numero_contrat__icontains=recherche) | Q(bien__titre__icontains=recherche)
        | Q(locataire__first_name__icontains=recherche) | Q(locataire__username__icontains=recherche)
    ).select_related('locataire', 'bien')[:5]
    if not contrats:
        return f"Aucun contrat correspondant à « {recherche} »."

    lignes = []
    for c in contrats:
        lignes.append(
            f"- {c.numero_contrat} — {c.bien.titre} — locataire "
            f"{c.locataire.get_full_name() if c.locataire else '—'} — statut {c.get_statut_display()} — "
            f"{_fcfa(c.prix_mensuel)}/mois"
        )
    return "\n".join(lignes)


def paiements_en_retard(user, jours_min=1):
    from contrats.models import Contrat, Paiement

    company = getattr(user, 'company', None)
    if not company:
        return "Aucune entreprise associée à ce compte."

    today = timezone.now().date()
    paiements = Paiement.objects.filter(
        contrat__proprietaire__company=company,
        statut__in=[Paiement.Statut.RETARD_MINEUR, Paiement.Statut.RETARD_MAJEUR, Paiement.Statut.IMPAYE],
    ).select_related('contrat__bien', 'contrat__locataire')

    lignes = []
    for p in paiements:
        jours = (today - p.date_limite).days
        if jours >= (jours_min or 1):
            nom = p.contrat.locataire.get_full_name() if p.contrat.locataire else '—'
            lignes.append(f"- {nom} — {p.contrat.bien.titre} — {_fcfa(p.montant_du)} — {jours} jours de retard")
    if not lignes:
        return f"Aucun paiement en retard de plus de {jours_min or 1} jour(s)."
    return "\n".join(sorted(lignes, key=lambda l: l, reverse=False)[:15])


def rdv_du_jour(user):
    from biens.models import Visite
    from construction.models import ProjetConstruction
    from facturation.models import RendezVousPaiement

    company = getattr(user, 'company', None)
    if not company:
        return "Aucune entreprise associée à ce compte."

    today = timezone.now().date()
    lignes = []

    for v in Visite.objects.filter(bien__proprietaire__company=company, date_visite__date=today).select_related('locataire', 'bien'):
        lignes.append(f"- Visite {v.date_visite.strftime('%H:%M')} : {v.locataire.get_full_name() or v.locataire.username} — {v.bien.titre}")

    for p in ProjetConstruction.objects.filter(entreprise=company, date_rdv__date=today).select_related('client'):
        lignes.append(f"- RDV construction {p.date_rdv.strftime('%H:%M')} : {p.client.get_full_name() or p.client.username} — {p.get_type_projet_display()}")

    for r in RendezVousPaiement.objects.filter(facture__contrat__proprietaire__company=company, date_confirmee__date=today).select_related('locataire'):
        lignes.append(f"- RDV paiement {r.date_confirmee.strftime('%H:%M')} : {r.locataire.get_full_name() or r.locataire.username}")

    if not lignes:
        return "Aucun rendez-vous programmé aujourd'hui."
    return "\n".join(sorted(lignes))


def chercher_devis(user, recherche=''):
    from construction.models import Devis
    from django.db.models import Q

    company = getattr(user, 'company', None)
    if not company:
        return "Aucune entreprise associée à ce compte."

    qs = Devis.objects.filter(projet__entreprise=company).select_related('projet__client')
    if recherche:
        qs = qs.filter(Q(projet__client__first_name__icontains=recherche) | Q(projet__client__username__icontains=recherche))
    qs = qs.order_by('-date_creation')[:8]
    if not qs:
        return "Aucun devis trouvé."

    lignes = []
    for d in qs:
        lignes.append(
            f"- {d.projet.client.get_full_name() or d.projet.client.username} — {_fcfa(d.montant)} — "
            f"statut {d.get_statut_display()} — émis le {d.date_creation.strftime('%d/%m/%Y')}"
        )
    return "\n".join(lignes)


TOOLS_ENTREPRISE = [
    {
        'name': 'chercher_client',
        'description': "Cherche un client (locataire) par nom parmi les contrats de l'entreprise connectée.",
        'input_schema': {
            'type': 'object',
            'properties': {'nom': {'type': 'string', 'description': 'Nom ou prénom du client'}},
            'required': ['nom'],
        },
    },
    {
        'name': 'chercher_contrat',
        'description': "Cherche un contrat par numéro, nom du bien ou nom du client.",
        'input_schema': {
            'type': 'object',
            'properties': {'recherche': {'type': 'string', 'description': 'Numéro de contrat, nom du bien ou du client'}},
            'required': ['recherche'],
        },
    },
    {
        'name': 'paiements_en_retard',
        'description': "Liste les paiements en retard de l'entreprise, filtrés par un nombre minimum de jours de retard.",
        'input_schema': {
            'type': 'object',
            'properties': {'jours_min': {'type': 'integer', 'description': 'Nombre minimum de jours de retard (défaut 1)'}},
        },
    },
    {
        'name': 'rdv_du_jour',
        'description': "Liste tous les rendez-vous du jour de l'entreprise : visites de biens, RDV construction, RDV de paiement en espèces.",
        'input_schema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'chercher_devis',
        'description': "Cherche les devis construction de l'entreprise, éventuellement filtrés par nom de client.",
        'input_schema': {
            'type': 'object',
            'properties': {'recherche': {'type': 'string', 'description': 'Nom du client (facultatif)'}},
        },
    },
]


TOOL_FUNCTIONS = {
    'chercher_biens': chercher_biens,
    'expliquer_facture': expliquer_facture,
    'mon_prochain_paiement': mon_prochain_paiement,
    'chercher_aide': chercher_aide,
    'chercher_client': chercher_client,
    'chercher_contrat': chercher_contrat,
    'paiements_en_retard': paiements_en_retard,
    'rdv_du_jour': rdv_du_jour,
    'chercher_devis': chercher_devis,
}


def executer_outil(nom, entree, user):
    fn = TOOL_FUNCTIONS.get(nom)
    if not fn:
        return f"Outil inconnu : {nom}"
    try:
        return fn(user, **entree)
    except Exception as e:
        return f"Erreur lors de l'exécution de l'outil : {e}"
