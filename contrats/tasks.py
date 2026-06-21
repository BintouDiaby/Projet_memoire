from celery import shared_task
from django.utils import timezone
from .models import Paiement
import logging

logger = logging.getLogger(__name__)


@shared_task
def mettre_a_jour_statut_paiements():
    """
    Tâche programmée pour mettre à jour le statut des paiements
    Exécution : toutes les 6 heures
    """
    try:
        paiements_retard = Paiement.objects.filter(
            date_paiement__isnull=True,
            statut__in=[
                Paiement.Statut.EN_ATTENTE,
                Paiement.Statut.RETARD_MINEUR,
                Paiement.Statut.RETARD_MAJEUR
            ]
        )
        
        statuts_maj = 0
        for paiement in paiements_retard:
            paiement.mettre_a_jour_statut()
            statuts_maj += 1
        
        logger.info(f"✅ {statuts_maj} paiements mis à jour")
        return {'statuts_maj': statuts_maj}
    
    except Exception as e:
        logger.error(f"❌ Erreur lors de la mise à jour des statuts : {str(e)}")
        raise
