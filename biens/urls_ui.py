from django.urls import path
from . import views

urlpatterns = [
    path('', views.ui_list, name='list'),
    path('publier/', views.publier_bien, name='publier'),
    path('ajouter/<str:operation>/', views.ajouter_bien_module, name='ajouter'),
    path('create/', views.ui_create, name='create'),
    path('<int:pk>/', views.ui_detail, name='detail'),
    path('<int:pk>/edit/', views.ui_update, name='edit'),
    path('<int:pk>/delete/', views.ui_delete, name='delete'),
]
