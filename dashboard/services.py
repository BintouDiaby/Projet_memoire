"""Point d'entrée unique pour créer des notifications utilisateur.

Au lieu d'appeler `Notification.objects.create(...)` depuis chaque vue
métier (message, visite, devis, réclamation...), on appelle
`NotificationService.send(...)`. Ça centralise la création et laisse un seul
endroit à modifier plus tard (email, push, temps réel) sans toucher aux vues
qui déclenchent l'action.
"""
from .models import Notification


class NotificationService:

    @staticmethod
    def send(destinataire, type_notification, titre, message='', lien='', expediteur=None):
        """Crée une notification pour `destinataire`. Ne fait rien de plus pour
        l'instant (pas d'email/push/temps réel) — c'est le point à étendre
        plus tard si besoin, sans changer les appelants."""
        if destinataire is None:
            return None
        return Notification.objects.create(
            destinataire=destinataire,
            expediteur=expediteur,
            type_notification=type_notification,
            titre=titre,
            message=message,
            lien=lien,
        )

    @staticmethod
    def unread_count(user):
        from construction.models import NotificationConstruction
        return (
            Notification.objects.filter(destinataire=user, lue=False).count()
            + NotificationConstruction.objects.filter(destinataire=user, lue=False).count()
        )

    @staticmethod
    def mark_all_read(user):
        from construction.models import NotificationConstruction
        Notification.objects.filter(destinataire=user, lue=False).update(lue=True)
        NotificationConstruction.objects.filter(destinataire=user, lue=False).update(lue=True)

    @staticmethod
    def mark_read(user, notification_id):
        Notification.objects.filter(destinataire=user, id=notification_id).update(lue=True)

    @staticmethod
    def mark_read_construction(user, notification_id):
        from construction.models import NotificationConstruction
        NotificationConstruction.objects.filter(destinataire=user, id=notification_id).update(lue=True)

    @staticmethod
    def delete(user, notification_id):
        Notification.objects.filter(destinataire=user, id=notification_id).delete()
