from django.contrib import admin
from .models import RechercheSauvegardee, BienFavori, HistoriqueRecherche


@admin.register(RechercheSauvegardee)
class RechercheSauvegardeeAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'nom', 'date_derniere_recherche', 'nombre_utilisations')
    list_filter = ('date_creation',)
    search_fields = ('utilisateur__username', 'nom')


@admin.register(BienFavori)
class BienFavoriAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'bien', 'note', 'date_ajout')
    list_filter = ('note', 'date_ajout')
    search_fields = ('utilisateur__username', 'bien__titre')


@admin.register(HistoriqueRecherche)
class HistoriqueRechercheAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'requete', 'nombre_resultats', 'date_recherche')
    list_filter = ('date_recherche',)
    search_fields = ('utilisateur__username', 'requete')
