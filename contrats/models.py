from django.db import models
from django.utils import timezone
from utilisateurs.models import Utilisateur
from biens.models import Bien
from datetime import timedelta


class Contrat(models.Model):
    """Modèle pour les contrats de location"""
    
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EN_COURS = 'en_cours', 'En cours'
        TERMINE = 'termine', 'Terminé'
        SUSPENDU = 'suspendu', 'Suspendu'
        RESILIE = 'resilie', 'Résilié'
    
    # Informations de base
    numero_contrat = models.CharField(max_length=50, unique=True)
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name='contrats')
    proprietaire = models.ForeignKey(
        Utilisateur,
        on_delete=models.PROTECT,
        related_name='contrats_proposes',
        limit_choices_to={'role': 'proprietaire'}
    )
    locataire = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contrats_souscrits',
        limit_choices_to={'role': 'locataire'}
    )
    
    # Dates
    date_debut = models.DateField()
    date_fin = models.DateField()
    date_signature = models.DateTimeField(blank=True, null=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    
    # Configuration financière
    prix_mensuel = models.DecimalField(max_digits=10, decimal_places=2)
    prix_depot_garantie = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    charges_mensuelles = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Conditions
    nombre_mois_minimum = models.IntegerField(default=12)
    jour_paiement = models.IntegerField(default=1)  # Jour du mois pour le paiement
    modalites_resilition = models.TextField(blank=True, null=True)
    conditions_speciales = models.TextField(blank=True, null=True)
    
    # Documents
    fichier_contrat = models.FileField(
        upload_to='contrats/',
        blank=True,
        null=True
    )
    
    # Audit
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Contrat'
        verbose_name_plural = 'Contrats'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['statut', 'date_debut']),
            models.Index(fields=['locataire']),
        ]
    
    def __str__(self):
        return f"Contrat {self.numero_contrat} - {self.bien.titre}"
    
    def is_actif(self):
        """Vérifier si le contrat est actif"""
        aujourd_hui = timezone.now().date()
        return self.date_debut <= aujourd_hui <= self.date_fin and self.statut == self.Statut.EN_COURS
    
    def generer_numero(self):
        """Générer automatiquement un numéro de contrat"""
        if not self.numero_contrat:
            from datetime import datetime
            self.numero_contrat = f"CONTRAT-{datetime.now().strftime('%Y%m%d%H%M%S')}"


class Paiement(models.Model):
    """Modèle pour les paiements de loyers"""
    
    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        RECU = 'recu', 'Reçu'
        RETARD_MINEUR = 'retard_mineur', 'Retard mineur'
        RETARD_MAJEUR = 'retard_majeur', 'Retard majeur'
        IMPAYE = 'impaye', 'Impayé'
    
    # Informations de base
    contrat = models.ForeignKey(Contrat, on_delete=models.CASCADE, related_name='paiements')
    mois = models.DateField(help_text="Premier jour du mois de la facturation")
    montant_du = models.DecimalField(max_digits=10, decimal_places=2)
    montant_recu = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Dates
    date_limite = models.DateField()
    date_paiement = models.DateField(blank=True, null=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    
    # Raisons de retard
    raison_retard = models.TextField(blank=True, null=True)
    
    # Pénalités
    montant_penalites = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Audit
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Paiement'
        verbose_name_plural = 'Paiements'
        ordering = ['-mois']
        unique_together = ['contrat', 'mois']
        indexes = [
            models.Index(fields=['statut', 'mois']),
            models.Index(fields=['contrat', 'statut']),
        ]
    
    def __str__(self):
        return f"Paiement {self.contrat.numero_contrat} - {self.mois.strftime('%B %Y')}"
    
    def mettre_a_jour_statut(self):
        """Mettre à jour le statut en fonction du paiement"""
        aujourd_hui = timezone.now().date()
        
        if self.date_paiement:
            self.statut = self.Statut.RECU
        elif (aujourd_hui - self.date_limite).days > 30:
            self.statut = self.Statut.IMPAYE
        elif (aujourd_hui - self.date_limite).days > 7:
            self.statut = self.Statut.RETARD_MAJEUR
        elif aujourd_hui > self.date_limite:
            self.statut = self.Statut.RETARD_MINEUR
        
        self.save()


class DocumentContrat(models.Model):
    """Modèle pour les documents associés au contrat"""
    
    class TypeDocument(models.TextChoices):
        CONTRAT = 'contrat', 'Contrat'
        AVENANT = 'avenant', 'Avenant'
        QUITTANCE = 'quittance', 'Quittance'
        RECONNAISSANCE_DETTE = 'recon_dette', 'Reconnaissance de dette'
        CERTIFICAT_RESIDENCE = 'cert_residence', 'Certificat de résidence'
    
    contrat = models.ForeignKey(Contrat, on_delete=models.CASCADE, related_name='documents')
    type_document = models.CharField(max_length=20, choices=TypeDocument.choices)
    fichier = models.FileField(upload_to='documents/contrats/')
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Document Contrat'
        verbose_name_plural = 'Documents Contrat'
    
    def __str__(self):
        return f"{self.get_type_document_display()} - {self.contrat.numero_contrat}"
