from django import forms
from groups.models import Group


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name', 'location', 'date_created', 'officer_name', 'banking_type']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Group Name'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Location'}),
            'date_created': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'officer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Group Officer Name'}),
            'banking_type': forms.Select(attrs={'class': 'form-select'}),
        }
