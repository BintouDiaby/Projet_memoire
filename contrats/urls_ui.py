from django.urls import path
from . import views

urlpatterns = [
    path('mes-locations/', views.ui_mes_locations, name='mes_locations'),
    path('nouveau/', views.contrats_nouveau, name='nouveau'),
    path('<int:contrat_id>/completer/', views.contrat_completer, name='completer'),
    path('signer/', views.contrat_signer, name='signer'),
    path('<int:contrat_id>/pdf/', views.contrat_pdf, name='pdf'),
    path('<int:contrat_id>/rappeler/', views.contrat_rappeler, name='rappeler'),
    path('<int:contrat_id>/supprimer/', views.contrat_supprimer, name='supprimer'),
    path('<int:contrat_id>/archiver/', views.contrat_archiver, name='archiver'),
    path('<int:contrat_id>/resilier/', views.contrat_resilier, name='resilier'),
    path('reclamation/<int:bien_id>/', views.reclamation_creer, name='reclamation_creer'),
    path('mes-reclamations/', views.mes_reclamations, name='mes_reclamations'),
    path('<int:contrat_id>/etat-des-lieux/<str:type_etat>/', views.etat_des_lieux_creer, name='etat_des_lieux_creer'),
    path('<int:contrat_id>/caution/', views.caution_traiter, name='caution_traiter'),
    path('paiement/<int:paiement_id>/mise-en-demeure/', views.envoyer_mise_en_demeure, name='envoyer_mise_en_demeure'),
    path('mise-en-demeure/<int:mise_id>/gerer/', views.gerer_mise_en_demeure, name='gerer_mise_en_demeure'),
    path('mise-en-demeure/<int:mise_id>/pdf/', views.mise_en_demeure_pdf, name='mise_en_demeure_pdf'),
    path('<int:contrat_id>/dossier-juridique/', views.preparer_dossier_juridique, name='dossier_juridique'),
    path('', views.ui_list, name='list'),
    path('<int:pk>/', views.ui_detail, name='detail'),
    path('<int:pk>/suivi/', views.contrat_suivi, name='suivi'),
]
