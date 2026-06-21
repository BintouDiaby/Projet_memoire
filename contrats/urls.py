from django.urls import path, include
from rest_framework.routers import SimpleRouter
from . import views

router = SimpleRouter()
router.register(r'contrats', views.ContratViewSet, basename='contrat')
router.register(r'paiements', views.PaiementViewSet, basename='paiement')

urlpatterns = [
    path('ui/', views.ui_index, name='contrats_ui'),
    path('', include(router.urls)),
]
