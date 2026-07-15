from django.db import models
from contrats.models import Contrat, Paiement
from django.utils import timezone
import uuid


class Facture(models.Model):
    """Modèle pour les factures générées automatiquement"""

    class ModePaiement(models.TextChoices):
        WAVE         = 'wave',         'Wave'
        ORANGE_MONEY = 'orange_money', 'Orange Money'
        MTN          = 'mtn',          'MTN MoMo'
        CARTE        = 'carte',        'Carte bancaire'
        ESPECES      = 'especes',      'Espèces'
        VIREMENT     = 'virement',     'Virement bancaire'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        GENEREE = 'generee', 'Générée'
        ENVOYEE = 'envoyee', 'Envoyée'
        EN_VALIDATION = 'en_validation', 'En attente de validation'
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

    # Paiement
    mode_paiement = models.CharField(max_length=20, choices=ModePaiement.choices, blank=True, null=True)
    reference_transaction = models.CharField(max_length=50, blank=True, null=True)
    numero_paiement_declare = models.CharField(
        max_length=20, blank=True, default='',
        help_text="Numéro mobile money saisi par le locataire lors de la déclaration du paiement.",
    )
    date_declaration_paiement = models.DateTimeField(blank=True, null=True)
    motif_rejet_paiement = models.TextField(
        blank=True, default='',
        help_text="Raison indiquée par le propriétaire s'il signale un problème sur un paiement déclaré.",
    )

    # Suivi
    tentatives_envoi = models.IntegerField(default=0)
    dernier_envoi = models.DateTimeField(blank=True, null=True)

    # Certification Facture Normalisée Électronique (FNE - DGI Côte d'Ivoire)
    fne_certifiee = models.BooleanField(default=False)
    fne_reference = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name="Numéro FNE",
        help_text="Numéro de facture normalisée renvoyé par la DGI après certification (série annuelle ininterrompue).",
    )
    fne_token = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name="Jeton de vérification FNE",
        help_text="URL de vérification renvoyée par la DGI, encodée en QR code sur la facture.",
    )
    fne_certifiee_le = models.DateTimeField(blank=True, null=True)
    fne_erreur = models.TextField(
        blank=True, default='',
        help_text="Dernier message d'erreur si la certification auprès de la DGI a échoué.",
    )

    # Archivage : masque la facture de la liste active du propriétaire (utile
    # quand il y en a beaucoup) sans toucher à son statut ni à ses données —
    # réservé aux factures déjà closes (payées ou annulées).
    est_archive = models.BooleanField(default=False)

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


class MoyenPaiementEnregistre(models.Model):
    """Numéro de paiement mobile money (Wave/Orange Money/MTN) enregistré par
    un locataire pour éviter de le ressaisir à chaque déclaration de paiement.
    Un seul numéro enregistré par mode et par utilisateur."""

    utilisateur = models.ForeignKey(
        'utilisateurs.Utilisateur', on_delete=models.CASCADE, related_name='moyens_paiement'
    )
    mode_paiement = models.CharField(max_length=20, choices=Facture.ModePaiement.choices)
    numero = models.CharField(max_length=20)
    date_ajout = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Moyen de paiement enregistré'
        verbose_name_plural = 'Moyens de paiement enregistrés'
        unique_together = ['utilisateur', 'mode_paiement']
        ordering = ['-date_modification']

    def __str__(self):
        return f"{self.get_mode_paiement_display()} — {self.utilisateur.username}"

    def numero_masque(self):
        if len(self.numero) <= 2:
            return self.numero
        return '*' * (len(self.numero) - 2) + self.numero[-2:]


class RendezVousPaiement(models.Model):
    """Demande de rendez-vous pour régler une facture en espèces. Le locataire
    propose un créneau, l'entreprise l'accepte, propose un autre créneau ou
    refuse ; une fois confirmé, le paiement est constaté et confirmé le jour
    du rendez-vous via le même mécanisme que les autres moyens de paiement."""

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente de réponse'
        CONTRE_PROPOSITION = 'contre_proposition', 'Autre créneau proposé'
        CONFIRME = 'confirme', 'Confirmé'
        REFUSE = 'refuse', 'Refusé'
        HONORE = 'honore', 'Honoré (paiement reçu)'

    facture = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name='rendez_vous_paiement')
    locataire = models.ForeignKey(
        'utilisateurs.Utilisateur', on_delete=models.CASCADE, related_name='rdv_paiements_demandes'
    )

    date_demandee = models.DateTimeField(verbose_name="Date/heure demandée par le locataire")
    message = models.TextField(blank=True, default='')

    date_proposee = models.DateTimeField(
        blank=True, null=True, verbose_name="Autre créneau proposé par l'entreprise"
    )
    date_confirmee = models.DateTimeField(blank=True, null=True)

    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    motif_refus = models.TextField(blank=True, default='')

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rendez-vous de paiement'
        verbose_name_plural = 'Rendez-vous de paiement'
        ordering = ['-date_creation']

    def __str__(self):
        return f"RDV paiement — {self.facture.numero_facture} ({self.get_statut_display()})"


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
