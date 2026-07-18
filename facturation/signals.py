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
        
        mois_courant = instance.date_debut.replace(day=1)
        while mois_courant <= instance.date_fin:
            # Déterminer la date limite de paiement
            if instance.jour_paiement <= mois_courant.replace(day=1).day:
                date_limite = mois_courant.replace(day=instance.jour_paiement)
            else:
                date_limite = mois_courant.replace(day=instance.jour_paiement)
            
            Paiement.objects.get_or_create(
                contrat=instance,
                mois=mois_courant,
                defaults={
                    'montant_du': instance.prix_mensuel + instance.charges_mensuelles,
                    'date_limite': date_limite,
                    'statut': Paiement.Statut.EN_ATTENTE
                }
            )
            
            # Passer au mois suivant
            if mois_courant.month == 12:
                mois_courant = mois_courant.replace(year=mois_courant.year + 1, month=1)
            else:
                mois_courant = mois_courant.replace(month=mois_courant.month + 1)
