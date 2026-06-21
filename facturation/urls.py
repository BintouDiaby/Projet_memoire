from django.urls import path, include
from rest_framework.routers import SimpleRouter
from . import views

router = SimpleRouter()
router.register(r'factures', views.FactureViewSet, basename='facture')
router.register(r'notifications', views.NotificationViewSet, basename='notification')
router.register(r'rappels', views.RappelPaiementViewSet, basename='rappel-paiement')

urlpatterns = [
    path('ui/', views.ui_index, name='facturation_ui'),
    path('', include(router.urls)),
]
