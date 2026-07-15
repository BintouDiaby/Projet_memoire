from django.urls import path
from . import views

app_name = 'messagerie'

urlpatterns = [
    path('', views.mes_conversations, name='mes_conversations'),
    path('dashboard/', views.dashboard_messages, name='dashboard_messages'),
    path('<int:conv_id>/', views.conversation_detail, name='conversation'),
    path('<int:conv_id>/messages/', views.api_nouveaux_messages, name='api_messages'),
    path('<int:conv_id>/phase/', views.changer_phase, name='changer_phase'),
    path('<int:conv_id>/archiver/', views.conversation_archiver, name='conversation_archiver'),
    path('message/<int:message_id>/modifier/', views.message_modifier, name='message_modifier'),
    path('message/<int:message_id>/supprimer/', views.message_supprimer, name='message_supprimer'),
    path('<int:conv_id>/client/<int:user_id>/', views.fiche_client, name='fiche_client'),
    path('nouveau/<int:bien_id>/', views.nouvelle_conversation, name='nouvelle_conversation'),
    path('visite/<int:visite_id>/gerer/', views.gerer_visite, name='gerer_visite'),
]
