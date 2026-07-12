from django.db import models
from django.utils import timezone
from utilisateurs.models import Utilisateur
from django.db.models import Sum, Count, Q, F
from datetime import timedelta


class StatistiquesProprietaire(models.Model):
    """Modèle pour stocker les statistiques des propriétaires"""
    
    proprietaire = models.OneToOneField(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='statistiques_proprietaire',
        limit_choices_to={'role': 'proprietaire'}
    )
    
    # Statistiques de base
    nombre_proprietes = models.IntegerField(default=0)
    nombre_contrats_actifs = models.IntegerField(default=0)
    nombre_locataires = models.IntegerField(default=0)
    
    # Revenus
    revenu_mensuel_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    revenu_annuel_estime = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    revenu_recu_ce_mois = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Retards de paiement
    montant_impaye = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    nombre_contrats_avec_impaye = models.IntegerField(default=0)
    
    # Taux de collecte
    taux_collecte_pourcentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100
    )  # En pourcentage
    
    # Données mises à jour
    date_derniere_mise_a_jour = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Statistiques Propriétaire'
        verbose_name_plural = 'Statistiques Propriétaires'
    
    def __str__(self):
        return f"Statistiques - {self.proprietaire.username}"
    
    def mettre_a_jour_statistiques(self):
        """Mettre à jour les statistiques du propriétaire"""
        from biens.models import Bien
        from contrats.models import Contrat, Paiement
        
        aujourd_hui = timezone.now().date()
        
        # Compter les propriétés
        self.nombre_proprietes = Bien.objects.filter(
            proprietaire=self.proprietaire
        ).count()
        
        # Compter les contrats actifs
        self.nombre_contrats_actifs = Contrat.objects.filter(
            proprietaire=self.proprietaire,
            statut='en_cours',
            date_debut__lte=aujourd_hui,
            date_fin__gte=aujourd_hui
        ).count()
        
        # Compter les locataires
        self.nombre_locataires = Contrat.objects.filter(
            proprietaire=self.proprietaire,
            statut='en_cours'
        ).values('locataire').distinct().count()
        
        # Calculer les revenus
        contrats_actifs = Contrat.objects.filter(
            proprietaire=self.proprietaire,
            statut='en_cours'
        ).aggregate(
            total=Sum('prix_mensuel'),
            charges=Sum('charges_mensuelles')
        )
        
        self.revenu_mensuel_total = (contrats_actifs['total'] or 0) + (contrats_actifs['charges'] or 0)
        self.revenu_annuel_estime = self.revenu_mensuel_total * 12
        
        # Revenus reçus ce mois
        debut_mois = aujourd_hui.replace(day=1)
        self.revenu_recu_ce_mois = Paiement.objects.filter(
            contrat__proprietaire=self.proprietaire,
            statut='recu',
            date_paiement__gte=debut_mois
        ).aggregate(Sum('montant_recu'))['montant_recu__sum'] or 0
        
        # Montants impayés
        impaye_data = Paiement.objects.filter(
            contrat__proprietaire=self.proprietaire,
            statut__in=['impaye', 'retard_majeur']
        ).aggregate(
            total=Sum('montant_du'),
            count=Count('id')
        )
        
        self.montant_impaye = impaye_data['total'] or 0
        self.nombre_contrats_avec_impaye = impaye_data['count'] or 0
        
        # Taux de collecte
        if self.revenu_mensuel_total > 0:
            self.taux_collecte_pourcentage = (self.revenu_recu_ce_mois / self.revenu_mensuel_total) * 100
        
        self.save()


class TableauBordLocataire(models.Model):
    """Modèle pour les données du tableau de bord locataire"""
    
    locataire = models.OneToOneField(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='tableau_bord_locataire',
        limit_choices_to={'role': 'locataire'}
    )
    
    # Contrats
    nombre_contrats_actifs = models.IntegerField(default=0)
    nombre_recherches_sauvegardees = models.IntegerField(default=0)
    
    # Paiements
    prochain_paiement_date = models.DateField(blank=True, null=True)
    prochain_paiement_montant = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )
    paiements_en_retard = models.IntegerField(default=0)
    montant_en_retard = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Biens favoris
    nombre_biens_favoris = models.IntegerField(default=0)
    
    # Visites
    nombre_visites_programmees = models.IntegerField(default=0)
    
    # Mise à jour
    date_derniere_mise_a_jour = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Tableau de Bord Locataire'
        verbose_name_plural = 'Tableaux de Bord Locataires'
    
    def __str__(self):
        return f"Dashboard - {self.locataire.username}"


class AlerteSysteme(models.Model):
    """Modèle pour les alertes système"""
    
    class Severite(models.TextChoices):
        INFO = 'info', 'Information'
        AVERTISSEMENT = 'warning', 'Avertissement'
        ERREUR = 'error', 'Erreur'
        CRITIQUE = 'critical', 'Critique'
    
    class Statut(models.TextChoices):
        ACTIVE = 'active', 'Active'
        RESOLUE = 'resolue', 'Résolue'
        IGNOREE = 'ignoree', 'Ignorée'
    
    # Contenu
    titre = models.CharField(max_length=255)
    message = models.TextField()
    severite = models.CharField(max_length=20, choices=Severite.choices, default=Severite.INFO)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.ACTIVE)
    
    # Ciblage
    tout_le_monde = models.BooleanField(default=False)
    proprietaires = models.BooleanField(default=False)
    locataires = models.BooleanField(default=False)
    utilisateurs_specifiques = models.ManyToManyField(
        Utilisateur,
        blank=True,
        related_name='alertes_specifiques'
    )
    
    # Dates
    date_creation = models.DateTimeField(auto_now_add=True)
    date_expiration = models.DateTimeField(blank=True, null=True)
    date_resolution = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'Alerte Système'
        verbose_name_plural = 'Alertes Système'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['statut', 'severite']),
        ]
    
    def __str__(self):
        return f"{self.titre} ({self.severite})"


class LogActivite(models.Model):
    """Modèle pour tracker les activités importantes"""
    
    class Type(models.TextChoices):
        CONNEXION = 'connexion', 'Connexion'
        CREATION_BIEN = 'creation_bien', 'Création de bien'
        CREATION_CONTRAT = 'creation_contrat', 'Création de contrat'
        FACTURE_GENEREE = 'facture_generee', 'Facture générée'
        PAIEMENT_RECU = 'paiement_recu', 'Paiement reçu'
        MODIFICATION = 'modification', 'Modification'
        SUPPRESSION = 'suppression', 'Suppression'
        EXPORT = 'export', 'Export'
        IMPORT = 'import', 'Import'
        AUTRE = 'autre', 'Autre'
    
    # Informations
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='logs_activite'
    )
    type_activite = models.CharField(max_length=50, choices=Type.choices)
    description = models.TextField()
    
    # Détails
    details_json = models.JSONField(default=dict, blank=True)
    adresse_ip = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    
    # Date
    date_activite = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Log Activité'
        verbose_name_plural = 'Logs Activité'
        ordering = ['-date_activite']
        indexes = [
            models.Index(fields=['utilisateur', 'date_activite']),
            models.Index(fields=['type_activite']),
        ]
    
    def __str__(self):
        return f"{self.utilisateur.username} - {self.get_type_activite_display()}"


class RapportMensuel(models.Model):
    """Modèle pour les rapports mensuels"""
    
    # Propriétaire
    proprietaire = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='rapports_mensuels',
        limit_choices_to={'role': 'proprietaire'}
    )
    
    # Période
    mois = models.DateField(help_text="Premier jour du mois")
    
    # Données collectées
    nombre_proprietes = models.IntegerField()
    nombre_contrats_actifs = models.IntegerField()
    nombre_locataires = models.IntegerField()
    
    # Revenus
    revenu_attendu = models.DecimalField(max_digits=12, decimal_places=2)
    revenu_recu = models.DecimalField(max_digits=12, decimal_places=2)
    montant_impaye = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Taux
    taux_collecte = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Généré
    date_generation = models.DateTimeField(auto_now_add=True)
    fichier_pdf = models.FileField(upload_to='rapports/', blank=True, null=True)
    
    class Meta:
        verbose_name = 'Rapport Mensuel'
        verbose_name_plural = 'Rapports Mensuels'
        unique_together = ['proprietaire', 'mois']
        ordering = ['-mois']
    
    def __str__(self):
        return f"Rapport {self.mois.strftime('%B %Y')} - {self.proprietaire.username}"


class ConfigurationDashboard(models.Model):
    """Modèle pour les paramètres de configuration du dashboard"""
    
    utilisateur = models.OneToOneField(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='config_dashboard'
    )
    
    # Affiches
    afficher_revenus = models.BooleanField(default=True)
    afficher_contrats = models.BooleanField(default=True)
    afficher_alertes = models.BooleanField(default=True)
    afficher_historique = models.BooleanField(default=True)
    
    # Notifications
    notifications_email_activees = models.BooleanField(default=True)
    notifier_paiement_recu = models.BooleanField(default=True)
    notifier_impaye = models.BooleanField(default=True)
    notifier_new_demande = models.BooleanField(default=True)
    
    # Langue & Préférences
    langue = models.CharField(
        max_length=10,
        default='fr-FR',
        choices=[
            ('fr-FR', 'Français'),
            ('en-US', 'English'),
        ]
    )
    theme = models.CharField(
        max_length=20,
        default='light',
        choices=[
            ('light', 'Clair'),
            ('dark', 'Sombre'),
        ]
    )
    
    # Widgets personnalisés
    widgets_actifs = models.JSONField(default=list, blank=True)
    
    # Mise à jour
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Configuration Dashboard'
        verbose_name_plural = 'Configurations Dashboard'
    
    def __str__(self):
        return f"Config Dashboard - {self.utilisateur.username}"


class Notification(models.Model):
    """Notification unifiée : chaque action utilisateur (message, visite,
    devis, réclamation, paiement...) passe par `NotificationService.send()`
    (dashboard/services.py) au lieu de créer directement des lignes ici.

    Ne remplace pas `facturation.Notification` (envois email/SMS programmés)
    ni `construction.NotificationConstruction` (déjà branchée sur ses propres
    templates) — c'est le point d'entrée pour tout ce qui est nouveau.
    """

    class Type(models.TextChoices):
        MESSAGE = 'message', 'Nouveau message'
        VISITE = 'visite', 'Visite'
        RESERVATION = 'reservation', 'Réservation'
        DEVIS = 'devis', 'Devis'
        RECLAMATION = 'reclamation', 'Réclamation'
        PAIEMENT = 'paiement', 'Paiement'
        CONTRAT = 'contrat', 'Contrat'
        SYSTEME = 'systeme', 'Système'

    destinataire = models.ForeignKey(
        Utilisateur, on_delete=models.CASCADE, related_name='notifications_recues'
    )
    expediteur = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notifications_envoyees'
    )
    type_notification = models.CharField(max_length=20, choices=Type.choices)
    titre = models.CharField(max_length=255)
    message = models.TextField(blank=True, default='')
    lien = models.CharField(max_length=255, blank=True, default='')
    lue = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['destinataire', 'lue']),
        ]

    def __str__(self):
        return f"{self.titre} → {self.destinataire.username}"
