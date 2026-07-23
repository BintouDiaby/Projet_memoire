from rest_framework import serializers

from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    """Un message tel que renvoyé à l'app mobile."""
    expediteur_id = serializers.IntegerField(read_only=True)
    expediteur_nom = serializers.SerializerMethodField()
    moi = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'expediteur_id', 'expediteur_nom', 'moi', 'contenu',
            'lu', 'est_modifie', 'est_supprime', 'cree_le',
        ]
        read_only_fields = fields

    def get_expediteur_nom(self, obj) -> str:
        return obj.expediteur.get_full_name() or obj.expediteur.username

    def get_moi(self, obj) -> bool:
        request = self.context.get('request')
        return bool(request and obj.expediteur_id == request.user.id)


class MessageCreateSerializer(serializers.Serializer):
    """Entrée pour l'envoi d'un message."""
    contenu = serializers.CharField()

    def validate_contenu(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError("Le message ne peut pas être vide.")
        return value


class ConversationSerializer(serializers.ModelSerializer):
    """Une conversation vue du côté de l'utilisateur courant (interlocuteur =
    l'autre partie, non-lus comptés pour lui)."""
    sujet = serializers.CharField(read_only=True)
    bien_id = serializers.IntegerField(read_only=True, allow_null=True)
    phase = serializers.CharField(read_only=True)
    interlocuteur_id = serializers.SerializerMethodField()
    interlocuteur_nom = serializers.SerializerMethodField()
    dernier_message = serializers.SerializerMethodField()
    nb_non_lus = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id', 'sujet', 'bien_id', 'phase',
            'interlocuteur_id', 'interlocuteur_nom',
            'dernier_message', 'nb_non_lus',
            'cree_le', 'mis_a_jour_le',
        ]

    def _user(self):
        request = self.context.get('request')
        return request.user if request else None

    def _interlocuteur(self, obj):
        user = self._user()
        if user and user.id == obj.demandeur_id:
            return obj.proprietaire
        return obj.demandeur

    def get_interlocuteur_id(self, obj) -> int:
        return self._interlocuteur(obj).id

    def get_interlocuteur_nom(self, obj) -> str:
        interlo = self._interlocuteur(obj)
        company = getattr(interlo, 'company', None)
        return (getattr(company, 'name', None) or interlo.get_full_name() or interlo.username)

    def get_dernier_message(self, obj) -> dict:
        m = obj.messages.order_by('-cree_le').first()
        if not m:
            return None
        return {
            'contenu': '(message supprimé)' if m.est_supprime else m.contenu[:120],
            'cree_le': m.cree_le,
            'de_moi': bool(self._user() and m.expediteur_id == self._user().id),
        }

    def get_nb_non_lus(self, obj) -> int:
        user = self._user()
        return obj.nb_non_lus_pour(user) if user else 0
