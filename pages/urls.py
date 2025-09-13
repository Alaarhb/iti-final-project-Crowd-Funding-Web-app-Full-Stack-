from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('projects/', views.projects, name='projects'),
    path('projects/<str:slug>/', views.project_detail, name='project_detail'),
]
