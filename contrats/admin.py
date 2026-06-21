from django.contrib import admin
from .models import Contrat, Paiement, DocumentContrat


class PaiementInline(admin.TabularInline):
    model = Paiement
    extra = 1
    readonly_fields = ('date_creation',)


class DocumentContratInline(admin.TabularInline):
    model = DocumentContrat
    extra = 1


@admin.register(Contrat)
class ContratAdmin(admin.ModelAdmin):
    list_display = ('numero_contrat', 'bien', 'locataire', 'statut', 'date_debut', 'date_fin')
    list_filter = ('statut', 'date_debut', 'date_fin')
    search_fields = ('numero_contrat', 'bien__titre', 'locataire__username')
    inlines = [PaiementInline, DocumentContratInline]
    fieldsets = (
        ('Informations de Base', {
            'fields': ('numero_contrat', 'bien', 'proprietaire', 'locataire', 'statut')
        }),
        ('Dates', {
            'fields': ('date_debut', 'date_fin', 'date_signature')
        }),
        ('Tarification', {
            'fields': ('prix_mensuel', 'prix_depot_garantie', 'charges_mensuelles')
        }),
        ('Conditions', {
            'fields': ('nombre_mois_minimum', 'jour_paiement', 'modalites_resilition', 'conditions_speciales')
        }),
        ('Documents', {
            'fields': ('fichier_contrat',)
        }),
    )


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ('contrat', 'mois', 'montant_du', 'montant_recu', 'statut', 'date_limite')
    list_filter = ('statut', 'mois')
    search_fields = ('contrat__numero_contrat',)
    readonly_fields = ('date_creation', 'date_modification')


@admin.register(DocumentContrat)
class DocumentContratAdmin(admin.ModelAdmin):
    list_display = ('type_document', 'contrat', 'date_creation')
    list_filter = ('type_document',)
    search_fields = ('contrat__numero_contrat',)
