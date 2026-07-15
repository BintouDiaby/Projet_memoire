from django.urls import path
from . import views

app_name = 'assistant'

urlpatterns = [
    path('historique/', views.historique, name='historique'),
    path('vider/', views.vider, name='vider'),
    path('chat/', views.chat, name='chat'),
    path('action/', views.action, name='action'),
    path('recherche-logement/', views.recherche_logement, name='recherche_logement'),
    path('recherche-client/', views.recherche_client, name='recherche_client'),
]
