from django.db import models
from biens.models import Bien
from utilisateurs.models import Utilisateur


class RechercheSauvegardee(models.Model):
    """Modèle pour sauvegarder les recherches favorites"""
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='recherches_sauvegardees'
    )
    nom = models.CharField(max_length=255)
    
    # Critères de recherche
    villes = models.JSONField(default=list, blank=True)
    budget_min = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    budget_max = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    nombre_chambres_min = models.IntegerField(blank=True, null=True)
    nombre_chambres_max = models.IntegerField(blank=True, null=True)
    surface_min = models.IntegerField(blank=True, null=True)
    types_bien = models.JSONField(default=list, blank=True)
    equipements = models.JSONField(default=list, blank=True)
    animaux_autorises = models.BooleanField(default=False)
    
    # Suivi
    date_creation = models.DateTimeField(auto_now_add=True)
    date_derniere_recherche = models.DateTimeField(blank=True, null=True)
    nombre_utilisations = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = 'Recherche Sauvegardée'
        verbose_name_plural = 'Recherches Sauvegardées'
        ordering = ['-date_derniere_recherche']
    
    def __str__(self):
        return f"Recherche : {self.nom}"


class BienFavori(models.Model):
    """Modèle pour les biens favoris"""
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='biens_favoris'
    )
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name='favoris')
    date_ajout = models.DateTimeField(auto_now_add=True)
    note = models.IntegerField(default=0, choices=[(i, str(i)) for i in range(0, 6)])
    commentaire = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'Bien Favori'
        verbose_name_plural = 'Biens Favoris'
        unique_together = ['utilisateur', 'bien']
        ordering = ['-date_ajout']
    
    def __str__(self):
        return f"{self.utilisateur.username} - {self.bien.titre}"


class HistoriqueRecherche(models.Model):
    """Modèle pour tracker l'historique des recherches"""
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='historique_recherches'
    )
    requete = models.CharField(max_length=255)
    nombre_resultats = models.IntegerField(default=0)
    date_recherche = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Historique Recherche'
        verbose_name_plural = 'Historiques Recherches'
        ordering = ['-date_recherche']
    
    def __str__(self):
        return f"Recherche : {self.requete} ({self.nombre_resultats} résultats)"
