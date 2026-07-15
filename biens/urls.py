from django.urls import path, include
from rest_framework.routers import SimpleRouter
from . import views

router = SimpleRouter()
router.register(r'biens', views.BienViewSet, basename='bien')
router.register(r'photos', views.PhotoBienViewSet, basename='photo')
router.register(r'visites', views.VisiteViewSet, basename='visite')
router.register(r'reservations', views.ReservationViewSet, basename='reservation')

urlpatterns = [
    path('ui/', views.ui_index, name='biens_ui'),
    path('', include(router.urls)),
]
