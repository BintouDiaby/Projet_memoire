from django.urls import path
from . import views

urlpatterns = [
    path('mes-locations/', views.ui_mes_locations, name='mes_locations'),
    path('nouveau/', views.contrats_nouveau, name='nouveau'),
    path('reclamation/<int:bien_id>/', views.reclamation_creer, name='reclamation_creer'),
    path('mes-reclamations/', views.mes_reclamations, name='mes_reclamations'),
    path('<int:contrat_id>/etat-des-lieux/<str:type_etat>/', views.etat_des_lieux_creer, name='etat_des_lieux_creer'),
    path('<int:contrat_id>/caution/', views.caution_traiter, name='caution_traiter'),
    path('', views.ui_list, name='list'),
    path('<int:pk>/', views.ui_detail, name='detail'),
    path('<int:pk>/suivi/', views.contrat_suivi, name='suivi'),
]
