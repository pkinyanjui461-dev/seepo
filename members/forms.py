from django import forms
from members.models import Member


class MemberForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ['member_number', 'name', 'phone', 'join_date', 'is_active']
        widgets = {
            'member_number': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 1', 'min': 1}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254...'}),
            'join_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
