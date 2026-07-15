from django.db import models
from utilisateurs.models import Utilisateur


class MessageAssistant(models.Model):
    """Historique de la conversation avec l'assistant IA — un fil continu par
    utilisateur (pas de notion de conversations multiples nommées)."""

    class Role(models.TextChoices):
        USER = 'user', 'Utilisateur'
        ASSISTANT = 'assistant', 'Assistant'

    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name='messages_assistant')
    role = models.CharField(max_length=10, choices=Role.choices)
    contenu = models.TextField()
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date_creation']
        verbose_name = 'Message assistant IA'

    def __str__(self):
        return f"[{self.role}] {self.utilisateur.username}: {self.contenu[:40]}"
