from django.shortcuts import render
from django.db.models import Count, Sum
from .models import Projects, Categories

def index(request):
    """
    Home page view showing featured projects and statistics
    """
    
    # Get featured projects (most funded or recently created)
    featured_projects = Projects.objects.filter(
        status='active'
    ).select_related('category', 'creator').order_by('-donation_amount', '-created_at')[:6]
    
    # Get categories with project counts
    categories = Categories.objects.annotate(
        projects_count=Count('projects', filter={'projects__status': 'active'})
    ).order_by('name')
    
    # Calculate homepage statistics
    stats = Projects.objects.filter(status='active').aggregate(
        total_projects=Count('id'),
        total_raised=Sum('donation_amount'),
        total_backers=Sum('donors')
    )
    
    # Get success stories (fully funded projects)
    success_stories = Projects.objects.filter(
        status='active',
        donation_amount__gte= models.F('target_amount')
    ).count()
    
    # Add success stories to stats
    stats['success_stories'] = success_stories
    
    # Get trending categories (categories with most projects)
    trending_categories = Categories.objects.annotate(
        projects_count=Count('projects', filter={'projects__status': 'active'})
    ).filter(projects_count__gt=0).order_by('-projects_count')[:6]
    
    context = {
        'featured_projects': featured_projects,
        'categories': categories,
        'trending_categories': trending_categories,
        'stats': stats,
        'page_title': 'Fund Your Dreams, Empower Egypt',
        'page_description': 'Join Egypt\'s leading crowdfunding platform to bring innovative projects to life or support ideas that matter to you.',
    }
    
    return render(request, 'pages/index.html', context)