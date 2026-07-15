from celery import shared_task
from django.utils import timezone
from .models import Paiement
from .escalade import verifier_escalade_retard, verifier_expiration_mises_en_demeure
import logging

logger = logging.getLogger(__name__)


@shared_task
def mettre_a_jour_statut_paiements():
    """
    Tâche programmée pour mettre à jour le statut des paiements, puis
    appliquer l'escalade de retard due (rappel/frais/mise en demeure
    recommandée/alerte grave — voir contrats.escalade), et faire expirer les
    mises en demeure dont le délai est dépassé.
    Exécution : toutes les 6 heures
    """
    try:
        paiements_retard = Paiement.objects.filter(
            date_paiement__isnull=True,
            statut__in=[
                Paiement.Statut.EN_ATTENTE,
                Paiement.Statut.RETARD_MINEUR,
                Paiement.Statut.RETARD_MAJEUR,
                Paiement.Statut.IMPAYE,
            ]
        ).select_related('contrat')

        statuts_maj = 0
        for paiement in paiements_retard:
            paiement.mettre_a_jour_statut()
            statuts_maj += 1
            try:
                verifier_escalade_retard(paiement)
            except Exception as e:
                logger.error(f"❌ Erreur escalade retard paiement {paiement.id} : {str(e)}")

        try:
            verifier_expiration_mises_en_demeure()
        except Exception as e:
            logger.error(f"❌ Erreur expiration mises en demeure : {str(e)}")

        logger.info(f"✅ {statuts_maj} paiements mis à jour")
        return {'statuts_maj': statuts_maj}

    except Exception as e:
        logger.error(f"❌ Erreur lors de la mise à jour des statuts : {str(e)}")
        raise
