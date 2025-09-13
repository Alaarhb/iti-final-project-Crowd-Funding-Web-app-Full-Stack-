"""
Views package for the pages app
Organizing views into separate modules for better maintainability
"""

from .base_views import index
from .projects import (
    projects_list, 
    project_detail, 
    projects_by_category,
    donate_to_project,
    add_comment,
    toggle_like,
    search_projects_ajax
)

# Import all views so they can be used in urls.py
__all__ = [
    'index',
    'projects_list',
    'project_detail', 
    'projects_by_category',
    'donate_to_project',
    'add_comment',
    'toggle_like',
    'search_projects_ajax',
]