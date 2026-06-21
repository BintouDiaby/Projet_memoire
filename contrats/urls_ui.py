from django.urls import path
from . import views

urlpatterns = [
    path('mes-locations/', views.ui_mes_locations, name='mes_locations'),
    path('', views.ui_list, name='list'),
    path('<int:pk>/', views.ui_detail, name='detail'),
]
