from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from datetime import timedelta, datetime
from decimal import Decimal
from .models import Facture, Notification, RappelPaiement
from contrats.models import Paiement, Contrat
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generer_factures_mensuelles(self):
    """
    Tâche programmée pour générer les factures du mois en cours
    Exécution : 1er du mois à 1h du matin
    """
    try:
        aujourd_hui = timezone.now().date()
        premier_jour_mois = aujourd_hui.replace(day=1)
        
        # Récupérer tous les contrats actifs
        contrats_actifs = Contrat.objects.filter(
            statut='en_cours',
            date_debut__lte=aujourd_hui,
            date_fin__gte=aujourd_hui
        )
        
        factures_creees = 0
        paiements_crees = 0
        
        for contrat in contrats_actifs:
            try:
                # Créer un paiement pour ce mois
                paiement, created = Paiement.objects.get_or_create(
                    contrat=contrat,
                    mois=premier_jour_mois,
                    defaults={
                        'montant_du': contrat.prix_mensuel + contrat.charges_mensuelles,
                        'date_limite': premier_jour_mois.replace(day=min(contrat.jour_paiement, 28))
                    }
                )
                
                if created:
                    paiements_crees += 1
                
                # Créer une facture pour ce paiement
                if not hasattr(paiement, 'facture'):
                    facture = Facture.objects.create(
                        paiement=paiement,
                        contrat=contrat,
                        numero_facture=f"FAC-{contrat.id}-{premier_jour_mois.strftime('%Y%m')}",
                        date_echéance=paiement.date_limite,
                        montant_loyer=contrat.prix_mensuel,
                        montant_charges=contrat.charges_mensuelles,
                        montant_total=paiement.montant_du,
                        statut=Facture.Statut.GENEREE,
                        date_emission=timezone.now()
                    )
                    factures_creees += 1

                    # Certification FNE (Facture Normalisée Électronique - DGI).
                    # N'interrompt jamais la génération : si la FNE n'est pas encore
                    # configurée ou injoignable, la facture reste valable en interne,
                    # simplement non certifiée (facture.fne_certifiee reste False).
                    try:
                        from .fne_service import certifier_facture
                        ok, msg = certifier_facture(facture)
                        if not ok:
                            logger.warning(f"Certification FNE non aboutie pour {facture.numero_facture} : {msg}")
                    except Exception as e:
                        logger.error(f"Erreur certification FNE pour {facture.numero_facture}: {str(e)}")

                    # Créer une notification pour le locataire
                    if contrat.locataire:
                        Notification.objects.create(
                            facture=facture,
                            utilisateur=contrat.locataire,
                            type_notification='email',
                            titre=f'Facture de loyer pour {contrat.bien.titre}',
                            message=f'Une nouvelle facture a été générée pour le mois de {premier_jour_mois.strftime("%B %Y")}',
                            statut=Notification.Statut.EN_ATTENTE
                        )
                        
                        # Créer les rappels de paiement
                        creer_rappels_paiement(paiement)
                        
            except Exception as e:
                logger.error(f"Erreur lors de la création de la facture pour le contrat {contrat.id}: {str(e)}")
                continue
        
        message = f"Génération des factures mensuelles: {factures_creees} factures, {paiements_crees} paiements"
        logger.info(message)
        return {'status': 'success', 'factures': factures_creees, 'paiements': paiements_crees}
        
    except Exception as exc:
        logger.error(f"Erreur: {str(exc)}")
        return self.retry(exc=exc, countdown=60)


def creer_rappels_paiement(paiement):
    """Créer les rappels de paiement pour un paiement"""
    try:
        date_limite = paiement.date_limite

        # Premier rappel: 2 jours après
        RappelPaiement.objects.get_or_create(
            paiement=paiement,
            type_rappel=RappelPaiement.Type.PREMIER_RAPPEL,
            defaults={'date_programmee': date_limite + timedelta(days=2)}
        )

        # Deuxième rappel: 7 jours après
        RappelPaiement.objects.get_or_create(
            paiement=paiement,
            type_rappel=RappelPaiement.Type.DEUXIEME_RAPPEL,
            defaults={'date_programmee': date_limite + timedelta(days=7)}
        )

        # Avis final: 15 jours après
        RappelPaiement.objects.get_or_create(
            paiement=paiement,
            type_rappel=RappelPaiement.Type.AVIS_FINAL,
            defaults={'date_programmee': date_limite + timedelta(days=15)}
        )

        logger.info(f"Rappels créés pour paiement {paiement.id}")

    except Exception as e:
        logger.error(f"Erreur création rappels: {str(e)}")


@shared_task
def envoyer_facture_par_email(facture_id):
    """
    Envoyer une facture par email au locataire et au propriétaire
    """
    try:
        facture = Facture.objects.get(id=facture_id)
        contrat = facture.contrat
        locataire = contrat.locataire
        proprietaire = contrat.proprietaire
        
        # Préparer le contenu de l'email
        contexte = {
            'numero_facture': facture.numero_facture,
            'montant_total': facture.montant_total,
            'date_echéance': facture.date_echéance,
            'bien': contrat.bien.titre,
            'locataire': locataire.get_full_name() or locataire.username,
        }
        
        sujet = f"Facture {facture.numero_facture} pour {contrat.bien.titre}"
        
        # Envoyer au locataire
        if locataire.email:
            message = render_to_string('email/facture.html', contexte)
            send_mail(sujet, message, 'noreply@immobilier.local', [locataire.email])
            
            # Créer notification
            Notification.objects.create(
                facture=facture,
                utilisateur=locataire,
                type_notification=Notification.Type.EMAIL,
                titre='Nouvelle facture',
                message=f"Facture {facture.numero_facture} pour un montant de {facture.montant_total} FCFA",
                statut=Notification.Statut.ENVOYEE
            )
        
        # Envoyer au propriétaire
        if proprietaire.email:
            message = render_to_string('email/facture_proprietaire.html', contexte)
            send_mail(sujet, message, 'noreply@immobilier.local', [proprietaire.email])
        
        facture.statut = Facture.Statut.ENVOYEE
        facture.save()
        
        logger.info(f"✅ Facture {facture.numero_facture} envoyée")
        return {'message': 'Facture envoyée'}
    
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'envoi de la facture : {str(e)}")
        raise


@shared_task
def envoyer_rappels_paiements():
    """
    Tâche programmée pour envoyer les rappels de paiement
    Exécution : tous les jours à 8h du matin
    """
    try:
        rappels_a_envoyer = RappelPaiement.objects.filter(
            est_envoye=False,
            date_programmee__lte=timezone.now()
        )
        
        rappels_envoyes = 0
        for rappel in rappels_a_envoyer:
            contrat = rappel.paiement.contrat
            locataire = contrat.locataire
            
            if not locataire or not locataire.email:
                continue

            sujet = f"Rappel de paiement - Paiement {rappel.paiement.id}"
            texte = f"Vous avez un loyer impayé de {rappel.paiement.montant_du} FCFA pour {contrat.bien.titre}."
            
            send_mail(sujet, texte, 'noreply@immobilier.local', [locataire.email])
            
            Notification.objects.create(
                facture=rappel.paiement.facture if hasattr(rappel.paiement, 'facture') else None,
                utilisateur=locataire,
                type_notification=Notification.Type.EMAIL,
                titre=sujet,
                message=texte,
                statut=Notification.Statut.ENVOYEE
            )
            
            rappel.est_envoye = True
            rappel.date_envoi_reel = timezone.now()
            rappel.save()
            rappels_envoyes += 1
        
        logger.info(f"✅ {rappels_envoyes} rappels de paiement envoyés")
        return {'rappels_envoyes': rappels_envoyes}
    
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'envoi des rappels : {str(e)}")
        raise
