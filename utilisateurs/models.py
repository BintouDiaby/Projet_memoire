
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import URLValidator, EmailValidator


class Utilisateur(AbstractUser):
    """Modèle personnalisé pour les utilisateurs"""
    
    class Role(models.TextChoices):
        PROPRIETAIRE = 'proprietaire', 'Propriétaire'
        GESTIONNAIRE = 'gestionnaire', 'Gestionnaire'
        LOCATAIRE = 'locataire', 'Locataire'
        ADMIN = 'admin', 'Administrateur'
    
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.LOCATAIRE
    )
    # Entreprise associée (optionnel)
    company = models.ForeignKey(
        'Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    telephone = models.CharField(max_length=20, blank=True, null=True)
    adresse = models.CharField(max_length=255, blank=True, null=True)
    ville = models.CharField(max_length=100, blank=True, null=True)
    code_postal = models.CharField(max_length=10, blank=True, null=True)
    photo_profil = models.ImageField(
        upload_to='profils/',
        blank=True,
        null=True
    )
    bio = models.TextField(blank=True, null=True)
    documents_verifies = models.BooleanField(default=False)
    email_verifie = models.BooleanField(default=False)
    # Code de vérification email (OTP) : fonctionne même quand l'utilisateur
    # ouvre son email sur un autre réseau/appareil que celui du serveur,
    # contrairement à un lien de confirmation qui dépend de l'hôte de la requête.
    otp_code = models.CharField(max_length=6, blank=True, default='')
    otp_expire_le = models.DateTimeField(null=True, blank=True)
    # Confidentialité : ce que les entreprises vérifiées peuvent voir/faire
    # sur la fiche client (dashboard/client_detail.html côté propriétaire)
    afficher_telephone = models.BooleanField(default=True)
    afficher_email = models.BooleanField(default=False)
    accepte_appels = models.BooleanField(default=True)
    # Préférences du tableau de bord personnalisées par utilisateur
    dashboard_preferences = models.JSONField(default=dict, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
        ordering = ['-date_creation']
    
    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"


class Company(models.Model):
    """Modèle représentant une entreprise / organisation cliente.

    `types` est une liste d'activités que l'entreprise réalise, par ex.:
    ["location", "vente", "construction"]
    """
    name = models.CharField(max_length=255)
    types = models.JSONField(default=list, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)
    adresse = models.CharField(max_length=255, blank=True, null=True)
    ville = models.CharField(max_length=100, blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    logo = models.ImageField(upload_to='companies/logos/', blank=True, null=True)
    cover_image = models.ImageField(upload_to='companies/covers/', blank=True, null=True)

    class Meta:
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'

    def __str__(self):
        return self.name


class ProprietaireProfile(models.Model):
    """Profil étendu pour les propriétaires"""
    utilisateur = models.OneToOneField(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='proprietaire_profile'
    )
    numero_siret_siren = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )
    nom_entreprise = models.CharField(max_length=255, blank=True, null=True)
    numero_licence = models.CharField(max_length=50, blank=True, null=True)
    iban = models.CharField(max_length=34, blank=True, null=True)
    nombre_proprietes = models.IntegerField(default=0)
    experience_annees = models.IntegerField(default=0)
    certification = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Profil Propriétaire'
        verbose_name_plural = 'Profils Propriétaires'
    
    def __str__(self):
        return f"Propriétaire: {self.utilisateur.username}"


class LocataireProfile(models.Model):
    """Profil étendu pour les locataires"""
    utilisateur = models.OneToOneField(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='locataire_profile'
    )
    numero_identite = models.CharField(max_length=50, blank=True, null=True)
    revenu_mensuel = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )
    numero_reference_bancaire = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )
    avis_impot = models.FileField(
        upload_to='documents/locataires/',
        blank=True,
        null=True
    )
    preuve_emploi = models.FileField(
        upload_to='documents/locataires/',
        blank=True,
        null=True
    )
    garant_contact = models.CharField(max_length=255, blank=True, null=True)
    localisation_preferee = models.CharField(max_length=255, blank=True, null=True)
    budget_max_mensuel = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )
    
    class Meta:
        verbose_name = 'Profil Locataire'
        verbose_name_plural = 'Profils Locataires'
    
    def __str__(self):
        return f"Locataire: {self.utilisateur.username}"
