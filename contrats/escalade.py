"""Escalade automatique des retards de paiement.

Applique le barème défini sur chaque contrat (jours_avant_rappel,
jours_avant_frais, montant_frais_retard, jours_avant_mise_en_demeure — voir
Contrat.generer_articles / Article 10) : rappel, frais, puis une
recommandation de mise en demeure. L'application ne décide jamais d'engager
une procédure — au-delà de la mise en demeure recommandée, c'est toujours le
propriétaire qui rédige et envoie la lettre (voir
contrats/views.py::envoyer_mise_en_demeure), et qui choisit la suite une
fois le délai expiré.

Idempotent : chaque étape est tracée par un champ horodaté sur `Paiement`
(ou l'existence d'une `MiseEnDemeure`) pour ne jamais se redéclencher.
"""
from django.utils import timezone

SEUIL_CAS_GRAVE_JOURS = 45


def _nom(utilisateur, defaut='ce locataire'):
    if not utilisateur:
        return defaut
    return utilisateur.get_full_name() or utilisateur.username


def _fcfa(montant):
    return f"{montant:,.0f}".replace(',', ' ') + " FCFA"


def verifier_escalade_retard(paiement):
    """Vérifie un paiement en retard et applique l'étape d'escalade due, le
    cas échéant. Ne fait rien si le paiement est réglé ou pas encore en
    retard. Sans effet de bord si aucune étape n'est due (sûr à appeler
    régulièrement, ex. dans la tâche périodique déjà existante)."""
    from dashboard.services import NotificationService
    from facturation.models import Facture

    if paiement.date_paiement or not paiement.date_limite:
        return

    today = timezone.now().date()
    jours_retard = (today - paiement.date_limite).days
    if jours_retard <= 0:
        return

    contrat = paiement.contrat
    locataire = contrat.locataire
    proprietaire = contrat.proprietaire
    bien_titre = contrat.bien.titre
    nom_locataire = _nom(locataire)

    facture_liee = Facture.objects.filter(paiement=paiement).first()
    lien_facture = f'/dashboard/facturation/{facture_liee.id}/' if facture_liee else '/dashboard/facturation/'

    # 1. Rappel de retard (aux deux parties)
    if jours_retard >= contrat.jours_avant_rappel and not paiement.date_rappel_retard_envoye:
        if locataire:
            NotificationService.send(
                destinataire=locataire,
                type_notification='paiement',
                titre=f"Paiement en retard — {bien_titre}",
                message=(
                    f"Votre paiement de {paiement.mois.strftime('%B %Y')} accuse un retard de "
                    f"{jours_retard} jour{'s' if jours_retard > 1 else ''}. Merci de régulariser votre situation."
                ),
                lien=lien_facture,
            )
        NotificationService.send(
            destinataire=proprietaire,
            type_notification='paiement',
            titre=f"Paiement en retard — {bien_titre}",
            message=f"Le paiement de {nom_locataire} pour {paiement.mois.strftime('%B %Y')} accuse un retard de {jours_retard} jour{'s' if jours_retard > 1 else ''}.",
            lien=lien_facture,
        )
        paiement.date_rappel_retard_envoye = timezone.now()
        paiement.save(update_fields=['date_rappel_retard_envoye'])

    # 2. Frais de retard (une seule fois, si le contrat en prévoit)
    if (
        jours_retard >= contrat.jours_avant_frais
        and contrat.montant_frais_retard > 0
        and not paiement.date_frais_appliques
    ):
        paiement.montant_penalites = contrat.montant_frais_retard
        paiement.date_frais_appliques = timezone.now()
        paiement.save(update_fields=['montant_penalites', 'date_frais_appliques'])

        facture = Facture.objects.filter(paiement=paiement).first()
        if facture:
            facture.montant_total = facture.montant_total + contrat.montant_frais_retard
            facture.save(update_fields=['montant_total'])

        montant_total_du = paiement.montant_du + contrat.montant_frais_retard
        if locataire:
            NotificationService.send(
                destinataire=locataire,
                type_notification='paiement',
                titre=f"Frais de retard appliqués — {bien_titre}",
                message=(
                    f"Des frais de retard de {_fcfa(contrat.montant_frais_retard)} ont été appliqués à votre "
                    f"paiement de {paiement.mois.strftime('%B %Y')}. Nouveau montant dû : {_fcfa(montant_total_du)}."
                ),
                lien=lien_facture,
            )
        NotificationService.send(
            destinataire=proprietaire,
            type_notification='paiement',
            titre=f"Frais de retard appliqués — {bien_titre}",
            message=f"Des frais de retard de {_fcfa(contrat.montant_frais_retard)} ont été appliqués au dossier de {nom_locataire}.",
            lien=lien_facture,
        )

    # 3. Mise en demeure recommandée — l'appli informe, le propriétaire rédige et envoie
    if jours_retard >= contrat.jours_avant_mise_en_demeure and not paiement.mises_en_demeure.exists():
        NotificationService.send(
            destinataire=proprietaire,
            type_notification='mise_en_demeure',
            titre=f"Dossier en situation d'impayé — {bien_titre}",
            message=(
                f"Le retard de {nom_locataire} dépasse {contrat.jours_avant_mise_en_demeure} jours. "
                f"Conformément aux clauses du contrat, vous pouvez lui envoyer une mise en demeure depuis la facture."
            ),
            lien=lien_facture,
        )

    # 4. Cas grave (seuil fixe, purement informatif — aucune action automatique)
    if jours_retard >= SEUIL_CAS_GRAVE_JOURS and not paiement.date_alerte_grave_envoyee:
        NotificationService.send(
            destinataire=proprietaire,
            type_notification='paiement',
            titre=f"Retard supérieur à {SEUIL_CAS_GRAVE_JOURS} jours — {bien_titre}",
            message=(
                f"Le dossier de {nom_locataire} accumule plus de {SEUIL_CAS_GRAVE_JOURS} jours de retard. "
                f"Les mesures prévues par le contrat et la législation en vigueur peuvent être engagées."
            ),
            lien=lien_facture,
        )
        if locataire:
            NotificationService.send(
                destinataire=locataire,
                type_notification='paiement',
                titre="Retard important",
                message=(
                    f"Votre retard de paiement dépasse {SEUIL_CAS_GRAVE_JOURS} jours. Veuillez prendre contact "
                    f"avec votre agence. Des mesures prévues par le contrat peuvent être engagées."
                ),
                lien=lien_facture,
            )
        paiement.date_alerte_grave_envoyee = timezone.now()
        paiement.save(update_fields=['date_alerte_grave_envoyee'])


def verifier_expiration_mises_en_demeure():
    """Fait passer au statut EXPIREE toute mise en demeure encore ENVOYEE
    dont le délai de régularisation est dépassé et dont le paiement n'a
    toujours pas été reçu — et prévient le propriétaire. Purement constatatif,
    ne déclenche aucune procédure."""
    from django.utils import timezone as tz
    from dashboard.services import NotificationService
    from .models import MiseEnDemeure
    from facturation.models import Facture

    today = tz.now().date()
    expirees = MiseEnDemeure.objects.filter(
        statut=MiseEnDemeure.Statut.ENVOYEE, date_limite_regularisation__lt=today
    ).select_related('paiement', 'contrat__bien', 'contrat__proprietaire')

    for mise in expirees:
        if mise.paiement.date_paiement:
            mise.statut = MiseEnDemeure.Statut.REGULARISEE
            mise.date_resolution = tz.now()
            mise.save(update_fields=['statut', 'date_resolution'])
            continue

        mise.statut = MiseEnDemeure.Statut.EXPIREE
        mise.date_resolution = tz.now()
        mise.save(update_fields=['statut', 'date_resolution'])

        facture_liee = Facture.objects.filter(paiement=mise.paiement).first()
        NotificationService.send(
            destinataire=mise.contrat.proprietaire,
            type_notification='mise_en_demeure',
            titre=f"Mise en demeure expirée — {mise.contrat.bien.titre}",
            message=(
                f"Le délai accordé à {_nom(mise.contrat.locataire)} pour régulariser sa situation est expiré. "
                f"Vous pouvez accorder un délai supplémentaire, clôturer le dossier, ou préparer le dossier juridique."
            ),
            lien=f'/dashboard/facturation/{facture_liee.id}/' if facture_liee else '/dashboard/facturation/',
        )


# Ordre d'affichage de l'échelle de recouvrement, du moins au plus grave.
ECHELLE_RECOUVREMENT = [
    ('a_jour', '🟢', 'Paiement à jour'),
    ('rappel', '🟡', 'Premier rappel envoyé'),
    ('frais', '🟠', 'Frais de retard appliqués'),
    ('mise_en_demeure', '🔴', 'Mise en demeure envoyée'),
    ('contentieux', '⚫', 'Dossier prêt pour procédure contentieuse'),
]


def echelle_recouvrement(paiement):
    """Étape actuelle du paiement sur l'échelle de recouvrement — visible
    uniquement côté propriétaire (le locataire ne voit que les notifications
    qui le concernent)."""
    if paiement.date_paiement:
        cle = 'a_jour'
    elif paiement.mises_en_demeure.filter(
        statut__in=['envoyee', 'expiree', 'delai_supplementaire', 'procedure']
    ).exists():
        derniere = paiement.mises_en_demeure.order_by('-date_creation').first()
        cle = 'contentieux' if derniere and derniere.statut == 'procedure' else 'mise_en_demeure'
    elif paiement.date_frais_appliques:
        cle = 'frais'
    elif paiement.date_rappel_retard_envoye:
        cle = 'rappel'
    else:
        cle = 'a_jour'
    return next((e for e in ECHELLE_RECOUVREMENT if e[0] == cle), ECHELLE_RECOUVREMENT[0])
