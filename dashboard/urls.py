from django.urls import path, include
from rest_framework.routers import SimpleRouter
from . import views

router = SimpleRouter()
router.register(r'alertes', views.AlerteSystemeViewSet, basename='alerte-systeme')
router.register(r'logs', views.LogActiviteViewSet, basename='log-activite')
router.register(r'config', views.ConfigurationDashboardViewSet, basename='config-dashboard')

urlpatterns = [
    path('', include(router.urls)),
    path('proprietaire/', views.dashboard_proprietaire, name='dashboard-proprietaire'),
    path('locataire/', views.dashboard_locataire, name='dashboard-locataire'),
    path('rapport-mensuel/', views.rapport_mensuel, name='rapport-mensuel'),
]
