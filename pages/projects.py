from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Count, Sum
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .models import Projects, Categories, Donation, ProjectComment, ProjectLike
from .forms import DonationForm, ProjectCommentForm, ProjectSearchForm
import json

class ProjectsViews:
    """Class to handle all project-related views"""
    
    @staticmethod
    def projects_list(request):
        """Main projects listing page with advanced filtering and search"""
        
        # Get base queryset
        projects_list = Projects.objects.filter(
            status='active'
        ).select_related('category', 'creator').prefetch_related('donations', 'likes')
        
        # Get all categories for filter dropdown
        categories = Categories.objects.annotate(
            projects_count=Count('projects', filter=Q(projects__status='active'))
        ).order_by('name')
        
        # Initialize form with GET data
        search_form = ProjectSearchForm(request.GET)
        
        # Apply filters
        search_query = request.GET.get('search', '').strip()
        if search_query:
            projects_list = projects_list.filter(
                Q(title__icontains=search_query) | 
                Q(description__icontains=search_query) |
                Q(about_project__icontains=search_query) |
                Q(category__name__icontains=search_query)
            )
        
        # Category filter
        category_filter = request.GET.get('category', '')
        if category_filter and category_filter != 'all':
            try:
                category_obj = Categories.objects.get(name=category_filter)
                projects_list = projects_list.filter(category=category_obj)
            except Categories.DoesNotExist:
                pass
        
        # Status filter
        status_filter = request.GET.get('status', '')
        if status_filter == 'funded':
            projects_list = projects_list.filter(donation_amount__gte= models.F('target_amount'))
        elif status_filter == 'ending_soon':
            from django.utils import timezone
            from datetime import timedelta
            ending_soon_date = timezone.now() + timedelta(days=7)
            projects_list = projects_list.filter(end_date__lte=ending_soon_date, end_date__gt=timezone.now())
        
        # Sorting options
        sort_by = request.GET.get('sort', 'newest')
        sort_options = {
            'newest': '-created_at',
            'oldest': 'created_at',
            'most_funded': '-donation_amount',
            'least_funded': 'donation_amount',
            'ending_soon': 'end_date',
            'most_popular': '-views_count',
            'alphabetical': 'title',
        }
        
        if sort_by in sort_options:
            projects_list = projects_list.order_by(sort_options[sort_by])
        else:
            projects_list = projects_list.order_by('-created_at')
        
        # Price range filter
        min_price = request.GET.get('min_price')
        max_price = request.GET.get('max_price')
        if min_price:
            try:
                projects_list = projects_list.filter(target_amount__gte=float(min_price))
            except ValueError:
                pass
        if max_price:
            try:
                projects_list = projects_list.filter(target_amount__lte=float(max_price))
            except ValueError:
                pass
        
        # Pagination
        items_per_page = int(request.GET.get('per_page', 12))
        if items_per_page not in [6, 12, 24, 48]:
            items_per_page = 12
            
        paginator = Paginator(projects_list, items_per_page)
        page = request.GET.get('page', 1)
        
        try:
            projects_page = paginator.page(page)
        except PageNotAnInteger:
            projects_page = paginator.page(1)
        except EmptyPage:
            projects_page = paginator.page(paginator.num_pages)
        
        # Calculate statistics
        stats = ProjectsViews._calculate_projects_stats()
        
        # Check for AJAX request (for infinite scroll or filtering)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ProjectsViews._handle_ajax_projects_request(request, projects_page)
        
        context = {
            'projects': projects_page,
            'categories': categories,
            'search_form': search_form,
            'search_query': search_query,
            'selected_category': category_filter,
            'selected_sort': sort_by,
            'selected_status': status_filter,
            'items_per_page': items_per_page,
            'stats': stats,
            'paginator': paginator,
            'has_filters': bool(search_query or category_filter or status_filter or min_price or max_price),
        }
        
        return render(request, 'pages/projects/projects_list.html', context)
    
    @staticmethod
    def project_detail(request, slug):
        """Detailed project view with donation and comment functionality"""
        
        project = get_object_or_404(
            Projects.objects.select_related('category', 'creator')
                    .prefetch_related('donations__donor', 'comments__user', 'likes'),
            slug=slug
        )
        
        # Increment view count (only for non-creator views)
        if request.user != project.creator:
            Projects.objects.filter(id=project.id).update(views_count= models.F('views_count') + 1)
            project.refresh_from_db()
        
        # Get project data
        recent_donations = project.donations.select_related('donor').order_by('-created_at')[:5]
        comments = project.comments.select_related('user').order_by('-created_at')[:10]
        
        # Get similar projects
        similar_projects = Projects.objects.filter(
            category=project.category,
            status='active'
        ).exclude(id=project.id).order_by('-donation_amount')[:4]
        
        # Check user interactions
        user_liked = False
        user_donated = False
        if request.user.is_authenticated:
            user_liked = project.likes.filter(user=request.user).exists()
            user_donated = project.donations.filter(donor=request.user).exists()
        
        # Initialize forms
        donation_form = DonationForm()
        comment_form = ProjectCommentForm()
        
        # Calculate project analytics
        analytics = ProjectsViews._get_project_analytics(project)
        
        context = {
            'project': project,
            'recent_donations': recent_donations,
            'comments': comments,
            'similar_projects': similar_projects,
            'user_liked': user_liked,
            'user_donated': user_donated,
            'donation_form': donation_form,
            'comment_form': comment_form,
            'analytics': analytics,
        }
        
        return render(request, 'pages/projects/project_detail.html', context)
    
    @staticmethod
    def projects_by_category(request, category_name):
        """Show projects filtered by specific category"""
        
        category = get_object_or_404(Categories, name=category_name)
        
        projects_list = Projects.objects.filter(
            category=category,
            status='active'
        ).select_related('creator').prefetch_related('donations')
        
        # Apply same sorting and filtering as main projects page
        sort_by = request.GET.get('sort', 'newest')
        if sort_by == 'most_funded':
            projects_list = projects_list.order_by('-donation_amount')
        elif sort_by == 'ending_soon':
            projects_list = projects_list.order_by('end_date')
        else:
            projects_list = projects_list.order_by('-created_at')
        
        # Pagination
        paginator = Paginator(projects_list, 12)
        page = request.GET.get('page', 1)
        
        try:
            projects_page = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            projects_page = paginator.page(1)
        
        context = {
            'projects': projects_page,
            'category': category,
            'categories': Categories.objects.all(),
            'selected_sort': sort_by,
        }
        
        return render(request, 'pages/projects/category_projects.html', context)
    
    @staticmethod
    @login_required
    @require_POST
    def donate_to_project(request, slug):
        """Handle donation to project"""
        
        project = get_object_or_404(Projects, slug=slug, status='active')
        
        # Check if project is still accepting donations
        if project.days_left <= 0:
            messages.error(request, 'This project campaign has ended.')
            return redirect('project_detail', slug=slug)
        
        form = DonationForm(request.POST)
        
        if form.is_valid():
            donation = form.save(commit=False)
            donation.project = project
            donation.donor = request.user
            
            try:
                donation.save()
                messages.success(
                    request, 
                    f'Thank you for your donation of £{donation.amount}! Your support means a lot.'
                )
                
                # Check if project reached its goal
                if project.donation_amount >= project.target_amount:
                    messages.info(request, '🎉 This project has reached its funding goal!')
                    
            except Exception as e:
                messages.error(request, 'There was an error processing your donation. Please try again.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field.title()}: {error}')
        
        return redirect('project_detail', slug=slug)
    
    @staticmethod
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
            
            messages.success(request, 'Your comment has been added successfully!')
        else:
            messages.error(request, 'Please enter a valid comment.')
        
        return redirect('project_detail', slug=slug)
    
    @staticmethod
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
            'success': True,
            'liked': liked,
            'likes_count': likes_count,
            'message': 'Added to favorites' if liked else 'Removed from favorites'
        })
    
    @staticmethod
    def search_projects_ajax(request):
        """AJAX search for projects (for autocomplete/live search)"""
        
        query = request.GET.get('q', '').strip()
        if len(query) < 2:
            return JsonResponse({'projects': []})
        
        projects = Projects.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query),
            status='active'
        ).values(
            'title', 'slug', 'donation_amount', 'target_amount', 'image'
        )[:8]
        
        projects_data = []
        for project in projects:
            funded_percentage = (
                (project['donation_amount'] / project['target_amount']) * 100 
                if project['target_amount'] > 0 else 0
            )
            projects_data.append({
                'title': project['title'],
                'slug': project['slug'],
                'funded_percentage': round(funded_percentage, 1),
                'image_url': project['image'] if project['image'] else None,
            })
        
        return JsonResponse({'projects': projects_data})
    
    @staticmethod
    def _calculate_projects_stats():
        """Calculate statistics for projects page"""
        
        from django.db.models import Count, Sum, Avg
        
        stats = Projects.objects.filter(status='active').aggregate(
            total_projects=Count('id'),
            total_raised=Sum('donation_amount'),
            total_backers=Sum('donors'),
            avg_funding=Avg('donation_amount')
        )
        
        # Add additional stats
        stats['categories_count'] = Categories.objects.count()
        stats['funded_projects'] = Projects.objects.filter(
            status='active',
            donation_amount__gte=models.F('target_amount')
        ).count()
        
        return stats
    
    @staticmethod
    def _get_project_analytics(project):
        """Get analytics data for a specific project"""
        
        from django.utils import timezone
        from datetime import timedelta
        
        # Calculate daily donations for the last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        daily_donations = project.donations.filter(
            created_at__gte=thirty_days_ago
        ).extra({
            'day': 'date(created_at)'
        }).values('day').annotate(
            amount=Sum('amount'),
            count=Count('id')
        ).order_by('day')
        
        analytics = {
            'daily_donations': list(daily_donations),
            'avg_donation': project.donations.aggregate(Avg('amount'))['amount__avg'] or 0,
            'funding_velocity': project.donation_amount / max(project.days_left, 1) if project.days_left > 0 else 0,
            'success_probability': min((project.funded_percentage / 100) * (30 / max(project.days_left, 1)), 1.0),
        }
        
        return analytics
    
    @staticmethod
    def _handle_ajax_projects_request(request, projects_page):
        """Handle AJAX requests for projects (infinite scroll, filtering)"""
        
        projects_data = []
        for project in projects_page:
            projects_data.append({
                'id': project.id,
                'title': project.title,
                'slug': project.slug,
                'description': project.description,
                'image_url': project.image.url if project.image else None,
                'category': project.category.name,
                'funded_percentage': project.funded_percentage,
                'donation_amount': float(project.donation_amount),
                'target_amount': float(project.target_amount),
                'donors': project.donors,
                'days_left': project.days_left,
                'creator': project.creator.get_full_name() or project.creator.username,
            })
        
        return JsonResponse({
            'projects': projects_data,
            'has_next': projects_page.has_next(),
            'has_previous': projects_page.has_previous(),
            'current_page': projects_page.number,
            'total_pages': projects_page.paginator.num_pages,
        })

# Create view functions that use the class methods
projects_list = ProjectsViews.projects_list
project_detail = ProjectsViews.project_detail
projects_by_category = ProjectsViews.projects_by_category
donate_to_project = ProjectsViews.donate_to_project
add_comment = ProjectsViews.add_comment
toggle_like = ProjectsViews.toggle_like
search_projects_ajax = ProjectsViews.search_projects_ajax