from django import forms
from members.models import Member


class MemberForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.group = kwargs.pop('group', None)
        super().__init__(*args, **kwargs)

        if self.group is None and self.instance and self.instance.pk:
            self.group = self.instance.group

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

    def clean_member_number(self):
        member_number = self.cleaned_data.get('member_number')

        if not member_number or not self.group:
            return member_number

        duplicate_qs = Member.objects.filter(group=self.group, member_number=member_number)
        if self.instance and self.instance.pk:
            duplicate_qs = duplicate_qs.exclude(pk=self.instance.pk)

        if duplicate_qs.exists():
            raise forms.ValidationError(
                'This member number already exists in the selected group. Choose a different number.'
            )

        return member_number
