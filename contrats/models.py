from django.db import models
from django.utils import timezone
from utilisateurs.models import Utilisateur
from biens.models import Bien
from datetime import timedelta


class Contrat(models.Model):
    """Modèle pour les contrats de location"""
    
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EN_ATTENTE_SIGNATURE = 'en_attente_signature', 'En attente de signature du locataire'
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
    
    # Réservation à l'origine de ce contrat, le cas échéant (un client qui
    # réserve un bien puis valide sa réservation passe par la signature d'un
    # vrai contrat plutôt qu'une simple confirmation de statut).
    reservation = models.OneToOneField(
        'biens.Reservation', on_delete=models.SET_NULL, null=True, blank=True, related_name='contrat'
    )

    # Dates
    date_debut = models.DateField()
    date_fin = models.DateField()
    # Signature électronique simple (clic-à-clic) : `date_envoi_signature` est
    # posée quand le propriétaire finalise le contrat et l'envoie au
    # locataire ; `date_signature` n'est posée QUE quand le locataire signe
    # réellement (voir `contrat_signer`) — c'est ce moment qui fait passer le
    # contrat EN_COURS, pas la création par le propriétaire seul.
    date_envoi_signature = models.DateTimeField(blank=True, null=True)
    date_signature = models.DateTimeField(blank=True, null=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    
    # Configuration financière
    prix_mensuel = models.DecimalField(max_digits=10, decimal_places=2)
    prix_depot_garantie = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    charges_mensuelles = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Remboursement de la caution (à la fin du contrat)
    class StatutCaution(models.TextChoices):
        NON_TRAITEE = 'non_traitee', 'Non traitée'
        RETENUE = 'retenue', 'Retenue (partiellement ou totalement)'
        REMBOURSEE = 'remboursee', 'Remboursée'
    statut_caution = models.CharField(max_length=20, choices=StatutCaution.choices, default=StatutCaution.NON_TRAITEE)
    montant_caution_rembourse = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    motif_retenue_caution = models.TextField(blank=True, default='')
    date_remboursement_caution = models.DateField(blank=True, null=True)
    
    # Conditions
    nombre_mois_minimum = models.IntegerField(default=12)
    jour_paiement = models.IntegerField(default=1)  # Jour du mois pour le paiement
    modalites_resilition = models.TextField(blank=True, null=True)
    conditions_speciales = models.TextField(blank=True, null=True)

    # Barème des retards de paiement (Article 10) — configurable par contrat ;
    # ce barème est écrit noir sur blanc dans le contrat signé, et déclenche
    # l'escalade automatique (rappels/frais/mise en demeure — voir
    # contrats.escalade). La mise en demeure reste une lettre formelle
    # invitant à régulariser, jamais une saisine automatique de la justice —
    # seul le propriétaire décide d'aller plus loin.
    jours_avant_rappel = models.PositiveIntegerField(
        default=7, verbose_name="Rappel après (jours de retard)"
    )
    jours_avant_frais = models.PositiveIntegerField(
        default=14, verbose_name="Frais de retard après (jours)"
    )
    montant_frais_retard = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name="Montant des frais de retard (FCFA)",
        help_text="0 = aucun frais de retard appliqué.",
    )
    jours_avant_mise_en_demeure = models.PositiveIntegerField(
        default=21, verbose_name="Mise en demeure après (jours de retard)"
    )

    # Texte des articles du contrat, figé au moment de l'envoi pour signature
    # (BROUILLON -> EN_ATTENTE_SIGNATURE) : ce que le locataire a réellement
    # lu et signé ne doit plus bouger même si le propriétaire modifie le
    # contrat après coup. Tant que le contrat est en brouillon, les articles
    # sont recalculés à la volée depuis les champs actuels (voir generer_articles).
    texte_contrat_signe = models.TextField(blank=True, default='')

    # Archivage : masque le contrat des listes actives sans toucher à son
    # statut juridique ni à ses données (paiements, factures...). N'a de sens
    # que pour un contrat déjà terminé/résilié — voir contrat_archiver.
    est_archive = models.BooleanField(default=False)

    # Résiliation anticipée (voir contrat_resilier) — distincte d'une fin de
    # contrat arrivée à échéance (statut TERMINE), qui n'a pas besoin de motif.
    date_resiliation = models.DateTimeField(blank=True, null=True)
    motif_resiliation = models.TextField(blank=True, default='')

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

    @staticmethod
    def _fcfa(montant):
        return f"{montant:,.0f}".replace(',', ' ') + " FCFA"

    def generer_articles(self):
        """Construit les articles numérotés du contrat à partir de ses champs
        actuels (bien, dates, montants, barème de retard). Utilisé pour
        l'aperçu en brouillon ET pour figer `texte_contrat_signe` au moment
        de l'envoi pour signature — voir la docstring de ce champ."""
        bien = self.bien
        locataire_nom = self.locataire.get_full_name() or self.locataire.username if self.locataire else '(locataire à désigner)'
        proprietaire_nom = self.proprietaire.get_full_name() or self.proprietaire.username

        articles = [
            {
                'numero': 1, 'titre': "Objet du contrat",
                'texte': (
                    f"Le présent contrat a pour objet la location, par {proprietaire_nom} (le bailleur) "
                    f"à {locataire_nom} (le locataire), du bien suivant : {bien.titre}, situé "
                    f"{bien.adresse}{', ' + bien.commune if bien.commune else ''}, {bien.ville}, "
                    f"d'une superficie de {bien.surface_m2} m², comportant {bien.nombre_chambres} chambre(s) "
                    f"et {bien.nombre_salles_bain} salle(s) de bain."
                ),
            },
            {
                'numero': 2, 'titre': "Durée",
                'texte': (
                    f"Le présent contrat est conclu pour une durée de {self.nombre_mois_minimum} mois, "
                    f"à compter du {self.date_debut.strftime('%d/%m/%Y')} jusqu'au {self.date_fin.strftime('%d/%m/%Y')}."
                ),
            },
            {
                'numero': 3, 'titre': "Montant du loyer",
                'texte': (
                    f"Le loyer mensuel est fixé à {self._fcfa(self.prix_mensuel)}"
                    + (f", majoré de charges mensuelles de {self._fcfa(self.charges_mensuelles)}." if self.charges_mensuelles else '.')
                ),
            },
            {
                'numero': 4, 'titre': "Paiement",
                'texte': (
                    f"Le loyer est payable d'avance, au plus tard le {self.jour_paiement} de chaque mois, "
                    f"par tout moyen de paiement accepté par le bailleur (mobile money, carte bancaire, "
                    f"espèces sur rendez-vous convenu, ou virement bancaire)."
                ),
            },
            {
                'numero': 5, 'titre': "Dépôt de garantie",
                'texte': (
                    f"Un dépôt de garantie de {self._fcfa(self.prix_depot_garantie)} est versé par le locataire "
                    f"à la signature du présent contrat. Il sera restitué en fin de bail, déduction faite le cas "
                    f"échéant des sommes dues au titre de dégradations locatives ou d'impayés, après réalisation "
                    f"de l'état des lieux de sortie."
                ) if self.prix_depot_garantie else "Aucun dépôt de garantie n'est exigé pour ce contrat.",
            },
            {
                'numero': 6, 'titre': "Obligations du bailleur",
                'texte': (
                    "Le bailleur s'engage à délivrer un logement en bon état d'usage et de réparation, à en "
                    "assurer la jouissance paisible au locataire, et à prendre en charge les grosses réparations "
                    "(structure, toiture, gros équipements) qui ne résultent pas d'une négligence du locataire."
                ),
            },
            {
                'numero': 7, 'titre': "Obligations du locataire",
                'texte': (
                    "Le locataire s'engage à payer le loyer et les charges aux échéances convenues, à user "
                    "paisiblement des lieux loués, à ne pas les sous-louer sans accord écrit préalable du "
                    "bailleur, et à signaler sans délai toute dégradation ou dysfonctionnement constaté."
                ),
            },
            {
                'numero': 8, 'titre': "Entretien du logement",
                'texte': (
                    "Le locataire assure l'entretien courant du logement (menues réparations, propreté, "
                    "équipements du quotidien). Le bailleur reste responsable des réparations relevant de la "
                    "structure du bâtiment ou de l'usure normale des gros équipements."
                ),
            },
            {
                'numero': 9, 'titre': "Résiliation",
                'texte': (
                    "Chaque partie peut résilier le présent contrat moyennant un préavis écrit d'au moins un "
                    "(1) mois, sauf disposition contraire prévue par la législation en vigueur ou accord "
                    "exprès entre les parties."
                ),
            },
            {
                'numero': 10, 'titre': "Retards de paiement",
                'texte': self._texte_article_retard(),
            },
        ]
        if self.conditions_speciales:
            articles.append({'numero': 11, 'titre': "Conditions particulières", 'texte': self.conditions_speciales})
        return articles

    def _texte_article_retard(self):
        lignes = [
            f"Le loyer est payable au plus tard le {self.jour_paiement} de chaque mois. En cas de retard de paiement, "
            f"les dispositions suivantes s'appliquent :",
            f"– Après {self.jours_avant_rappel} jour(s) de retard : envoi d'un rappel de paiement au locataire.",
        ]
        if self.montant_frais_retard:
            lignes.append(
                f"– Après {self.jours_avant_frais} jour(s) de retard : application de frais de retard de "
                f"{self._fcfa(self.montant_frais_retard)}."
            )
        lignes.append(
            f"– Après {self.jours_avant_mise_en_demeure} jour(s) de retard : envoi d'une mise en demeure invitant "
            f"le locataire à régulariser sa situation dans un délai fixé par le bailleur."
        )
        lignes.append(
            "En l'absence de régularisation à l'issue de ce délai, le bailleur pourra engager les démarches "
            "prévues par le présent contrat et par la législation en vigueur."
        )
        return "\n".join(lignes)

    @property
    def texte_articles_actuel(self):
        """Texte complet des articles, calculé à la volée depuis les champs
        actuels (aperçu en brouillon). Pour le texte réellement signé, voir
        `texte_contrat_signe`."""
        return "\n\n".join(f"Article {a['numero']} — {a['titre']}\n{a['texte']}" for a in self.generer_articles())


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

    # Suivi de l'escalade des retards (voir contrats.escalade) — chaque étape
    # n'est déclenchée qu'une fois, ces horodatages servent à ne pas la
    # redéclencher à chaque passage de la tâche périodique.
    date_rappel_retard_envoye = models.DateTimeField(blank=True, null=True)
    date_frais_appliques = models.DateTimeField(blank=True, null=True)
    date_alerte_grave_envoyee = models.DateTimeField(blank=True, null=True)

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

    def regulariser_mises_en_demeure(self):
        """À appeler dès que ce paiement est effectivement reçu : sans ça, une
        mise en demeure déjà envoyée reste affichée « Envoyée » indéfiniment
        côté locataire tant que sa date limite n'est pas dépassée (le seul
        endroit qui la repassait à « Régularisée » était le cron
        `verifier_expiration_mises_en_demeure`, qui n'agit qu'après coup).

        Inclut aussi `EXPIREE` : si le paiement arrive après l'échéance du
        délai (le cron a déjà fait passer la mise en demeure à « Expirée »
        avant que le locataire ne paie), elle doit quand même se régulariser
        — sinon la bannière « mise en demeure expirée » reste affichée
        indéfiniment malgré le paiement reçu."""
        self.mises_en_demeure.filter(
            statut__in=[
                MiseEnDemeure.Statut.ENVOYEE,
                MiseEnDemeure.Statut.DELAI_SUPPLEMENTAIRE,
                MiseEnDemeure.Statut.EXPIREE,
            ]
        ).update(statut=MiseEnDemeure.Statut.REGULARISEE, date_resolution=timezone.now())


class MiseEnDemeure(models.Model):
    """Mise en demeure envoyée par le propriétaire à un locataire en retard
    de paiement (au-delà de `Contrat.jours_avant_mise_en_demeure`) : une
    lettre formelle qui accorde un dernier délai de régularisation, jamais
    une saisine de la justice. L'application ne décide jamais d'engager une
    procédure — elle trace le délai et laisse le propriétaire choisir la suite
    une fois celui-ci expiré (voir `preparer_dossier_juridique`)."""

    class Statut(models.TextChoices):
        ENVOYEE = 'envoyee', 'Envoyée'
        REGULARISEE = 'regularisee', 'Régularisée'
        EXPIREE = 'expiree', 'Expirée'
        DELAI_SUPPLEMENTAIRE = 'delai_supplementaire', 'Délai supplémentaire accordé'
        CLOTUREE = 'cloturee', 'Dossier clôturé'
        PROCEDURE = 'procedure', 'Procédure contentieuse engagée'

    paiement = models.ForeignKey(Paiement, on_delete=models.CASCADE, related_name='mises_en_demeure')
    contrat = models.ForeignKey(Contrat, on_delete=models.CASCADE, related_name='mises_en_demeure')
    objet = models.CharField(max_length=255, default='Mise en demeure pour non-paiement')
    date_limite_regularisation = models.DateField()

    envoi_application = models.BooleanField(default=True)
    envoi_email = models.BooleanField(default=False)
    envoi_pdf = models.BooleanField(default=False)
    message_complementaire = models.TextField(blank=True, default='')

    statut = models.CharField(max_length=25, choices=Statut.choices, default=Statut.ENVOYEE)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_resolution = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Mise en demeure'
        verbose_name_plural = 'Mises en demeure'
        ordering = ['-date_creation']

    def __str__(self):
        return f"Mise en demeure {self.contrat.numero_contrat} — {self.date_creation.strftime('%d/%m/%Y')}"

    def texte_lettre(self):
        """Texte formel de la lettre, tel qu'envoyé/affiché au locataire."""
        proprietaire_nom = self.contrat.proprietaire.company.name if getattr(self.contrat.proprietaire, 'company', None) else (self.contrat.proprietaire.get_full_name() or self.contrat.proprietaire.username)
        locataire_nom = self.contrat.locataire.get_full_name() or self.contrat.locataire.username if self.contrat.locataire else ''
        jours_retard = (self.date_creation.date() - self.paiement.date_limite).days if self.paiement.date_limite else 0
        signature_txt = self.contrat.date_signature.strftime('%d/%m/%Y') if self.contrat.date_signature else '—'
        lignes = [
            f"Madame, Monsieur {locataire_nom},",
            "",
            (
                f"Conformément au contrat de location signé le {signature_txt}, nous constatons que votre paiement "
                f"présente un retard de {jours_retard} jour{'s' if jours_retard > 1 else ''}."
            ),
            "",
            f"Nous vous invitons à régulariser votre situation avant le {self.date_limite_regularisation.strftime('%d %B %Y')}.",
            "",
            (
                "À défaut de régularisation dans le délai indiqué, notre entreprise pourra engager les démarches "
                "prévues par le contrat et par la législation en vigueur."
            ),
        ]
        if self.message_complementaire:
            lignes += ["", self.message_complementaire]
        lignes += ["", "Cordialement,", proprietaire_nom]
        return "\n".join(lignes)


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


class Reclamation(models.Model):
    class Statut(models.TextChoices):
        OUVERTE  = 'ouverte',  'Ouverte'
        EN_COURS = 'en_cours', 'En cours'
        RESOLUE  = 'resolue',  'Résolue'
        FERMEE   = 'fermee',   'Fermée'

    class Priorite(models.TextChoices):
        NORMALE = 'normale', 'Normale'
        URGENTE = 'urgente', 'Urgente'

    bien = models.ForeignKey(
        'biens.Bien', on_delete=models.CASCADE, related_name='reclamations'
    )
    locataire = models.ForeignKey(
        Utilisateur, on_delete=models.CASCADE, related_name='reclamations_envoyees'
    )
    titre = models.CharField(max_length=200)
    description = models.TextField()
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.OUVERTE)
    priorite = models.CharField(max_length=20, choices=Priorite.choices, default=Priorite.NORMALE)
    reponse = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    mis_a_jour_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réclamation'
        verbose_name_plural = 'Réclamations'
        ordering = ['-cree_le']

    def __str__(self):
        return f"{self.titre} — {self.locataire.username}"


class EtatDesLieux(models.Model):
    """État des lieux d'entrée ou de sortie, réalisé pour un contrat."""

    class Type(models.TextChoices):
        ENTREE = 'entree', "Entrée"
        SORTIE = 'sortie', "Sortie"

    class EtatGeneral(models.TextChoices):
        BON = 'bon', 'Bon état'
        MOYEN = 'moyen', 'État moyen'
        MAUVAIS = 'mauvais', 'Mauvais état'

    contrat = models.ForeignKey(Contrat, on_delete=models.CASCADE, related_name='etats_des_lieux')
    type_etat = models.CharField(max_length=10, choices=Type.choices)
    etat_general = models.CharField(max_length=10, choices=EtatGeneral.choices, default=EtatGeneral.BON)
    observations = models.TextField(blank=True, default='')
    realise_par = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, related_name='etats_des_lieux_realises')
    date_realisation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'État des lieux'
        verbose_name_plural = 'États des lieux'
        ordering = ['-date_realisation']
        unique_together = ['contrat', 'type_etat']

    def __str__(self):
        return f"État des lieux ({self.get_type_etat_display()}) — {self.contrat.numero_contrat}"
