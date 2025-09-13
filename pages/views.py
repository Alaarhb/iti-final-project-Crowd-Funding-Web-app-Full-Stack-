from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Count, Sum
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Projects, Categories, Donation, ProjectComment, ProjectLike
from .forms import DonationForm, ProjectCommentForm
import json

def index(request):
    """Home page view"""
    featured_projects = Projects.objects.filter(status='active').select_related('category').order_by('-created_at')[:3]
    categories = Categories.objects.annotate(projects_count=Count('projects')).order_by('name')
    
    context = {
        'projects': featured_projects,
        'categories': categories
    }
    return render(request, 'pages/index.html', context)

def projects(request):
    """Projects listing page with search, filter, and pagination"""
    projects_list = Projects.objects.filter(status='active').select_related('category', 'creator')
    categories = Categories.objects.all()
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        projects_list = projects_list.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Category filter
    category_filter = request.GET.get('category', '')
    if category_filter and category_filter != 'all':
        projects_list = projects_list.filter(category__name=category_filter)
    
    # Sorting
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'oldest':
        projects_list = projects_list.order_by('created_at')
    elif sort_by == 'most_funded':
        projects_list = projects_list.order_by('-donation_amount')
    elif sort_by == 'least_funded':
        projects_list = projects_list.order_by('donation_amount')
    elif sort_by == 'ending_soon':
        projects_list = projects_list.order_by('end_date')
    else:  # newest
        projects_list = projects_list.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(projects_list, 9)  # Show 9 projects per page
    page = request.GET.get('page', 1)
    
    try:
        projects_page = paginator.page(page)
    except PageNotAnInteger:
        projects_page = paginator.page(1)
    except EmptyPage:
        projects_page = paginator.page(paginator.num_pages)
    
    # Statistics for display
    total_projects = Projects.objects.filter(status='active').count()
    total_funded = Projects.objects.filter(status='active').aggregate(
        total=Sum('donation_amount')
    )['total'] or 0
    
    context = {
        'projects': projects_page,
        'categories': categories,
        'search_query': search_query,
        'selected_category': category_filter,
        'selected_sort': sort_by,
        'total_projects': total_projects,
        'total_funded': total_funded,
        'paginator': paginator,
    }
    return render(request, 'pages/projects.html', context)

def project_detail(request, slug):
    """Project detail page"""
    project = get_object_or_404(
        Projects.objects.select_related('category', 'creator'),
        slug=slug
    )
    
    # Increment view count
    project.views_count += 1
    project.save(update_fields=['views_count'])
    
    # Get recent donations
    recent_donations = project.get_recent_donations(limit=5)
    
    # Get comments
    comments = project.comments.select_related('user').order_by('-created_at')[:10]
    
    # Get similar projects
    similar_projects = Projects.objects.filter(
        category=project.category,
        status='active'
    ).exclude(id=project.id)[:3]
    
    # Check if user has liked this project
    user_liked = False
    if request.user.is_authenticated:
        user_liked = ProjectLike.objects.filter(
            project=project, 
            user=request.user
        ).exists()
    
    # Forms
    donation_form = DonationForm()
    comment_form = ProjectCommentForm()
    
    context = {
        'project': project,
        'recent_donations': recent_donations,
        'comments': comments,
        'similar_projects': similar_projects,
        'user_liked': user_liked,
        'donation_form': donation_form,
        'comment_form': comment_form,
    }
    return render(request, 'pages/project_detail.html', context)

@login_required
@require_POST
def donate_to_project(request, slug):
    """Handle donation to project"""
    project = get_object_or_404(Projects, slug=slug, status='active')
    form = DonationForm(request.POST)
    
    if form.is_valid():
        donation = form.save(commit=False)
        donation.project = project
        donation.donor = request.user
        donation.save()
        
        messages.success(request, f'Thank you for your donation of £{donation.amount}!')
        return redirect('project_detail', slug=slug)
    else:
        messages.error(request, 'Please correct the errors in the donation form.')
        return redirect('project_detail', slug=slug)

@login_required
@require_POST
def add_comment(request, slug):
    """Add comment to project"""
    project = get_object_or_404(Projects, slug=slug)
    form = ProjectCommentForm(request.POST)
    
    if form.is_valid():
        comment = form.save(commit=False)
        comment.project = project
        comment.user = request.user
        comment.save()
        
        messages.success(request, 'Your comment has been added!')
    else:
        messages.error(request, 'Please enter a valid comment.')
    
    return redirect('project_detail', slug=slug)

@login_required
@require_POST
def toggle_like(request, slug):
    """Toggle like/unlike for a project (AJAX)"""
    project = get_object_or_404(Projects, slug=slug)
    
    like, created = ProjectLike.objects.get_or_create(
        project=project,
        user=request.user
    )
    
    if not created:
        like.delete()
        liked = False
    else:
        liked = True
    
    likes_count = project.likes.count()
    
    return JsonResponse({
        'liked': liked,
        'likes_count': likes_count
    })

def projects_by_category(request, category_name):
    """Show projects filtered by category"""
    category = get_object_or_404(Categories, name=category_name)
    projects_list = Projects.objects.filter(
        category=category,
        status='active'
    ).select_related('creator')
    
    # Pagination
    paginator = Paginator(projects_list, 9)
    page = request.GET.get('page', 1)
    
    try:
        projects_page = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        projects_page = paginator.page(1)
    
    context = {
        'projects': projects_page,
        'category': category,
        'categories': Categories.objects.all(),
    }
    return render(request, 'pages/category_projects.html', context)

def search_projects(request):
    """AJAX search for projects"""
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'projects': []})
    
    projects = Projects.objects.filter(
        Q(title__icontains=query) | Q(description__icontains=query),
        status='active'
    ).values('title', 'slug', 'donation_amount', 'target_amount')[:5]
    
    projects_data = []
    for project in projects:
        funded_percentage = (project['donation_amount'] / project['target_amount']) * 100 if project['target_amount'] > 0 else 0
        projects_data.append({
            'title': project['title'],
            'slug': project['slug'],
            'funded_percentage': round(funded_percentage, 1)
        })
    
    return JsonResponse({'projects': projects_data})