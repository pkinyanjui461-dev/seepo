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

    def clean(self):
        cleaned_data = super().clean()
        name = (cleaned_data.get('name') or '').strip()
        location = (cleaned_data.get('location') or '').strip()

        if not name or not location:
            return cleaned_data

        duplicate_qs = Group.objects.filter(name__iexact=name, location__iexact=location)
        if self.instance and self.instance.pk:
            duplicate_qs = duplicate_qs.exclude(pk=self.instance.pk)

        if duplicate_qs.exists():
            message = 'A group with this name already exists at this location.'
            self.add_error('name', message)
            self.add_error('location', message)

        return cleaned_data
