from rest_framework import serializers
from .models import Facture, Notification, RappelPaiement
from contrats.serializers import ContratListSerializer


class FactureSerializer(serializers.ModelSerializer):
    """Serializer pour les factures"""
    contrat = ContratListSerializer(read_only=True)
    contrat_id = serializers.PrimaryKeyRelatedField(
        write_only=True,
        queryset=Facture.objects.none()
    )
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    
    class Meta:
        model = Facture
        fields = [
            'id', 'id_unique', 'numero_facture', 'contrat', 'contrat_id',
            'date_generation', 'date_emission', 'date_echéance', 'date_paiement',
            'montant_loyer', 'montant_charges', 'montant_autres', 'montant_taxe',
            'montant_total', 'description', 'notes', 'statut', 'statut_display',
            'fichier_pdf', 'tentatives_envoi', 'dernier_envoi'
        ]
        read_only_fields = [
            'id', 'id_unique', 'numero_facture', 'date_generation',
            'date_modification'
        ]


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer pour les notifications"""
    facture = FactureSerializer(read_only=True)
    facture_id = serializers.PrimaryKeyRelatedField(
        write_only=True,
        queryset=Facture.objects.all()
    )
    type_display = serializers.CharField(source='get_type_notification_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'facture', 'facture_id', 'utilisateur', 'type_notification',
            'type_display', 'titre', 'message', 'statut', 'statut_display',
            'date_creation', 'date_envoi', 'date_lecture', 'message_erreur'
        ]
        read_only_fields = ['id', 'date_creation', 'date_envoi', 'date_lecture']


class RappelPaiementSerializer(serializers.ModelSerializer):
    """Serializer pour les rappels de paiement"""
    paiement = serializers.StringRelatedField(read_only=True)
    type_display = serializers.CharField(source='get_type_rappel_display', read_only=True)
    
    class Meta:
        model = RappelPaiement
        fields = [
            'id', 'paiement', 'type_rappel', 'type_display',
            'date_programmee', 'date_envoi_reel', 'est_envoye'
        ]
        read_only_fields = ['id', 'date_envoi_reel']
