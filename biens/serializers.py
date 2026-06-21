from rest_framework import serializers
from .models import Bien, PhotoBien, Visite
from utilisateurs.serializers import UtilisateurSerializer


class PhotoBienSerializer(serializers.ModelSerializer):
    """Serializer pour les photos des biens"""
    
    class Meta:
        model = PhotoBien
        fields = ['id', 'bien', 'photo', 'description', 'ordre', 'date_ajout']
        read_only_fields = ['id', 'date_ajout']


class BienListSerializer(serializers.ModelSerializer):
    """Serializer allégé pour lister les biens"""
    proprietaire = UtilisateurSerializer(read_only=True)
    type_bien_display = serializers.CharField(source='get_type_bien_display', read_only=True)
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    
    class Meta:
        model = Bien
        fields = [
            'id', 'titre', 'description', 'type_bien', 'type_bien_display',
            'transaction_type', 'transaction_type_display',
            'statut', 'statut_display', 'adresse', 'ville', 'code_postal',
            'surface_m2', 'nombre_chambres', 'nombre_salles_bain',
            'prix_mensuel', 'photo_principale', 'proprietaire',
            'date_publication'
        ]


class BienDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour un bien"""
    proprietaire = UtilisateurSerializer(read_only=True)
    photos = PhotoBienSerializer(many=True, read_only=True)
    type_bien_display = serializers.CharField(source='get_type_bien_display', read_only=True)
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    
    class Meta:
        model = Bien
        fields = [
            'id', 'titre', 'description', 'type_bien', 'type_bien_display',
            'transaction_type', 'transaction_type_display',
            'statut', 'statut_display', 'adresse', 'ville', 'code_postal',
            'pays', 'latitude', 'longitude', 'surface_m2', 'nombre_chambres',
            'nombre_salles_bain', 'nombre_etages', 'prix_mensuel',
            'prix_depot_garantie', 'charges_incluses', 'equipements',
            'animaux_autorises', 'fumeurs_acceptes', 'photo_principale',
            'photos', 'proprietaire', 'date_creation', 'date_publication'
        ]
        read_only_fields = ['id', 'date_creation']


class BienCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour créer/modifier un bien"""
    
    class Meta:
        model = Bien
        fields = [
            'titre', 'description', 'type_bien', 'statut', 'adresse',
            'transaction_type',
            'ville', 'code_postal', 'pays', 'latitude', 'longitude',
            'surface_m2', 'nombre_chambres', 'nombre_salles_bain',
            'nombre_etages', 'prix_mensuel', 'prix_depot_garantie',
            'charges_incluses', 'equipements', 'animaux_autorises',
            'fumeurs_acceptes', 'photo_principale'
        ]


class VisiteSerializer(serializers.ModelSerializer):
    """Serializer pour les visites"""
    locataire = UtilisateurSerializer(read_only=True)
    bien = BienListSerializer(read_only=True)
    
    class Meta:
        model = Visite
        fields = [
            'id', 'bien', 'locataire', 'date_visite', 'notes',
            'interet', 'date_reservation'
        ]
        read_only_fields = ['id', 'date_reservation']
