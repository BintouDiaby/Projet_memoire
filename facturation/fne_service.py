"""Intégration avec la plateforme Facture Normalisée Électronique (FNE) de la
Direction Générale des Impôts de Côte d'Ivoire.

Référence : guide officiel « PROCEDURE D'INTERFACAGE DES ENTREPRISES PAR API »
(DGI, mai 2025), https://www.fne.dgi.gouv.ci/.

Ceci implémente l'API #1 (certification de facture de vente) telle que
documentée. Avant toute certification réelle, l'entreprise doit :
  1. S'inscrire sur la plateforme FNE (environnement de test) ;
  2. Développer/valider l'intégration en sandbox ;
  3. Transmettre des spécimens de factures à support.fne@dgi.gouv.ci ;
  4. Recevoir de la DGI l'URL de production et la clé API (visible dans
     l'espace FNE de l'entreprise, onglet « Paramétrage »).

Tant que FNE_API_KEY n'est pas renseignée dans .env, la certification est
simplement ignorée (la facture reste valable en interne, non certifiée) —
aucune tentative d'appel réseau n'est faite.
"""
import requests
from django.conf import settings
from django.utils import timezone


# paymentMethod attendu par l'API FNE : cash | card | check | mobile-money | transfer | deferred
MODE_PAIEMENT_VERS_FNE = {
    'wave': 'mobile-money',
    'orange_money': 'mobile-money',
    'mtn': 'mobile-money',
    'carte': 'card',
    'especes': 'cash',
    'virement': 'transfer',
}


class FneError(Exception):
    """Erreur de certification FNE (requête invalide, auth, ou service indisponible)."""


def _entreprise_de(facture):
    """Company du propriétaire du contrat (None si le propriétaire n'a pas d'entreprise)."""
    return getattr(facture.contrat.proprietaire, 'company', None)


def _est_configuree():
    return bool(settings.FNE_API_KEY) and bool(settings.FNE_API_URL)


def construire_payload(facture):
    """Construit le corps JSON attendu par POST {url}/external/invoices/sign,
    à partir des données réelles du contrat/de la facture. Ne fabrique aucune
    donnée : lève FneError si une information obligatoire manque (NCC vendeur,
    coordonnées client)."""
    contrat = facture.contrat
    locataire = contrat.locataire
    entreprise = _entreprise_de(facture)

    if not entreprise or not entreprise.numero_ncc:
        raise FneError(
            "Le NCC (Numéro de Compte Contribuable) de l'entreprise n'est pas renseigné "
            "— impossible de certifier la facture auprès de la DGI. "
            "À renseigner dans les paramètres entreprise."
        )
    if not locataire or not locataire.telephone or not locataire.email:
        raise FneError(
            "Téléphone et email du locataire sont obligatoires pour la certification FNE."
        )

    mode_paiement_fne = MODE_PAIEMENT_VERS_FNE.get(facture.mode_paiement, 'deferred')
    taux_tva = entreprise.taux_tva_loyer or 'TVAD'

    items = [{
        'taxes': [taux_tva],
        'reference': f'LOYER-{contrat.id}',
        'description': f"Loyer {facture.paiement.mois.strftime('%B %Y')} — {contrat.bien.titre}",
        'quantity': 1,
        'amount': float(facture.montant_loyer),
        'measurementUnit': 'mois',
    }]
    if facture.montant_charges:
        items.append({
            'taxes': [taux_tva],
            'reference': f'CHARGES-{contrat.id}',
            'description': f"Charges {facture.paiement.mois.strftime('%B %Y')}",
            'quantity': 1,
            'amount': float(facture.montant_charges),
            'measurementUnit': 'mois',
        })

    return {
        'invoiceType': 'sale',
        'paymentMethod': mode_paiement_fne,
        'template': 'B2C',
        'isRne': False,
        'clientCompanyName': locataire.get_full_name() or locataire.username,
        'clientPhone': locataire.telephone,
        'clientEmail': locataire.email,
        'pointOfSale': entreprise.name,
        'establishment': entreprise.name,
        'commercialMessage': '',
        'footer': f"NCC {entreprise.numero_ncc} — RCCM {entreprise.numero_rccm}".strip(' —'),
        'items': items,
    }


def certifier_facture(facture):
    """Envoie la facture à la plateforme FNE pour certification et enregistre
    le résultat sur l'objet Facture. Retourne (succes: bool, message: str).
    N'appelle jamais le réseau si FNE_API_KEY n'est pas configurée."""
    if not _est_configuree():
        return False, "FNE non configurée (FNE_API_KEY manquante dans .env) — facture non certifiée."

    try:
        payload = construire_payload(facture)
    except FneError as e:
        facture.fne_erreur = str(e)
        facture.save(update_fields=['fne_erreur'])
        return False, str(e)

    try:
        resp = requests.post(
            f"{settings.FNE_API_URL}/external/invoices/sign",
            json=payload,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': f'Bearer {settings.FNE_API_KEY}',
            },
            timeout=15,
        )
    except requests.RequestException as e:
        facture.fne_erreur = f"Service FNE injoignable : {e}"
        facture.save(update_fields=['fne_erreur'])
        return False, facture.fne_erreur

    if resp.status_code not in (200, 201):
        try:
            detail = resp.json().get('message', resp.text)
        except ValueError:
            detail = resp.text
        facture.fne_erreur = f"Erreur DGI ({resp.status_code}) : {detail}"
        facture.save(update_fields=['fne_erreur'])
        return False, facture.fne_erreur

    data = resp.json()
    facture.fne_certifiee = True
    facture.fne_reference = data.get('reference', '')
    facture.fne_token = data.get('token', '')
    facture.fne_certifiee_le = timezone.now()
    facture.fne_erreur = ''
    facture.save(update_fields=['fne_certifiee', 'fne_reference', 'fne_token', 'fne_certifiee_le', 'fne_erreur'])
    return True, "Facture certifiée FNE."
