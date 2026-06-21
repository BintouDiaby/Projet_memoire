from django.contrib import admin
from .models import (
    StatistiquesProprietaire, TableauBordLocataire, AlerteSysteme,
    LogActivite, RapportMensuel, ConfigurationDashboard
)


@admin.register(StatistiquesProprietaire)
class StatistiquesProprietaireAdmin(admin.ModelAdmin):
    list_display = ('proprietaire', 'nombre_proprietes', 'nombre_contrats_actifs', 'revenu_mensuel_total', 'taux_collecte_pourcentage')
    list_filter = ('date_derniere_mise_a_jour',)
    search_fields = ('proprietaire__username',)
    readonly_fields = ('date_derniere_mise_a_jour',)


@admin.register(TableauBordLocataire)
class TableauBordLocataireAdmin(admin.ModelAdmin):
    list_display = ('locataire', 'nombre_contrats_actifs', 'nombre_recherches_sauvegardees', 'paiements_en_retard')
    list_filter = ('date_derniere_mise_a_jour',)
    search_fields = ('locataire__username',)
    readonly_fields = ('date_derniere_mise_a_jour',)


@admin.register(AlerteSysteme)
class AlerteSystemeAdmin(admin.ModelAdmin):
    list_display = ('titre', 'severite', 'statut', 'date_creation')
    list_filter = ('severite', 'statut', 'date_creation')
    search_fields = ('titre', 'message')
    filter_horizontal = ('utilisateurs_specifiques',)


@admin.register(LogActivite)
class LogActiviteAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'type_activite', 'date_activite', 'adresse_ip')
    list_filter = ('type_activite', 'date_activite')
    search_fields = ('utilisateur__username', 'description')
    readonly_fields = ('date_activite',)


@admin.register(RapportMensuel)
class RapportMensuelAdmin(admin.ModelAdmin):
    list_display = ('proprietaire', 'mois', 'revenu_recu', 'revenu_attendu', 'taux_collecte')
    list_filter = ('mois', 'proprietaire')
    search_fields = ('proprietaire__username',)
    readonly_fields = ('date_generation',)


@admin.register(ConfigurationDashboard)
class ConfigurationDashboardAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'theme', 'langue', 'date_modification')
    list_filter = ('theme', 'langue')
    search_fields = ('utilisateur__username',)
