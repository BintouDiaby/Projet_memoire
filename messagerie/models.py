from django.db import models
from django.db.models import Q
from utilisateurs.models import Utilisateur
from biens.models import Bien


class Conversation(models.Model):

    class Phase(models.TextChoices):
        COMMERCIAL = 'commercial', 'Commercial'
        LOCATAIRE  = 'locataire',  'Locataire'
        SAV        = 'sav',        'SAV / Après achat'

    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, null=True, blank=True, related_name='conversations')
    # FK vers ProjetConstruction — string reference pour éviter import circulaire
    projet = models.ForeignKey(
        'construction.ProjetConstruction', on_delete=models.CASCADE,
        null=True, blank=True, related_name='conversations'
    )
    demandeur = models.ForeignKey(
        Utilisateur, on_delete=models.CASCADE, related_name='conversations_envoyees'
    )
    proprietaire = models.ForeignKey(
        Utilisateur, on_delete=models.CASCADE, related_name='conversations_recues'
    )
    phase = models.CharField(max_length=20, choices=Phase.choices, default=Phase.COMMERCIAL)
    cree_le = models.DateTimeField(auto_now_add=True)
    mis_a_jour_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-mis_a_jour_le']
        constraints = [
            models.UniqueConstraint(
                fields=['bien', 'demandeur'],
                condition=Q(bien__isnull=False),
                name='unique_bien_demandeur'
            ),
            models.UniqueConstraint(
                fields=['projet', 'demandeur'],
                condition=Q(projet__isnull=False),
                name='unique_projet_demandeur'
            ),
        ]
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'

    def __str__(self):
        if self.bien:
            return f"{self.demandeur.username} — {self.bien.titre}"
        if self.projet:
            return f"{self.demandeur.username} — Projet {self.projet.get_type_projet_display()}"
        return f"{self.demandeur.username} — conversation {self.id}"

    @property
    def sujet(self):
        if self.bien:
            return self.bien.titre
        if self.projet:
            return f"Projet {self.projet.get_type_projet_display()}"
        return "Conversation"

    def nb_non_lus_pour(self, user):
        return self.messages.filter(lu=False).exclude(expediteur=user).count()

    def dernier_message(self):
        return self.messages.order_by('-cree_le').first()


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    expediteur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name='messages_envoyes')
    contenu = models.TextField()
    lu = models.BooleanField(default=False)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['cree_le']
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'

    def __str__(self):
        return f"{self.expediteur.username}: {self.contenu[:60]}"
