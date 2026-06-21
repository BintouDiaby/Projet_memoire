from django.urls import path, include
from rest_framework.routers import SimpleRouter
from . import views

router = SimpleRouter()
router.register(r'recherches', views.RechercheSauvegardeeViewSet, basename='recherche-sauvegardee')
router.register(r'favoris', views.BienFavoriViewSet, basename='bien-favori')
router.register(r'historique', views.HistoriqueRechercheViewSet, basename='historique-recherche')

urlpatterns = [
    path('', include(router.urls)),
        path('ui/', views.ui_index, name='recherche_ui'),
    path('avancee/', views.recherche_avancee, name='recherche-avancee'),
]
