from rest_framework import serializers
from .models import Contrat, Paiement, DocumentContrat
from biens.serializers import BienListSerializer
from utilisateurs.serializers import UtilisateurSerializer


class PaiementSerializer(serializers.ModelSerializer):
    """Serializer pour les paiements"""
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    
    class Meta:
        model = Paiement
        fields = [
            'id', 'contrat', 'mois', 'montant_du', 'montant_recu',
            'date_limite', 'date_paiement', 'statut', 'statut_display',
            'raison_retard', 'montant_penalites', 'date_creation'
        ]
        read_only_fields = ['id', 'date_creation']


class DocumentContratSerializer(serializers.ModelSerializer):
    """Serializer pour les documents du contrat"""
    type_document_display = serializers.CharField(source='get_type_document_display', read_only=True)
    
    class Meta:
        model = DocumentContrat
        fields = [
            'id', 'contrat', 'type_document', 'type_document_display',
            'fichier', 'date_creation'
        ]
        read_only_fields = ['id', 'date_creation']


class ContratListSerializer(serializers.ModelSerializer):
    """Serializer allégé pour lister les contrats"""
    bien = BienListSerializer(read_only=True)
    locataire = UtilisateurSerializer(read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    
    class Meta:
        model = Contrat
        fields = [
            'id', 'numero_contrat', 'bien', 'locataire', 'date_debut',
            'date_fin', 'statut', 'statut_display', 'prix_mensuel'
        ]


class ContratDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour un contrat"""
    bien = BienListSerializer(read_only=True)
    locataire = UtilisateurSerializer(read_only=True)
    proprietaire = UtilisateurSerializer(read_only=True)
    paiements = PaiementSerializer(many=True, read_only=True)
    documents = DocumentContratSerializer(many=True, read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    is_actif = serializers.SerializerMethodField()
    
    class Meta:
        model = Contrat
        fields = [
            'id', 'numero_contrat', 'bien', 'proprietaire', 'locataire',
            'date_debut', 'date_fin', 'date_signature', 'statut',
            'statut_display', 'is_actif', 'prix_mensuel', 'prix_depot_garantie',
            'charges_mensuelles', 'nombre_mois_minimum', 'jour_paiement',
            'modalites_resilition', 'conditions_speciales', 'fichier_contrat',
            'paiements', 'documents', 'date_creation'
        ]
        read_only_fields = ['id', 'date_creation']
    
    def get_is_actif(self, obj):
        return obj.is_actif()


class ContratCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour créer/modifier un contrat"""
    
    class Meta:
        model = Contrat
        fields = [
            'numero_contrat', 'bien', 'proprietaire', 'locataire',
            'date_debut', 'date_fin', 'date_signature', 'statut',
            'prix_mensuel', 'prix_depot_garantie', 'charges_mensuelles',
            'nombre_mois_minimum', 'jour_paiement', 'modalites_resilition',
            'conditions_speciales', 'fichier_contrat'
        ]
    
    def validate(self, attrs):
        if attrs['date_debut'] >= attrs['date_fin']:
            raise serializers.ValidationError(
                "La date de début doit être antérieure à la date de fin."
            )
        return attrs
