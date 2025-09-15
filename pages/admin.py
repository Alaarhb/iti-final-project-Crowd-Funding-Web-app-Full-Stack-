from django.contrib import admin
from django.utils.html import format_html
from .models import Projects, Categories, Donation, ProjectComment, ProjectLike

@admin.register(Categories)
class CategoriesAdmin(admin.ModelAdmin):
    list_display = ['name', 'projects_count', 'created_at']
    search_fields = ['name']
    
    def projects_count(self, obj):
        return obj.projects.count()
    projects_count.short_description = 'Projects Count'

class DonationInline(admin.TabularInline):
    model = Donation
    extra = 0
    readonly_fields = ['created_at']
    fields = ['donor', 'amount', 'message', 'is_anonymous', 'created_at']

class CommentInline(admin.TabularInline):
    model = ProjectComment
    extra = 0
    readonly_fields = ['created_at']

@admin.register(Projects)
class ProjectsAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'creator', 'category', 'status',
        'funded_percentage_display', 'donation_amount',
        'target_amount', 'donors', 'views_count', 'created_at'
    ]
    list_filter = ['status', 'category', 'created_at', 'end_date']
    search_fields = ['title', 'description', 'creator__username']
    readonly_fields = ['slug', 'donation_amount', 'donors', 'views_count', 'funded_percentage_display']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [DonationInline, CommentInline]
    
    def funded_percentage_display(self, obj):
        percentage = obj.funded_percentage
        color = 'green' if percentage >= 100 else 'orange' if percentage >= 50 else 'red'
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color,
            percentage
        )
    funded_percentage_display.short_description = 'Funded %'
    
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(self.readonly_fields)
        if obj:
            readonly_fields.extend(['created_at', 'updated_at'])
        return readonly_fields

@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ['donor', 'project', 'amount', 'is_anonymous', 'created_at']
    list_filter = ['is_anonymous', 'created_at', 'project__category']
    search_fields = ['donor__username', 'project__title']
    readonly_fields = ['created_at']
    raw_id_fields = ['project', 'donor']
    
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(ProjectComment)
class ProjectCommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'project', 'content_preview', 'created_at']
    list_filter = ['created_at', 'project__category']
    search_fields = ['user__username', 'project__title', 'content']
    readonly_fields = ['created_at']
    raw_id_fields = ['project', 'user']
    
    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content Preview'

@admin.register(ProjectLike)
class ProjectLikeAdmin(admin.ModelAdmin):
    list_display = ['user', 'project', 'created_at']
    list_filter = ['created_at', 'project__category']
    search_fields = ['user__username', 'project__title']
    readonly_fields = ['created_at']
    raw_id_fields = ['project', 'user']

admin.site.site_header = "EgyptFund Administration"
admin.site.site_title = "EgyptFund Admin"
admin.site.index_title = "Welcome to EgyptFund Administration"
