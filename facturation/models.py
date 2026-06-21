from django.db import models
from contrats.models import Contrat, Paiement
from django.utils import timezone
import uuid


class Facture(models.Model):
    """Modèle pour les factures générées automatiquement"""
    
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        GENEREE = 'generee', 'Générée'
        ENVOYEE = 'envoyee', 'Envoyée'
        PAYEE = 'payee', 'Payée'
        ANNULEE = 'annulee', 'Annulée'
    
    # Identifiant
    id_unique = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    numero_facture = models.CharField(max_length=50, unique=True)
    
    # Relations
    paiement = models.OneToOneField(
        Paiement,
        on_delete=models.CASCADE,
        related_name='facture'
    )
    contrat = models.ForeignKey(Contrat, on_delete=models.PROTECT, related_name='factures')
    
    # Date
    date_generation = models.DateTimeField(auto_now_add=True)
    date_emission = models.DateTimeField(blank=True, null=True)
    date_echéance = models.DateField()
    date_paiement = models.DateField(blank=True, null=True)
    
    # Montants
    montant_loyer = models.DecimalField(max_digits=10, decimal_places=2)
    montant_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    montant_autres = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    montant_taxe = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    montant_total = models.DecimalField(max_digits=10, decimal_places=2)
    # Descriptions
    description = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    # Statut et fichier
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    fichier_pdf = models.FileField(upload_to='factures/pdf/', blank=True, null=True)
    
    # Suivi
    tentatives_envoi = models.IntegerField(default=0)
    dernier_envoi = models.DateTimeField(blank=True, null=True)
    
    # Audit
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Facture'
        verbose_name_plural = 'Factures'
        ordering = ['-date_generation']
        indexes = [
            models.Index(fields=['statut', 'date_echéance']),
            models.Index(fields=['contrat', 'date_generation']),
        ]
    
    def __str__(self):
        return f"Facture {self.numero_facture}"
    
    def generer_numero(self):
        """Générer automatiquement un numéro de facture"""
        if not self.numero_facture:
            from datetime import datetime
            self.numero_facture = f"FAC-{datetime.now().strftime('%Y%m%d%H%M%S')}"


class Notification(models.Model):
    """Modèle pour les notifications d'envoi de factures"""
    
    class Type(models.TextChoices):
        EMAIL = 'email', 'Email'
        SMS = 'sms', 'SMS'
        PUSH = 'push', 'Notification Push'
    
    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        ENVOYEE = 'envoyee', 'Envoyée'
        LUE = 'lue', 'Lue'
        ECHEC = 'echec', 'Échec'
    
    # Relations
    facture = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name='notifications')
    utilisateur = models.ForeignKey(
        'utilisateurs.Utilisateur',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    # Contenu
    type_notification = models.CharField(max_length=20, choices=Type.choices)
    titre = models.CharField(max_length=255)
    message = models.TextField()
    
    # Suivi
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_envoi = models.DateTimeField(blank=True, null=True)
    date_lecture = models.DateTimeField(blank=True, null=True)
    
    # Erreur
    message_erreur = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['utilisateur', 'statut']),
            models.Index(fields=['facture']),
        ]
    
    def __str__(self):
        return f"Notification {self.type_notification} pour {self.utilisateur.username}"


class RappelPaiement(models.Model):
    """Modèle pour les rappels de paiement automatiques"""
    
    class Type(models.TextChoices):
        PREMIER_RAPPEL = 'premier_rappel', 'Premier rappel (2 jours après)'
        DEUXIEME_RAPPEL = 'deuxieme_rappel', 'Deuxième rappel (7 jours après)'
        AVIS_FINAL = 'avis_final', 'Avis final (15 jours après)'
    
    # Relations
    paiement = models.ForeignKey(Paiement, on_delete=models.CASCADE, related_name='rappels')
    notification = models.ForeignKey(
        Notification,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Configuration
    type_rappel = models.CharField(max_length=20, choices=Type.choices)
    date_programmee = models.DateTimeField()
    date_envoi_reel = models.DateTimeField(blank=True, null=True)
    
    # Statut
    est_envoye = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Rappel de Paiement'
        verbose_name_plural = 'Rappels de Paiement'
        unique_together = ['paiement', 'type_rappel']
        indexes = [
            models.Index(fields=['est_envoye', 'date_programmee']),
        ]
    
    def __str__(self):
        return f"{self.get_type_rappel_display()} pour {self.paiement}"
