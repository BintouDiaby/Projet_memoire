from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Count
from .models import StatistiquesProprietaire, RapportMensuel
from utilisateurs.models import Utilisateur
from biens.models import Bien
from contrats.models import Contrat, Paiement
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def mettre_a_jour_statistiques(self):
    """
    Tâche programmée pour mettre à jour les statistiques des propriétaires
    Exécution : Toutes les heures
    """
    try:
        proprietaires = Utilisateur.objects.filter(role='proprietaire')
        updated = 0
        
        for proprietaire in proprietaires:
            try:
                stats, _ = StatistiquesProprietaire.objects.get_or_create(
                    proprietaire=proprietaire
                )
                stats.mettre_a_jour_statistiques()
                updated += 1
            except Exception as e:
                logger.error(f"Erreur mise à jour stats pour {proprietaire.username}: {str(e)}")
                continue
        
        logger.info(f"Statistiques mises à jour pour {updated} propriétaires")
        return {'status': 'success', 'updated': updated}
        
    except Exception as exc:
        logger.error(f"Erreur: {str(exc)}")
        return self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def generer_rapports_mensuels(self):
    """
    Tâche programmée pour générer les rapports mensuels
    Exécution : 1er du mois à 9h
    """
    try:
        aujourd_hui = timezone.now().date()
        mois = aujourd_hui.replace(day=1)
        
        proprietaires = Utilisateur.objects.filter(role='proprietaire')
        rapports_crees = 0
        
        for proprietaire in proprietaires:
            try:
                rapport, created = RapportMensuel.objects.get_or_create(
                    proprietaire=proprietaire,
                    mois=mois
                )
                
                if created or True:  # Toujours mettre à jour
                    # Compter les propriétés
                    rapport.nombre_proprietes = Bien.objects.filter(
                        proprietaire=proprietaire
                    ).count()
                    
                    # Compter les contrats actifs
                    rapport.nombre_contrats_actifs = Contrat.objects.filter(
                        proprietaire=proprietaire,
                        statut='en_cours',
                        date_debut__lte=aujourd_hui,
                        date_fin__gte=aujourd_hui
                    ).count()
                    
                    # Compter les locataires
                    rapport.nombre_locataires = Contrat.objects.filter(
                        proprietaire=proprietaire,
                        statut='en_cours'
                    ).values('locataire').distinct().count()
                    
                    # Calculs financiers
                    paiements = Paiement.objects.filter(
                        contrat__proprietaire=proprietaire,
                        mois=mois
                    )
                    
                    rapport.revenu_attendu = paiements.aggregate(
                        Sum('montant_du')
                    )['montant_du__sum'] or 0
                    
                    rapport.revenu_recu = paiements.filter(
                        statut='recu'
                    ).aggregate(Sum('montant_recu'))['montant_recu__sum'] or 0
                    
                    rapport.montant_impaye = paiements.filter(
                        statut__in=['impaye', 'retard_majeur']
                    ).aggregate(Sum('montant_du'))['montant_du__sum'] or 0
                    
                    if rapport.revenu_attendu > 0:
                        rapport.taux_collecte = (rapport.revenu_recu / rapport.revenu_attendu) * 100
                    else:
                        rapport.taux_collecte = 0
                    
                    rapport.save()
                    
                    if created:
                        rapports_crees += 1
                        logger.info(f"Rapport créé pour {proprietaire.username} - {mois.strftime('%B %Y')}")
                        
            except Exception as e:
                logger.error(f"Erreur création rapport pour {proprietaire.username}: {str(e)}")
                continue
        
        logger.info(f"Rapports mensuels générés: {rapports_crees}")
        return {'status': 'success', 'rapports_crees': rapports_crees}
        
    except Exception as exc:
        logger.error(f"Erreur: {str(exc)}")
        return self.retry(exc=exc, countdown=60)
