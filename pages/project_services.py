

from django.db.models import Q, Count, Sum, Avg, F
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from .models import Projects, Categories, Donation, ProjectComment, ProjectLike

class ProjectsService:
    """Service class to handle project-related business logic"""
    
    @staticmethod
    def get_featured_projects(limit=6):
        """Get featured projects for homepage"""
        return Projects.objects.filter(
            status='active'
        ).select_related('category', 'creator').annotate(
            score=F('donation_amount') * 0.7 + F('views_count') * 0.2 + F('donors') * 0.1
        ).order_by('-score', '-created_at')[:limit]
    
    @staticmethod
    def search_projects(query, filters=None):
        """Advanced search functionality for projects"""
        if filters is None:
            filters = {}
        
        queryset = Projects.objects.filter(status='active').select_related('category', 'creator')
        
        # Text search
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(about_project__icontains=query) |
                Q(category__name__icontains=query) |
                Q(creator__first_name__icontains=query) |
                Q(creator__last_name__icontains=query)
            )
        
        # Apply filters
        if filters.get('category'):
            queryset = queryset.filter(category__name=filters['category'])
        
        if filters.get('min_amount'):
            queryset = queryset.filter(target_amount__gte=filters['min_amount'])
        
        if filters.get('max_amount'):
            queryset = queryset.filter(target_amount__lte=filters['max_amount'])
        
        if filters.get('status') == 'funded':
            queryset = queryset.filter(donation_amount__gte=F('target_amount'))
        elif filters.get('status') == 'active':
            queryset = queryset.filter(end_date__gt=timezone.now())
        elif filters.get('status') == 'ending_soon':
            ending_soon = timezone.now() + timedelta(days=7)
            queryset = queryset.filter(
                end_date__lte=ending_soon,
                end_date__gt=timezone.now()
            )
        
        # Sorting
        sort_options = {
            'newest': '-created_at',
            'oldest': 'created_at',
            'most_funded': '-donation_amount',
            'least_funded': 'donation_amount',
            'ending_soon': 'end_date',
            'most_popular': '-views_count',
            'alphabetical': 'title',
            'relevance': '-score'
        }
        
        sort_by = filters.get('sort', 'newest')
        if sort_by == 'relevance' and query:
            # Add relevance scoring when searching
            queryset = queryset.annotate(
                score=Count('title', filter=Q(title__icontains=query)) * 3 +
                      Count('description', filter=Q(description__icontains=query)) * 2 +
                      Count('category__name', filter=Q(category__name__icontains=query))
            )
        
        order_by = sort_options.get(sort_by, '-created_at')
        queryset = queryset.order_by(order_by)
        
        return queryset
    
    @staticmethod
    def get_project_analytics(project):
        """Get detailed analytics for a project"""
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        
        # Daily donations for the last 30 days
        daily_donations = project.donations.filter(
            created_at__gte=thirty_days_ago
        ).extra(
            select={'day': 'DATE(created_at)'}
        ).values('day').annotate(
            total_amount=Sum('amount'),
            donation_count=Count('id')
        ).order_by('day')
        
        # Donation statistics
        donation_stats = project.donations.aggregate(
            avg_donation=Avg('amount'),
            max_donation=Sum('amount', filter=Q(amount=F('amount'))),
            total_donations=Count('id')
        )
        
        # Funding velocity (average per day)
        days_active = max((now - project.created_at).days, 1)
        funding_velocity = project.donation_amount / days_active
        
        # Prediction metrics
        days_remaining = max(project.days_left, 1)
        amount_needed = project.target_amount - project.donation_amount
        required_daily_funding = amount_needed / days_remaining if amount_needed > 0 else 0
        
        success_probability = min(
            (project.funded_percentage / 100) * (funding_velocity / max(required_daily_funding, 0.01)),
            1.0
        ) if required_daily_funding > 0 else 1.0
        
        return {
            'daily_donations': list(daily_donations),
            'donation_stats': donation_stats,
            'funding_velocity': funding_velocity,
            'required_daily_funding': required_daily_funding,
            'success_probability': success_probability,
            'days_active': days_active,
        }
    
    @staticmethod
    def get_similar_projects(project, limit=4):
        """Get projects similar to the given project"""
        return Projects.objects.filter(
            category=project.category,
            status='active'
        ).exclude(id=project.id).annotate(
            similarity_score=Count('donations') + Count('likes')
        ).order_by('-similarity_score', '-donation_amount')[:limit]
    
    @staticmethod
    def calculate_platform_stats():
        """Calculate overall platform statistics"""
        active_projects = Projects.objects.filter(status='active')
        
        stats = active_projects.aggregate(
            total_projects=Count('id'),
            total_raised=Sum('donation_amount'),
            total_target=Sum('target_amount'),
            total_backers=Sum('donors'),
            avg_project_size=Avg('target_amount'),
            avg_funding=Avg('donation_amount')
        )
        
        # Additional calculations
        stats['success_rate'] = active_projects.filter(
            donation_amount__gte=F('target_amount')
        ).count() / max(stats['total_projects'], 1) * 100
        
        stats['total_categories'] = Categories.objects.count()
        
        # Monthly growth
        current_month = timezone.now().replace(day=1)
        last_month = (current_month - timedelta(days=1)).replace(day=1)
        
        current_month_projects = active_projects.filter(created_at__gte=current_month).count()
        last_month_projects = active_projects.filter(
            created_at__gte=last_month,
            created_at__lt=current_month
        ).count()
        
        if last_month_projects > 0:
            stats['monthly_growth'] = ((current_month_projects - last_month_projects) / last_month_projects) * 100
        else:
            stats['monthly_growth'] = 100 if current_month_projects > 0 else 0
        
        return stats
    
    @staticmethod
    def process_donation(project, user, amount, message="", is_anonymous=False):
        """Process a donation with all necessary checks and updates"""
        
        # Validation checks
        if project.days_left <= 0:
            raise ValueError("Project campaign has ended")
        
        if amount < Decimal('1.00'):
            raise ValueError("Minimum donation amount is £1.00")
        
        if project.status != 'active':
            raise ValueError("Project is not active")
        
        # Create donation
        donation = Donation.objects.create(
            project=project,
            donor=user,
            amount=amount,
            message=message,
            is_anonymous=is_anonymous
        )
        
        # Update project statistics (handled in model save method)
        project.refresh_from_db()
        
        # Check if project reached goal
        goal_reached = project.donation_amount >= project.target_amount
        
        return {
            'donation': donation,
            'goal_reached': goal_reached,
            'new_funded_percentage': project.funded_percentage
        }
    
    @staticmethod
    def get_trending_projects(days=7, limit=6):
        """Get trending projects based on recent activity"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        return Projects.objects.filter(
            status='active'
        ).annotate(
            recent_donations=Count('donations', filter=Q(donations__created_at__gte=cutoff_date)),
            recent_comments=Count('comments', filter=Q(comments__created_at__gte=cutoff_date)),
            recent_likes=Count('likes', filter=Q(likes__created_at__gte=cutoff_date)),
            trending_score=F('recent_donations') * 3 + F('recent_comments') * 2 + F('recent_likes')
        ).filter(trending_score__gt=0).order_by('-trending_score')[:limit]
    
    @staticmethod
    def get_category_stats():
        """Get statistics for each category"""
        return Categories.objects.annotate(
            total_projects=Count('projects', filter=Q(projects__status='active')),
            total_raised=Sum('projects__donation_amount', filter=Q(projects__status='active')),
            avg_funding=Avg('projects__donation_amount', filter=Q(projects__status='active')),
            success_rate=Count(
                'projects',
                filter=Q(
                    projects__status='active',
                    projects__donation_amount__gte=F('projects__target_amount')
                )
            ) * 100.0 / Count('projects', filter=Q(projects__status='active'))
        ).filter(total_projects__gt=0).order_by('-total_raised')

class DonationService:
    """Service for handling donation-related operations"""
    
    @staticmethod
    def get_user_donations(user, limit=None):
        """Get all donations made by a user"""
        donations = Donation.objects.filter(donor=user).select_related('project').order_by('-created_at')
        if limit:
            donations = donations[:limit]
        return donations
    
    @staticmethod
    def get_donation_summary(user):
        """Get donation summary for a user"""
        summary = Donation.objects.filter(donor=user).aggregate(
            total_donated=Sum('amount'),
            total_projects=Count('project', distinct=True),
            avg_donation=Avg('amount')
        )
        
        # Get favorite categories
        favorite_categories = Categories.objects.filter(
            projects__donations__donor=user
        ).annotate(
            donation_count=Count('projects__donations')
        ).order_by('-donation_count')[:3]
        
        summary['favorite_categories'] = favorite_categories
        return summary
    
    @staticmethod
    def check_donation_eligibility(project, user):
        """Check if a user can donate to a project"""
        errors = []
        
        if project.creator == user:
            errors.append("You cannot donate to your own project")
        
        if project.days_left <= 0:
            errors.append("This project's campaign has ended")
        
        if project.status != 'active':
            errors.append("This project is not currently accepting donations")
        
        return len(errors) == 0, errors

class ProjectSearchService:
    """Advanced search service for projects"""
    
    @staticmethod
    def autocomplete_search(query, limit=5):
        """Get autocomplete suggestions for project search"""
        if len(query) < 2:
            return []
        
        # Search in project titles and descriptions
        projects = Projects.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query),
            status='active'
        ).values('title', 'slug')[:limit]
        
        # Search in categories
        categories = Categories.objects.filter(
            name__icontains=query
        ).values('name')[:3]
        
        results = []
        
        # Add project suggestions
        for project in projects:
            results.append({
                'type': 'project',
                'title': project['title'],
                'slug': project['slug'],
                'url': f"/projects/{project['slug']}/"
            })
        
        # Add category suggestions
        for category in categories:
            results.append({
                'type': 'category',
                'title': f"Projects in {category['name']}",
                'name': category['name'],
                'url': f"/category/{category['name']}/"
            })
        
        return results
    
    @staticmethod
    def advanced_search(filters):
        """Perform advanced search with multiple filters"""
        queryset = Projects.objects.filter(status='active').select_related('category', 'creator')
        
        # Text search
        if filters.get('query'):
            queryset = ProjectsService.search_projects(filters['query'], filters)
        
        # Price range
        if filters.get('min_price'):
            queryset = queryset.filter(target_amount__gte=filters['min_price'])
        if filters.get('max_price'):
            queryset = queryset.filter(target_amount__lte=filters['max_price'])
        
        # Funding status
        funding_status = filters.get('funding_status')
        if funding_status == 'not_funded':
            queryset = queryset.filter(donation_amount__lt=F('target_amount'))
        elif funding_status == 'funded':
            queryset = queryset.filter(donation_amount__gte=F('target_amount'))
        elif funding_status == 'nearly_funded':
            queryset = queryset.filter(
                donation_amount__gte=F('target_amount') * 0.8,
                donation_amount__lt=F('target_amount')
            )
        
        # Time filters
        time_filter = filters.get('time_filter')
        now = timezone.now()
        if time_filter == 'ending_soon':
            queryset = queryset.filter(
                end_date__lte=now + timedelta(days=7),
                end_date__gt=now
            )
        elif time_filter == 'just_started':
            queryset = queryset.filter(
                created_at__gte=now - timedelta(days=7)
            )
        elif time_filter == 'long_running':
            queryset = queryset.filter(
                created_at__lte=now - timedelta(days=30)
            )
        
        return queryset

class ProjectRecommendationService:
    """Service for recommending projects to users"""
    
    @staticmethod
    def get_recommendations_for_user(user, limit=6):
        """Get personalized project recommendations for a user"""
        
        # Get user's donation history to understand preferences
        user_categories = Categories.objects.filter(
            projects__donations__donor=user
        ).annotate(
            donation_count=Count('projects__donations')
        ).order_by('-donation_count')
        
        recommendations = []
        
        if user_categories.exists():
            # Recommend based on user's favorite categories
            for category in user_categories[:3]:
                similar_projects = Projects.objects.filter(
                    category=category,
                    status='active'
                ).exclude(
                    donations__donor=user  # Exclude already backed projects
                ).order_by('-donation_amount')[:2]
                
                recommendations.extend(similar_projects)
        
        # If we don't have enough recommendations, add trending projects
        if len(recommendations) < limit:
            trending = ProjectsService.get_trending_projects(
                limit=limit - len(recommendations)
            ).exclude(
                id__in=[p.id for p in recommendations]
            )
            recommendations.extend(trending)
        
        return recommendations[:limit]
    
    @staticmethod
    def get_similar_projects_collaborative(project, limit=4):
        """Get similar projects using collaborative filtering"""
        
        # Find users who donated to this project
        project_donors = User.objects.filter(donations__project=project)
        
        # Find other projects these users also supported
        similar_projects = Projects.objects.filter(
            donations__donor__in=project_donors,
            status='active'
        ).exclude(id=project.id).annotate(
            common_donors=Count('donations__donor', distinct=True)
        ).order_by('-common_donors', '-donation_amount')[:limit]
        
        return similar_projects