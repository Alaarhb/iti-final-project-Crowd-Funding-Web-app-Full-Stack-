from django.db import models
from django.utils.text import slugify
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

class Categories(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="FontAwesome icon class")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    def get_projects_count(self):
        return self.projects.count()
    
    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']

class Projects(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('draft', 'Draft'),
    ]
    
    title = models.CharField(max_length=100)
    description = models.TextField()
    about_project = models.TextField()
    image = models.ImageField(upload_to='projects/%Y/%m/%d/')
    
    # Financial fields
    target_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1.00'))]
    )
    donation_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    
    # Project info
    category = models.ForeignKey('Categories', on_delete=models.CASCADE, related_name='projects')
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_projects')
    slug = models.SlugField(null=True, blank=True, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    end_date = models.DateTimeField()
    
    # Statistics
    donors = models.IntegerField(default=0)
    views_count = models.IntegerField(default=0)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            # Ensure unique slug
            counter = 1
            original_slug = self.slug
            while Projects.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('project_detail', kwargs={'slug': self.slug})
    
    @property
    def funded_percentage(self):
        """Calculate the percentage of funding achieved"""
        if self.target_amount > 0:
            return min((self.donation_amount / self.target_amount) * 100, 100)
        return 0
    
    @property
    def remaining_amount(self):
        """Calculate remaining amount needed"""
        return max(self.target_amount - self.donation_amount, 0)
    
    @property
    def days_left(self):
        """Calculate days left for the campaign"""
        from django.utils import timezone
        if self.end_date > timezone.now():
            return (self.end_date - timezone.now()).days
        return 0
    
    @property
    def is_funded(self):
        """Check if project is fully funded"""
        return self.donation_amount >= self.target_amount
    
    def get_recent_donations(self, limit=5):
        """Get recent donations for this project"""
        return self.donations.select_related('donor').order_by('-created_at')[:limit]
    
    class Meta:
        verbose_name = 'Project'
        verbose_name_plural = 'Projects'
        ordering = ['-created_at']

class Donation(models.Model):
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, related_name='donations')
    donor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='donations')
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1.00'))]
    )
    message = models.TextField(blank=True)
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.donor.username} donated {self.amount} to {self.project.title}"
    
    def save(self, *args, **kwargs):
        # Update project donation amount and donor count
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            # Update project statistics
            self.project.donation_amount += self.amount
            if not Donation.objects.filter(project=self.project, donor=self.donor).exclude(pk=self.pk).exists():
                self.project.donors += 1
            self.project.save(update_fields=['donation_amount', 'donors'])
    
    class Meta:
        ordering = ['-created_at']

class ProjectComment(models.Model):
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Comment by {self.user.username} on {self.project.title}"
    
    class Meta:
        ordering = ['-created_at']

class ProjectLike(models.Model):
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('project', 'user')
        
    def __str__(self):
        return f"{self.user.username} likes {self.project.title}"