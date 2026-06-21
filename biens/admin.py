from django.contrib import admin
from .models import Bien, PhotoBien, Visite


class PhotoBienInline(admin.TabularInline):
    model = PhotoBien
    extra = 1


@admin.register(Bien)
class BienAdmin(admin.ModelAdmin):
    list_display = ('titre', 'ville', 'type_bien', 'prix_mensuel', 'statut')
    list_filter = ('statut', 'type_bien', 'ville', 'date_creation')
    search_fields = ('titre', 'adresse', 'ville')
    inlines = [PhotoBienInline]
    fieldsets = (
        ('Informations Basiques', {
            'fields': ('titre', 'description', 'type_bien', 'statut')
        }),
        ('Localisation', {
            'fields': ('adresse', 'ville', 'code_postal', 'pays', 'latitude', 'longitude')
        }),
        ('Caractéristiques', {
            'fields': ('surface_m2', 'nombre_chambres', 'nombre_salles_bain', 'nombre_etages')
        }),
        ('Tarification', {
            'fields': ('prix_mensuel', 'prix_depot_garantie', 'charges_incluses')
        }),
        ('Équipements & Conditions', {
            'fields': ('equipements', 'animaux_autorises', 'fumeurs_acceptes')
        }),
        ('Médias', {
            'fields': ('photo_principale',)
        }),
        ('Propriétaire', {
            'fields': ('proprietaire',)
        }),
    )


@admin.register(PhotoBien)
class PhotoBienAdmin(admin.ModelAdmin):
    list_display = ('bien', 'ordre', 'date_ajout')
    list_filter = ('bien__ville',)


@admin.register(Visite)
class VisiteAdmin(admin.ModelAdmin):
    list_display = ('bien', 'locataire', 'date_visite', 'interet')
    list_filter = ('interet', 'date_reservation')
    search_fields = ('bien__titre', 'locataire__username')
