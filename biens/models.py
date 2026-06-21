from django.db import models
from utilisateurs.models import Utilisateur
from django.core.validators import MinValueValidator


class Bien(models.Model):
    """Modèle pour les biens immobiliers"""
    
    class TypeBien(models.TextChoices):
        APPARTEMENT = 'appartement', 'Appartement'
        MAISON = 'maison', 'Maison'
        MAISON_BASSE = 'maison_basse', 'Maison basse'
        STUDIO = 'studio', 'Studio'
        T1 = 't1', 'T1'
        T2 = 't2', 'T2'
        T3 = 't3', 'T3'
        T4 = 't4', 'T4'
        PLUS = 't5plus', 'T5+'
        DUPLEX = 'duplex', 'Duplex'
        IMMEUBLE = 'immeuble', 'Immeuble'
        RESIDENCE = 'residence', 'Résidence'
        TERRAIN = 'terrain', 'Terrain'
        BUREAU = 'bureau', 'Bureau'
        MAGASIN = 'magasin', 'Magasin'
        BOUTIQUE = 'boutique', 'Boutique'
        LOCAL_COMMERCIAL = 'local_commercial', 'Local commercial'
        ENTREPOT = 'entrepot', 'Entrepôt'
    
    class Statut(models.TextChoices):
        DISPONIBLE = 'disponible', 'Disponible'
        LOUE = 'loue', 'Loué'
        MAINTENANCE = 'maintenance', 'Maintenance'
        ARCHIVE = 'archive', 'Archivé'
    
    # Informations basiques
    titre = models.CharField(max_length=255)
    description = models.TextField()
    type_bien = models.CharField(max_length=20, choices=TypeBien.choices)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.DISPONIBLE)
    
    # Localisation
    adresse = models.CharField(max_length=255)
    ville = models.CharField(max_length=100)
    code_postal = models.CharField(max_length=10)
    pays = models.CharField(max_length=100, default='Côte d\'Ivoire')
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    
    # Caractéristiques
    surface_m2 = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    nombre_chambres = models.IntegerField(validators=[MinValueValidator(0)])
    nombre_salles_bain = models.IntegerField(validators=[MinValueValidator(0)])
    nombre_etages = models.IntegerField(validators=[MinValueValidator(1)], default=1)
    
    # Prix
    prix_mensuel = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    prix_vente = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)], blank=True, null=True)
    prix_depot_garantie = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0
    )
    charges_incluses = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Équipements
    equipements = models.JSONField(default=list, blank=True)  # Liste des équipements
    animaux_autorises = models.BooleanField(default=False)
    fumeurs_acceptes = models.BooleanField(default=False)
    
    # Photos
    photo_principale = models.ImageField(upload_to='biens/principales/')
    photos_additionnelles = models.JSONField(default=list, blank=True)
    
    # Propriétaire
    proprietaire = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='biens',
        limit_choices_to={'role': 'proprietaire'}
    )

    # Type d'opération : location / vente / les deux
    class TransactionType(models.TextChoices):
        LOCATION = 'location', 'Location'
        VENTE = 'vente', 'Vente'
        BOTH = 'both', 'Location & Vente'

    transaction_type = models.CharField(
        max_length=10,
        choices=TransactionType.choices,
        default=TransactionType.LOCATION,
        help_text='Type d\'opération pour ce bien'
    )
    
    # Dates
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    date_publication = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'Bien'
        verbose_name_plural = 'Biens'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['statut', 'ville']),
            models.Index(fields=['prix_mensuel']),
        ]
    
    def __str__(self):
        return f"{self.titre} - {self.ville}"


class PhotoBien(models.Model):
    """Modèle pour les photos additionnelles des biens"""
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name='photos')
    photo = models.ImageField(upload_to='biens/photos/')
    description = models.CharField(max_length=255, blank=True, null=True)
    ordre = models.IntegerField(default=0)
    date_ajout = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['ordre']
        verbose_name = 'Photo'
        verbose_name_plural = 'Photos'
    
    def __str__(self):
        return f"Photo de {self.bien.titre}"


class Visite(models.Model):
    """Modèle pour les visites de biens"""
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name='visites')
    locataire = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='visites',
        limit_choices_to={'role': 'locataire'}
    )
    date_visite = models.DateTimeField()
    notes = models.TextField(blank=True, null=True)
    interet = models.BooleanField(default=False)
    date_reservation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['bien', 'locataire', 'date_visite']
        verbose_name = 'Visite'
        verbose_name_plural = 'Visites'
    
    def __str__(self):
        return f"Visite de {self.locataire.username} pour {self.bien.titre}"
