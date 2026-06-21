from rest_framework import serializers
from .models import (
    StatistiquesProprietaire, TableauBordLocataire, AlerteSysteme,
    LogActivite, RapportMensuel, ConfigurationDashboard
)
from utilisateurs.serializers import UtilisateurSerializer


class StatistiquesProprietaireSerializer(serializers.ModelSerializer):
    """Serializer pour les statistiques propriétaire"""
    proprietaire = UtilisateurSerializer(read_only=True)
    
    class Meta:
        model = StatistiquesProprietaire
        fields = [
            'id', 'proprietaire', 'nombre_proprietes', 'nombre_contrats_actifs',
            'nombre_locataires', 'revenu_mensuel_total', 'revenu_annuel_estime',
            'revenu_recu_ce_mois', 'montant_impaye', 'nombre_contrats_avec_impaye',
            'taux_collecte_pourcentage', 'date_derniere_mise_a_jour'
        ]
        read_only_fields = ['id', 'date_derniere_mise_a_jour']


class TableauBordLocataireSerializer(serializers.ModelSerializer):
    """Serializer pour les données du tableau de bord locataire"""
    locataire = UtilisateurSerializer(read_only=True)
    
    class Meta:
        model = TableauBordLocataire
        fields = [
            'id', 'locataire', 'nombre_contrats_actifs',
            'nombre_recherches_sauvegardees', 'prochain_paiement_date',
            'prochain_paiement_montant', 'paiements_en_retard',
            'montant_en_retard', 'nombre_biens_favoris',
            'nombre_visites_programmees', 'date_derniere_mise_a_jour'
        ]
        read_only_fields = ['id', 'date_derniere_mise_a_jour']


class AlerteSystemeSerializer(serializers.ModelSerializer):
    """Serializer pour les alertes système"""
    severite_display = serializers.CharField(source='get_severite_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    utilisateurs_specifiques = UtilisateurSerializer(many=True, read_only=True)
    
    class Meta:
        model = AlerteSysteme
        fields = [
            'id', 'titre', 'message', 'severite', 'severite_display',
            'statut', 'statut_display', 'tout_le_monde', 'proprietaires',
            'locataires', 'utilisateurs_specifiques', 'date_creation',
            'date_expiration', 'date_resolution'
        ]
        read_only_fields = ['id', 'date_creation']


class LogActiviteSerializer(serializers.ModelSerializer):
    """Serializer pour les logs d'activité"""
    utilisateur = UtilisateurSerializer(read_only=True)
    type_display = serializers.CharField(source='get_type_activite_display', read_only=True)
    
    class Meta:
        model = LogActivite
        fields = [
            'id', 'utilisateur', 'type_activite', 'type_display',
            'description', 'details_json', 'adresse_ip', 'user_agent',
            'date_activite'
        ]
        read_only_fields = ['id', 'date_activite']


class RapportMensuelSerializer(serializers.ModelSerializer):
    """Serializer pour les rapports mensuels"""
    proprietaire = UtilisateurSerializer(read_only=True)
    
    class Meta:
        model = RapportMensuel
        fields = [
            'id', 'proprietaire', 'mois', 'nombre_proprietes',
            'nombre_contrats_actifs', 'nombre_locataires', 'revenu_attendu',
            'revenu_recu', 'montant_impaye', 'taux_collecte',
            'date_generation', 'fichier_pdf'
        ]
        read_only_fields = ['id', 'date_generation']


class ConfigurationDashboardSerializer(serializers.ModelSerializer):
    """Serializer pour la configuration du dashboard"""
    utilisateur = UtilisateurSerializer(read_only=True)
    
    class Meta:
        model = ConfigurationDashboard
        fields = [
            'id', 'utilisateur', 'afficher_revenus', 'afficher_contrats',
            'afficher_alertes', 'afficher_historique', 'notifications_email_activees',
            'notifier_paiement_recu', 'notifier_impaye', 'notifier_new_demande',
            'langue', 'theme', 'widgets_actifs', 'date_modification'
        ]
        read_only_fields = ['id', 'date_modification']
