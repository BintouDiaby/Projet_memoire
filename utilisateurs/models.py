
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import URLValidator, EmailValidator, MinValueValidator, MaxValueValidator


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

    def comptes_entreprise(self):
        """Tous les comptes (Directeur + employés) de la même entreprise que
        cet utilisateur, PLUS toujours soi-même. Si `company` n'est pas
        encore défini (onboarding en cours), ne renvoie que soi-même plutôt
        qu'un queryset vide — évite qu'un filtre `company=None` ne fasse
        fuiter les données entre comptes orphelins non liés entre eux, TOUT
        en garantissant qu'un propriétaire sans entreprise liée voit quand
        même ses propres biens/contrats/paiements/clients (bug réel constaté :
        `proprietaire__in=user.comptes_entreprise()` renvoyait un queryset
        vide, donc rien, pour tout compte sans `company_id`, y compris ses
        propres ressources)."""
        if not self.company_id:
            return Utilisateur.objects.filter(id=self.id)
        return Utilisateur.objects.filter(company_id=self.company_id)

    def meme_entreprise(self, autre_user):
        """Pour les vérifications objet-par-objet (remplace `user == obj.proprietaire`).
        Vrai si même entreprise OU si c'est littéralement le même compte —
        sans ce second cas, un propriétaire sans `company_id` ne pouvait
        jamais passer cette vérification, même sur ses propres biens."""
        if not autre_user:
            return False
        if self.id == autre_user.id:
            return True
        return bool(self.company_id and self.company_id == autre_user.company_id)

    def a_acces(self, *flags):
        """Le Directeur (role=PROPRIETAIRE) et le staff plateforme ont toujours
        accès. Pour un employé, au moins un des flags donnés doit être actif
        sur son profil Collaborateur."""
        if self.role == self.Role.PROPRIETAIRE or self.is_staff:
            return True
        profile = getattr(self, 'collaborateur_profile', None)
        return bool(profile and any(getattr(profile, f, False) for f in flags))

    @property
    def peut_commercial(self):
        return self.a_acces('acces_commercial')

    @property
    def peut_comptable(self):
        return self.a_acces('acces_comptable')

    @property
    def peut_gestion_locative(self):
        return self.a_acces('acces_gestion_locative')


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
    facebook = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    # Disponibilité affichée sur la fiche publique
    horaires = models.JSONField(
        default=dict, blank=True,
        help_text="Ex: {'lundi': '08:00-18:00', 'dimanche': ''} — vide ou absent = fermé ce jour-là.",
    )
    disponible_maintenant = models.BooleanField(
        default=True,
        help_text="Décochez pour afficher « actuellement indisponible » même pendant vos horaires d'ouverture.",
    )
    delai_reponse_minutes = models.PositiveIntegerField(
        blank=True, null=True,
        help_text="Délai de réponse habituel affiché aux clients, en minutes (ex: 5, 60).",
    )

    JOURS_SEMAINE = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']

    def statut_actuel(self):
        """Statut de disponibilité dérivé des horaires + du flag manuel, pour
        la fiche publique (🟢 en ligne / 🟡 ouverte mais indisponible / 🔴 fermée)."""
        from datetime import datetime
        from django.utils import timezone

        if not self.horaires:
            return {'etat': 'inconnu'}

        now = timezone.localtime()
        jour = self.JOURS_SEMAINE[now.weekday()]
        horaire_jour = (self.horaires or {}).get(jour, '')
        ouvert = False
        if horaire_jour and '-' in horaire_jour:
            try:
                debut_s, fin_s = horaire_jour.split('-')
                debut = datetime.strptime(debut_s.strip(), '%H:%M').time()
                fin = datetime.strptime(fin_s.strip(), '%H:%M').time()
                ouvert = debut <= now.time() <= fin
            except ValueError:
                ouvert = False

        if ouvert and self.disponible_maintenant:
            return {'etat': 'ouvert', 'delai_reponse_minutes': self.delai_reponse_minutes}
        if ouvert:
            return {'etat': 'pause'}

        for i in range(1, 8):
            jour_suivant = self.JOURS_SEMAINE[(now.weekday() + i) % 7]
            h = (self.horaires or {}).get(jour_suivant, '')
            if h and '-' in h:
                return {
                    'etat': 'ferme',
                    'prochain_jour': jour_suivant,
                    'prochaine_heure': h.split('-')[0].strip(),
                    'demain': i == 1,
                }
        return {'etat': 'ferme'}

    # Identifiants légaux (OHADA/SYSCOHADA + Facture Normalisée Électronique - DGI Côte d'Ivoire)
    numero_ncc = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name="Numéro de Compte Contribuable (NCC)",
        help_text="Attribué par la DGI. Requis pour la certification FNE et comme identifiant vendeur.",
    )
    numero_rccm = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name="Numéro RCCM",
        help_text="Registre du Commerce et du Crédit Mobilier — mention obligatoire OHADA (pied de page des factures).",
    )

    class Taxes(models.TextChoices):
        TVA = 'TVA', 'TVA normal 18%'
        TVAB = 'TVAB', 'TVA réduit 9%'
        TVAC = 'TVAC', 'Exonération conventionnelle 0%'
        TVAD = 'TVAD', 'Exonération légale 0%'

    taux_tva_loyer = models.CharField(
        max_length=4, choices=Taxes.choices, default=Taxes.TVAD,
        verbose_name="Régime TVA appliqué aux loyers",
        help_text="Code transmis à la FNE pour chaque facture de loyer. Par défaut : exonération légale "
                   "(traitement standard de la location nue à usage d'habitation) — à confirmer avec votre comptable.",
    )

    # Particulier (propriétaire individuel, sans personnel ni RCCM) vs
    # Entreprise immobilière (agence — Personnel, CRM, Statistiques, RCCM).
    # Défaut ENTREPRISE : les comptes existants avant cette distinction
    # gardent tous les menus auxquels ils avaient déjà accès.
    class TypeCompte(models.TextChoices):
        PARTICULIER = 'particulier', 'Particulier'
        ENTREPRISE = 'entreprise', 'Entreprise immobilière'

    type_compte = models.CharField(
        max_length=12, choices=TypeCompte.choices, default=TypeCompte.ENTREPRISE,
    )

    # Vérification du document RCCM par un administrateur de la plateforme
    class StatutVerification(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente de vérification'
        VALIDEE = 'validee', 'Vérifiée'
        REJETEE = 'rejetee', 'Rejetée'

    document_rccm = models.FileField(
        upload_to='companies/rccm/', blank=True, null=True,
        verbose_name="Document RCCM",
        help_text="Justificatif du Registre du Commerce et du Crédit Mobilier (PDF ou photo).",
    )
    statut_verification = models.CharField(
        max_length=10, choices=StatutVerification.choices, default=StatutVerification.EN_ATTENTE,
    )
    motif_rejet = models.TextField(blank=True, default='')
    date_verification = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'

    def __str__(self):
        return self.name


class AvisEntreprise(models.Model):
    """Avis d'un locataire sur une entreprise dont il a effectivement loué
    un bien (voir contrats.models.Contrat) — un seul avis par locataire et
    par entreprise."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='avis')
    auteur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='avis_entreprises',
        limit_choices_to={'role': 'locataire'}
    )
    note = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    commentaire = models.TextField()
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['company', 'auteur']
        ordering = ['-date_creation']
        verbose_name = 'Avis sur une entreprise'
        verbose_name_plural = 'Avis sur les entreprises'

    def __str__(self):
        return f"Avis de {self.auteur.username} sur {self.company.name} ({self.note}/5)"


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


class Collaborateur(models.Model):
    """Profil employé d'une entreprise — uniquement pour les comptes
    role=GESTIONNAIRE invités par un propriétaire. Le compte fondateur
    (role=PROPRIETAIRE) n'a pas de Collaborateur : il est implicitement
    le Directeur, avec accès total à toutes les données de son entreprise."""

    class Poste(models.TextChoices):
        COMMERCIAL = 'commercial', 'Commercial'
        COMPTABLE = 'comptable', 'Comptable'
        GESTIONNAIRE_LOCATIF = 'gestionnaire_locatif', 'Gestionnaire locatif'
        ASSISTANT = 'assistant', 'Assistant'

    utilisateur = models.OneToOneField(
        Utilisateur, on_delete=models.CASCADE, related_name='collaborateur_profile'
    )
    poste = models.CharField(max_length=30, choices=Poste.choices, default=Poste.ASSISTANT)
    invite_par = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='collaborateurs_invites'
    )
    date_ajout = models.DateTimeField(auto_now_add=True)

    # Préréglages d'accès par poste (Étape 2) — de vrais champs, pas un
    # simple `if poste == ...` dans les vues, pour permettre plus tard une
    # personnalisation fine par employé sans nouvelle migration.
    acces_commercial = models.BooleanField(
        default=False, help_text="Biens, réservations, devis, messages, clients, rendez-vous"
    )
    acces_comptable = models.BooleanField(
        default=False, help_text="Facturation, validation des paiements, statistiques"
    )
    acces_gestion_locative = models.BooleanField(
        default=False, help_text="Contrats, réclamations"
    )

    PRESETS_POSTE = {
        Poste.COMMERCIAL: {'acces_commercial': True},
        Poste.COMPTABLE: {'acces_comptable': True},
        Poste.GESTIONNAIRE_LOCATIF: {'acces_gestion_locative': True},
        Poste.ASSISTANT: {},
    }

    def appliquer_preset_poste(self):
        """Réinitialise les 3 flags d'accès puis applique le préréglage du
        poste actuel. Appelé à la création et à chaque changement de poste."""
        self.acces_commercial = False
        self.acces_comptable = False
        self.acces_gestion_locative = False
        for champ, valeur in self.PRESETS_POSTE.get(self.poste, {}).items():
            setattr(self, champ, valeur)

    class Meta:
        verbose_name = 'Collaborateur'
        verbose_name_plural = 'Collaborateurs'
        ordering = ['-date_ajout']

    def __str__(self):
        return f"{self.utilisateur.get_full_name() or self.utilisateur.username} — {self.get_poste_display()}"


class Tache(models.Model):
    """Tâche assignée par le Directeur à un collaborateur de son entreprise."""

    class Statut(models.TextChoices):
        A_FAIRE = 'a_faire', 'À faire'
        FAIT = 'fait', 'Faite'

    assignee_a = models.ForeignKey(
        Utilisateur, on_delete=models.CASCADE, related_name='taches_recues'
    )
    creee_par = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, related_name='taches_creees'
    )
    titre = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    date_limite = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.A_FAIRE)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_terminee = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Tâche'
        verbose_name_plural = 'Tâches'
        ordering = ['statut', 'date_limite', '-date_creation']

    def __str__(self):
        return f"{self.titre} → {self.assignee_a.get_full_name() or self.assignee_a.username}"


class DemandeConge(models.Model):
    """Demande de congé d'un membre de l'entreprise (Directeur ou employé),
    soumise à validation du Directeur."""

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        ACCEPTE = 'accepte', 'Acceptée'
        REFUSE = 'refuse', 'Refusée'

    demandeur = models.ForeignKey(
        Utilisateur, on_delete=models.CASCADE, related_name='demandes_conge'
    )
    date_debut = models.DateField()
    date_fin = models.DateField()
    motif = models.TextField(blank=True, default='')
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.EN_ATTENTE)
    traite_par = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True, related_name='conges_traites'
    )
    date_demande = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Demande de congé'
        verbose_name_plural = 'Demandes de congé'
        ordering = ['-date_demande']

    def __str__(self):
        return f"Congé {self.demandeur.get_full_name() or self.demandeur.username} ({self.date_debut} → {self.date_fin})"


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
