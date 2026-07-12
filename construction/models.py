from django.db import models
from utilisateurs.models import Utilisateur, Company
from biens.models import Bien


class ProfilConstruction(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='profil_construction')
    description = models.TextField(blank=True)
    annee_creation = models.IntegerField(null=True, blank=True)
    nb_projets_realises = models.IntegerField(default=0)
    specialites = models.JSONField(default=list, blank=True)
    adresse = models.CharField(max_length=255, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    site_web = models.CharField(max_length=255, blank=True)
    note_moyenne = models.DecimalField(max_digits=3, decimal_places=1, default=4.5)

    class Meta:
        verbose_name = 'Profil construction'
        verbose_name_plural = 'Profils construction'

    def __str__(self):
        return f"Profil construction — {self.company.name}"


class RealisationConstruction(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='realisations')
    titre = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to='construction/realisations/', blank=True, null=True)
    annee = models.IntegerField(null=True, blank=True)
    localisation = models.CharField(max_length=255, blank=True)
    type_projet = models.CharField(max_length=50, blank=True)
    ordre = models.IntegerField(default=0)

    class Meta:
        ordering = ['ordre', '-annee']
        verbose_name = 'Realisation'
        verbose_name_plural = 'Realisations'

    def __str__(self):
        return f"{self.titre} — {self.company.name}"


class ProjetConstruction(models.Model):

    class TypeProjet(models.TextChoices):
        VILLA      = 'villa',      'Villa'
        DUPLEX     = 'duplex',     'Duplex'
        IMMEUBLE   = 'immeuble',   'Immeuble'
        MAGASIN    = 'magasin',    'Magasin / Commerce'
        BUREAU     = 'bureau',     'Bureau'
        RENOVATION = 'renovation', 'Renovation'
        AUTRE      = 'autre',      'Autre'

    class Statut(models.TextChoices):
        EN_ATTENTE   = 'en_attente',   'En attente'
        DEVIS_ENVOYE = 'devis_envoye', 'Devis envoye'
        ACCEPTE      = 'accepte',      'Accepte'
        EN_COURS     = 'en_cours',     'En cours'
        TERMINE      = 'termine',      'Termine'
        ANNULE       = 'annule',       'Annule'

    client       = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name='projets_construction')
    entreprise   = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='projets_recus')
    type_projet  = models.CharField(max_length=20, choices=TypeProjet.choices)
    superficie   = models.DecimalField(max_digits=8, decimal_places=0, null=True, blank=True)
    a_terrain    = models.BooleanField(default=False)
    localisation_terrain = models.CharField(max_length=255, blank=True)
    budget_estime = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True)
    description  = models.TextField()
    statut       = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    pourcentage_avancement = models.IntegerField(default=0)
    terrain_lie  = models.ForeignKey(Bien, on_delete=models.SET_NULL, null=True, blank=True, related_name='projets_construction')
    date_rdv     = models.DateTimeField(null=True, blank=True)
    notes_rdv    = models.TextField(blank=True)
    rdv_confirme = models.BooleanField(default=False)
    cree_le      = models.DateTimeField(auto_now_add=True)
    mis_a_jour_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-cree_le']
        verbose_name = 'Projet de construction'
        verbose_name_plural = 'Projets de construction'

    def __str__(self):
        return f"{self.get_type_projet_display()} — {self.client.username} / {self.entreprise.name}"

    def creer_etapes_par_defaut(self):
        ETAPES = [
            ('Etude du projet', 0),
            ('Devis', 1),
            ('Signature du contrat', 2),
            ('Fondations', 3),
            ('Elevation des murs', 4),
            ('Toiture', 5),
            ('Finitions', 6),
            ('Livraison', 7),
        ]
        for nom, ordre in ETAPES:
            EtapeChantier.objects.get_or_create(
                projet=self, nom=nom,
                defaults={'ordre': ordre, 'statut': EtapeChantier.StatutEtape.A_VENIR}
            )

    def recalculer_avancement(self):
        etapes = self.etapes.all()
        if not etapes.exists():
            return
        total = etapes.count()
        terminees = etapes.filter(statut=EtapeChantier.StatutEtape.TERMINE).count()
        self.pourcentage_avancement = round(terminees / total * 100)
        self.save(update_fields=['pourcentage_avancement'])


class EtapeChantier(models.Model):

    class StatutEtape(models.TextChoices):
        A_VENIR  = 'a_venir',  'A venir'
        EN_COURS = 'en_cours', 'En cours'
        TERMINE  = 'termine',  'Termine'

    projet   = models.ForeignKey(ProjetConstruction, on_delete=models.CASCADE, related_name='etapes')
    nom      = models.CharField(max_length=100)
    ordre    = models.IntegerField(default=0)
    statut   = models.CharField(max_length=20, choices=StatutEtape.choices, default=StatutEtape.A_VENIR)
    date_prevue = models.DateField(null=True, blank=True)
    date_reelle = models.DateField(null=True, blank=True)
    notes    = models.TextField(blank=True)

    class Meta:
        ordering = ['ordre']
        verbose_name = 'Etape de chantier'
        verbose_name_plural = 'Etapes de chantier'

    def __str__(self):
        return f"{self.nom} ({self.projet})"


class PhotoChantier(models.Model):
    projet     = models.ForeignKey(ProjetConstruction, on_delete=models.CASCADE, related_name='photos_chantier')
    photo      = models.ImageField(upload_to='chantiers/photos/', blank=True, null=True)
    legende    = models.CharField(max_length=255, blank=True)
    etape      = models.ForeignKey(EtapeChantier, on_delete=models.SET_NULL, null=True, blank=True, related_name='photos')
    ajoute_par = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True)
    cree_le    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-cree_le']
        verbose_name = 'Photo de chantier'

    def __str__(self):
        return f"Photo chantier — {self.projet}"


class NotificationConstruction(models.Model):
    class Type(models.TextChoices):
        NOUVEAU_DEVIS = 'nouveau_devis', 'Nouveau devis reçu'
        RDV_PROPOSE   = 'rdv_propose',   'RDV proposé'
        RDV_MODIFIE   = 'rdv_modifie',   'RDV modifié par le client'
        RDV_CONFIRME  = 'rdv_confirme',  'RDV confirmé par le client'
        RDV_ANNULE    = 'rdv_annule',    'RDV annulé par l\'entreprise'
        STATUT_CHANGE = 'statut_change', 'Statut du projet modifié'
        ETAPE_CHANGE  = 'etape_change',  'Étape mise à jour'

    destinataire = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name='notifs_construction')
    projet       = models.ForeignKey(ProjetConstruction, on_delete=models.CASCADE, related_name='notifications')
    type         = models.CharField(max_length=30, choices=Type.choices)
    message      = models.TextField()
    lue          = models.BooleanField(default=False)
    cree_le      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-cree_le']
        verbose_name = 'Notification construction'

    def __str__(self):
        return f"[{self.type}] {self.destinataire.username} — {self.projet}"
