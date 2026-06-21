from django.urls import path
from . import views

urlpatterns = [
    path('', views.ui_list, name='list'),
    path('<int:pk>/', views.ui_detail, name='detail'),
    path('choix-profil/', views.choose_profile, name='choix_profil'),
    path('onboarding/', views.onboarding, name='onboarding'),
    path('set-type/<str:type_name>/', views.set_company_type, name='set_company_type'),
    path('set-types/', views.set_company_types, name='set_company_types'),
]
