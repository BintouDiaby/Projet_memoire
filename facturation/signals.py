from django.db.models.signals import post_save
from django.dispatch import receiver
from contrats.models import Contrat
from .models import Facture, RappelPaiement
from django.utils import timezone
from datetime import timedelta


@receiver(post_save, sender=Contrat)
def creer_paiements_initiaux(sender, instance, created, raw=False, **kwargs):
    """Créer les paiements initiaux quand un contrat est créé.

    `raw=True` pendant un chargement de fixture (`loaddata`) : il ne faut
    surtout pas recréer des paiements ici, sinon ça entre en collision avec
    les vrais `Paiement` déjà présents dans la fixture elle-même (même
    contrat + même mois, contrainte `unique_together` violée) — bug réel
    rencontré lors d'un export/import de la base vers PostgreSQL."""
    if raw:
        return
    if created and instance.statut == Contrat.Statut.EN_COURS:
        from contrats.models import Paiement
        from .tasks import generer_facture_pour_paiement

        premier_jour_du_bail = instance.date_debut.replace(day=1)
        premier_jour_mois_courant = timezone.now().date().replace(day=1)

        mois_courant = premier_jour_du_bail
        while mois_courant <= instance.date_fin:
            date_limite = mois_courant.replace(day=instance.jour_paiement)
            if mois_courant == premier_jour_du_bail and date_limite < instance.date_debut:
                # Le premier mois ne peut pas être déjà "en retard" avant même
                # que le contrat ne commence — le locataire n'a pas encore pu
                # payer (bug réel : jour_paiement déjà passé dans le mois de
                # signature donnait une échéance antérieure à date_debut).
                date_limite = instance.date_debut

            paiement, _ = Paiement.objects.get_or_create(
                contrat=instance,
                mois=mois_courant,
                defaults={
                    'montant_du': instance.prix_mensuel + instance.charges_mensuelles,
                    'date_limite': date_limite,
                    'statut': Paiement.Statut.EN_ATTENTE
                }
            )

            # Si ce mois est déjà le mois calendaire en cours, la tâche
            # mensuelle (1er du mois) est déjà passée et ne repassera plus —
            # sans ça la facture ne serait JAMAIS générée pour ce paiement :
            # "en retard" partout, mais introuvable en Facturation et sans
            # bouton Payer nulle part (bug réel constaté sur un contrat signé
            # en cours de mois).
            if mois_courant == premier_jour_mois_courant:
                generer_facture_pour_paiement(paiement, instance)

            # Passer au mois suivant
            if mois_courant.month == 12:
                mois_courant = mois_courant.replace(year=mois_courant.year + 1, month=1)
            else:
                mois_courant = mois_courant.replace(month=mois_courant.month + 1)
