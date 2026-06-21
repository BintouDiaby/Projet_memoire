from rest_framework import serializers
from .models import RechercheSauvegardee, BienFavori, HistoriqueRecherche
from biens.serializers import BienListSerializer
from utilisateurs.serializers import UtilisateurSerializer


class RechercheSauvegardeeSerializer(serializers.ModelSerializer):
    """Serializer pour les recherches sauvegardées"""
    utilisateur = UtilisateurSerializer(read_only=True)
    
    class Meta:
        model = RechercheSauvegardee
        fields = [
            'id', 'utilisateur', 'nom', 'villes', 'budget_min', 'budget_max',
            'nombre_chambres_min', 'nombre_chambres_max', 'surface_min',
            'types_bien', 'equipements', 'animaux_autorises',
            'date_creation', 'date_derniere_recherche', 'nombre_utilisations'
        ]
        read_only_fields = ['id', 'date_creation', 'date_derniere_recherche', 'nombre_utilisations']


class BienFavoriSerializer(serializers.ModelSerializer):
    """Serializer pour les biens favoris"""
    bien = BienListSerializer(read_only=True)
    bien_id = serializers.PrimaryKeyRelatedField(
        write_only=True,
        queryset=__import__('biens.models', fromlist=['Bien']).Bien.objects.all()
    )
    utilisateur = UtilisateurSerializer(read_only=True)
    
    class Meta:
        model = BienFavori
        fields = [
            'id', 'utilisateur', 'bien', 'bien_id', 'note', 'commentaire',
            'date_ajout'
        ]
        read_only_fields = ['id', 'date_ajout']


class HistoriqueRechercheSerializer(serializers.ModelSerializer):
    """Serializer pour l'historique des recherches"""
    utilisateur = UtilisateurSerializer(read_only=True)
    
    class Meta:
        model = HistoriqueRecherche
        fields = [
            'id', 'utilisateur', 'requete', 'nombre_resultats', 'date_recherche'
        ]
        read_only_fields = ['id', 'date_recherche']
