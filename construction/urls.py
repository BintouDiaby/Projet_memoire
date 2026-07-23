from django.urls import path
from . import views

app_name = 'construction'

urlpatterns = [
    path('', views.liste_entreprises, name='liste'),
    path('entreprise/<int:company_id>/', views.profil_entreprise, name='profil_entreprise'),
    path('interesse/<int:company_id>/', views.demander_contact_construction, name='demander_contact'),
    path('devis/<int:projet_id>/', views.demande_devis, name='demande_devis'),
    path('mes-projets/', views.mes_projets, name='mes_projets'),
    path('projet/<int:projet_id>/', views.projet_detail, name='projet_detail'),
    path('dashboard/', views.dashboard_construction, name='dashboard'),
    path('etape/<int:etape_id>/update/', views.mettre_a_jour_etape, name='update_etape'),
    path('projet/<int:projet_id>/statut/', views.changer_statut_projet, name='statut_projet'),
    path('projet/<int:projet_id>/rdv/', views.gerer_rdv, name='gerer_rdv'),
    path('projet/<int:projet_id>/rdv/confirmer/', views.confirmer_rdv, name='confirmer_rdv'),
    path('projet/<int:projet_id>/rdv/annuler/', views.annuler_rdv, name='annuler_rdv'),
    path('notifs/lues/', views.marquer_notifs_lues, name='notifs_lues'),
    path('projet/<int:projet_id>/devis/preparer/', views.devis_preparer, name='devis_preparer'),
    path('devis/<int:devis_id>/repondre/', views.devis_repondre, name='devis_repondre'),
    path('devis/<int:devis_id>/pdf/', views.devis_pdf, name='devis_pdf'),
    path('mon-profil/', views.gerer_profil, name='gerer_profil'),
    path('mon-profil/realisation/ajouter/', views.realisation_ajouter, name='realisation_ajouter'),
    path('mon-profil/realisation/<int:realisation_id>/modifier/', views.realisation_modifier, name='realisation_modifier'),
    path('mon-profil/realisation/<int:realisation_id>/supprimer/', views.realisation_supprimer, name='realisation_supprimer'),
]
