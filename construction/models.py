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
    # Valeurs par défaut : un client "intéressé" crée d'abord ce projet en
    # coquille vide (voir demander_contact_construction), avant même de
    # connaître le type de projet — remplies pour de vrai une fois le RDV
    # confirmé par l'entreprise, via demande_devis.
    type_projet  = models.CharField(max_length=20, choices=TypeProjet.choices, default=TypeProjet.AUTRE)
    superficie   = models.DecimalField(max_digits=8, decimal_places=0, null=True, blank=True)
    a_terrain    = models.BooleanField(default=False)
    localisation_terrain = models.CharField(max_length=255, blank=True)
    budget_estime = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True)
    description  = models.TextField(blank=True, default='')
    statut       = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    pourcentage_avancement = models.IntegerField(default=0)
    terrain_lie  = models.ForeignKey(Bien, on_delete=models.SET_NULL, null=True, blank=True, related_name='projets_construction')
    date_rdv     = models.DateTimeField(null=True, blank=True)
    notes_rdv    = models.TextField(blank=True)
    # Confirmé par l'ENTREPRISE (pas le client) — c'est ce qui débloque le
    # formulaire de devis détaillé (voir construction/views.py::demande_devis
    # / confirmer_rdv). Le client peut proposer/modifier une date via
    # gerer_rdv, mais seule l'entreprise peut la confirmer.
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


class Devis(models.Model):
    """Devis chiffré préparé par l'entreprise pour un projet, que le client
    accepte ou refuse. Plusieurs devis peuvent se succéder sur un même
    projet (ex. devis refusé puis révisé)."""

    class Statut(models.TextChoices):
        ENVOYE  = 'envoye',  'Envoyé'
        ACCEPTE = 'accepte', 'Accepté'
        REFUSE  = 'refuse',  'Refusé'
        EXPIRE  = 'expire',  'Expiré'

    projet   = models.ForeignKey(ProjetConstruction, on_delete=models.CASCADE, related_name='devis')
    montant  = models.DecimalField(max_digits=14, decimal_places=0)
    detail   = models.TextField(help_text="Prestations, matériaux, délais...")
    validite_jours = models.PositiveIntegerField(default=30)
    statut   = models.CharField(max_length=20, choices=Statut.choices, default=Statut.ENVOYE)
    motif_refus = models.TextField(blank=True)
    cree_par = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, related_name='devis_prepares')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_reponse  = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date_creation']
        verbose_name = 'Devis'
        verbose_name_plural = 'Devis'

    def __str__(self):
        return f"Devis {self.montant} FCFA — {self.projet}"

    @property
    def date_limite_validite(self):
        from datetime import timedelta
        return (self.date_creation + timedelta(days=self.validite_jours)).date()


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
        RDV_MODIFIE   = 'rdv_modifie',   'RDV proposé/modifié par le client'
        RDV_CONFIRME  = 'rdv_confirme',  'RDV confirmé par l\'entreprise — devis débloqué'
        RDV_ANNULE    = 'rdv_annule',    'RDV annulé'
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
