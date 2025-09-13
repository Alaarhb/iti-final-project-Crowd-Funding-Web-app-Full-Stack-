from django.urls import path
from .views import (
    index,
    projects_list,
    project_detail,
    projects_by_category,
    donate_to_project,
    add_comment,
    toggle_like,
    search_projects_ajax
)

app_name = 'pages'

urlpatterns = [
    # Main pages
    path('', index, name='index'),
    path('projects/', projects_list, name='projects'),
    path('projects/<str:slug>/', project_detail, name='project_detail'),
    
    # Category-specific projects
    path('category/<str:category_name>/', projects_by_category, name='projects_by_category'),
    
    # Project interactions
    path('projects/<str:slug>/donate/', donate_to_project, name='donate_to_project'),
    path('projects/<str:slug>/comment/', add_comment, name='add_comment'),
    path('projects/<str:slug>/toggle-like/', toggle_like, name='toggle_like'),
    
    # AJAX endpoints
    path('api/search-projects/', search_projects_ajax, name='search_projects_ajax'),
]