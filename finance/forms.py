from django import forms
from finance.models import MonthlyForm
import datetime

from django.utils import timezone

class MonthlyFormForm(forms.ModelForm):
    MONTH_CHOICES = [(i, datetime.date(2000, i, 1).strftime('%B')) for i in range(1, 13)]
    month = forms.ChoiceField(choices=MONTH_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    year = forms.IntegerField(
        initial=timezone.localdate().year,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 2020, 'max': 2099})
    )

    class Meta:
        model = MonthlyForm
        fields = ['month', 'year', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

from finance.models import CashReceipt, Expense

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


class CashReceiptForm(forms.ModelForm):
    class Meta:
        model = CashReceipt
        fields = [
            'receipt_number', 'receipt_date', 'officer', 'officer_name', 'group',
            'receipt_amount', 'amount_deposited', 'notes'
        ]
        widgets = {
            'receipt_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Receipt number'}),
            'receipt_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'officer': forms.Select(attrs={'class': 'form-select'}),
            'officer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Officer name'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
            'receipt_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'amount_deposited': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            from accounts.models import User
            self.fields['officer'].queryset = User.objects.filter(
                role__in=['officer', 'admin', 'ict']
            ).order_by('first_name', 'last_name', 'username')
        except Exception:
            pass
        self.fields['officer'].required = False
