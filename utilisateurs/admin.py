from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Utilisateur, ProprietaireProfile, LocataireProfile


@admin.register(Utilisateur)
class UtilisateurAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'email_verifie', 'documents_verifies')
    list_filter = ('role', 'email_verifie', 'documents_verifies', 'date_creation')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Informations Professionnelles', {
            'fields': ('role', 'telephone', 'adresse', 'ville', 'code_postal')
        }),
        ('Statut', {
            'fields': ('email_verifie', 'documents_verifies')
        }),
        ('Profil', {
            'fields': ('photo_profil', 'bio')
        }),
    )


@admin.register(ProprietaireProfile)
class ProprietaireProfileAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'nom_entreprise', 'certification', 'nombre_proprietes')
    list_filter = ('certification',)
    search_fields = ('utilisateur__username', 'nom_entreprise')


@admin.register(LocataireProfile)
class LocataireProfileAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'budget_max_mensuel', 'localisation_preferee')
    list_filter = ('budget_max_mensuel',)
    search_fields = ('utilisateur__username',)
