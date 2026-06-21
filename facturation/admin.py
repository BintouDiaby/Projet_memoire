from django.contrib import admin
from .models import Facture, Notification, RappelPaiement


@admin.register(Facture)
class FactureAdmin(admin.ModelAdmin):
    list_display = ('numero_facture', 'contrat', 'montant_total', 'statut', 'date_echéance')
    list_filter = ('statut', 'date_echéance', 'date_generation')
    search_fields = ('numero_facture', 'contrat__numero_contrat')
    readonly_fields = ('id_unique', 'date_generation', 'date_modification')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('titre', 'utilisateur', 'type_notification', 'statut', 'date_creation')
    list_filter = ('statut', 'type_notification', 'date_creation')
    search_fields = ('utilisateur__username', 'titre')
    readonly_fields = ('date_creation', 'date_envoi', 'date_lecture')


@admin.register(RappelPaiement)
class RappelPaiementAdmin(admin.ModelAdmin):
    list_display = ('type_rappel', 'paiement', 'date_programmee', 'est_envoye')
    list_filter = ('type_rappel', 'est_envoye', 'date_programmee')
    search_fields = ('paiement__contrat__numero_contrat',)
