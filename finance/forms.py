from django import forms
from finance.models import MonthlyForm
import datetime


class MonthlyFormForm(forms.ModelForm):
    MONTH_CHOICES = [(i, datetime.date(2000, i, 1).strftime('%B')) for i in range(1, 13)]
    month = forms.ChoiceField(choices=MONTH_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    year = forms.IntegerField(
        initial=datetime.date.today().year,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 2020, 'max': 2099})
    )

    class Meta:
        model = MonthlyForm
        fields = ['month', 'year', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

from finance.models import Expense

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['date', 'name', 'amount', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'list': 'expense-names', 'autocomplete': 'off', 'placeholder': 'e.g., Office Rent'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional details'}),
        }
