from django.urls import path, include
from rest_framework.routers import SimpleRouter
from . import views

router = SimpleRouter()
router.register(r'utilisateurs', views.UtilisateurViewSet, basename='utilisateur')
router.register(r'proprietaires', views.ProprietaireProfileViewSet, basename='proprietaire')
router.register(r'locataires', views.LocataireProfileViewSet, basename='locataire')

urlpatterns = [
    path('ui/', views.ui_index, name='utilisateurs_ui'),
    path('', include(router.urls)),
]
