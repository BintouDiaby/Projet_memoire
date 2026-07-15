from django.contrib import admin
from .models import MessageAssistant


@admin.register(MessageAssistant)
class MessageAssistantAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'role', 'contenu', 'date_creation')
    list_filter = ('role', 'date_creation')
    search_fields = ('utilisateur__username', 'contenu')
