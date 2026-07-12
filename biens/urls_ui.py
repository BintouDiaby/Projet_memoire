from django.urls import path
from . import views

urlpatterns = [
    path('', views.ui_list, name='list'),
    path('publier/', views.publier_bien, name='publier'),
    path('ajouter/<str:operation>/', views.ajouter_bien_module, name='ajouter'),
    path('create/', views.ui_create, name='create'),
    path('mes-visites/', views.mes_visites, name='mes_visites'),
    path('mes-visites/<int:visite_id>/annuler/', views.annuler_visite, name='annuler_visite'),
    path('mes-reservations/', views.mes_reservations, name='mes_reservations'),
    path('mes-reservations/<int:reservation_id>/annuler/', views.annuler_reservation, name='annuler_reservation'),
    path('reserver/<int:bien_id>/', views.reserver_bien, name='reserver'),
    path('<int:pk>/', views.ui_detail, name='detail'),
    path('<int:pk>/gerer/', views.ui_gerer, name='gerer'),
    path('<int:pk>/edit/', views.ui_update, name='edit'),
    path('<int:pk>/delete/', views.ui_delete, name='delete'),
]
