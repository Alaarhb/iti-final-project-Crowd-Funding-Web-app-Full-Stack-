from django import forms
from .models import Donation, ProjectComment, Projects
from django.core.validators import MinValueValidator
from decimal import Decimal

class DonationForm(forms.ModelForm):
    class Meta:
        model = Donation
        fields = ['amount', 'message', 'is_anonymous']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter amount (£)',
                'min': '1',
                'step': '0.01'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Leave a message (optional)',
                'rows': 3
            }),
            'is_anonymous': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount < Decimal('1.00'):
            raise forms.ValidationError('Minimum donation amount is £1.00')
        return amount

class ProjectCommentForm(forms.ModelForm):
    class Meta:
        model = ProjectComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Share your thoughts...',
                'rows': 4
            })
        }

class ProjectSearchForm(forms.Form):
    search = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search projects...'
        })
    )
    
    SORT_CHOICES = [
        ('newest', 'Newest'),
        ('oldest', 'Oldest'),
        ('most_funded', 'Most Funded'),
        ('least_funded', 'Least Funded'),
        ('ending_soon', 'Ending Soon'),
    ]
    
    sort = forms.ChoiceField(
        choices=SORT_CHOICES,
        required=False,
        initial='newest',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    category = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Categories
        self.fields['category'].queryset = Categories.objects.all()

class ProjectCreateForm(forms.ModelForm):
    class Meta:
        model = Projects
        fields = [
            'title', 'description', 'about_project', 'image',
            'target_amount', 'category', 'end_date'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter project title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Brief description of your project',
                'rows': 3
            }),
            'about_project': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Detailed description of your project',
                'rows': 6
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control'
            }),
            'target_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Target amount (£)',
                'min': '1',
                'step': '0.01'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'end_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            })
        }
    
    def clean_target_amount(self):
        amount = self.cleaned_data.get('target_amount')
        if amount and amount < Decimal('10.00'):
            raise forms.ValidationError('Minimum target amount is £10.00')
        return amount