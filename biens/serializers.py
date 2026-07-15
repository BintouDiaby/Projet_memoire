from rest_framework import serializers
from .models import Bien, PhotoBien, Visite, Reservation
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
    """Serializer pour les visites.

    Correction (app mobile) : `bien_id` écrivable était absent — `bien`
    étant déclaré read_only sans contrepartie écrivable, toute création
    échouait avec une IntegrityError (colonne bien_id NULL). `statut` était
    aussi absent, empêchant tout affichage/changement de statut côté client
    (demandes de visite en attente, accepter/refuser)."""
    locataire = UtilisateurSerializer(read_only=True)
    bien = BienListSerializer(read_only=True)
    bien_id = serializers.PrimaryKeyRelatedField(
        source='bien', queryset=Bien.objects.all(), write_only=True
    )
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)

    class Meta:
        model = Visite
        fields = [
            'id', 'bien', 'bien_id', 'locataire', 'date_visite', 'notes',
            'interet', 'statut', 'statut_display', 'date_reservation'
        ]
        read_only_fields = ['id', 'statut', 'date_reservation']


class ReservationSerializer(serializers.ModelSerializer):
    """Serializer pour les réservations (app mobile — le modèle `Reservation`
    existait déjà mais n'avait aucune route DRF)."""
    bien = BienListSerializer(read_only=True)
    bien_id = serializers.PrimaryKeyRelatedField(
        source='bien', queryset=Bien.objects.all(), write_only=True
    )
    client = UtilisateurSerializer(read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    hold_actif = serializers.BooleanField(read_only=True)

    class Meta:
        model = Reservation
        fields = [
            'id', 'bien', 'bien_id', 'client', 'statut', 'statut_display',
            'sans_visite', 'date_expiration', 'montant_acompte', 'notes',
            'hold_actif', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'id', 'statut', 'date_expiration', 'hold_actif',
            'date_creation', 'date_modification',
        ]
