from django.db import models
from groups.models import Group
from members.models import Member


class MonthlyForm(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
    ]
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='monthly_forms')
    month = models.PositiveSmallIntegerField()  # 1-12
    year = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('group', 'month', 'year')
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.group.name} – {self.get_month_display()} {self.year}"

    def get_month_display(self):
        import calendar
        return calendar.month_name[self.month]

    def get_month_name(self):
        import calendar
        return calendar.month_name[self.month]


class MemberRecord(models.Model):
    monthly_form = models.ForeignKey(MonthlyForm, on_delete=models.CASCADE, related_name='member_records')
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    order = models.PositiveSmallIntegerField(default=0)

    # Financial columns
    savings_share_bf = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    loan_balance_bf = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_repaid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    principal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    loan_interest = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shares_this_month = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fines_charges = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    savings_share_cf = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    loan_balance_cf = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Validation flags
    savings_valid = models.BooleanField(default=True)
    loan_valid = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'member__name']
        unique_together = ('monthly_form', 'member')

    def __str__(self):
        return f"{self.member.name} – {self.monthly_form}"

    def calculate(self):
        """Backend calculation mirror of JS logic."""
        from decimal import Decimal, ROUND_HALF_UP
        
        # Round the user input values
        self.savings_share_bf = Decimal(str(self.savings_share_bf)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        self.loan_balance_bf = Decimal(str(self.loan_balance_bf)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        self.principal = Decimal(str(self.principal)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        self.total_repaid = Decimal(str(self.total_repaid)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        self.fines_charges = Decimal(str(self.fines_charges)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

        # Calculated fields
        self.loan_interest = (self.loan_balance_bf * Decimal('0.015')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        self.shares_this_month = self.total_repaid - (self.principal + self.loan_interest)
        self.savings_share_cf = self.savings_share_bf + self.shares_this_month
        self.loan_balance_cf = self.loan_balance_bf - self.principal

    def validate(self):
        """Returns dict of validation errors."""
        errors = {}
        
        # Check for negatives
        loan_errors = []
        if self.loan_balance_bf < 0: loan_errors.append("Loan B/F cannot be negative.")
        if self.loan_balance_cf < 0: loan_errors.append("Loan C/F cannot be negative.")
        
        # Loan balance rule: loan_balance_bf == principal + loan_balance_cf
        if self.loan_balance_bf != (self.principal + self.loan_balance_cf):
            loan_errors.append(f"Mismatch. Expected: {self.principal + self.loan_balance_cf}, Current: {self.loan_balance_bf}")
            
        if loan_errors:
            errors['loan'] = loan_errors

        sav_errors = []
        if self.savings_share_bf < 0: sav_errors.append("Savings B/F cannot be negative.")
        if self.savings_share_cf < 0: sav_errors.append("Savings C/F cannot be negative.")

        # Savings rule: savings_cf == savings_bf + shares
        if self.savings_share_cf != (self.savings_share_bf + self.shares_this_month):
            sav_errors.append(f"Mismatch. Expected: {self.savings_share_bf + self.shares_this_month}, Current: {self.savings_share_cf}")
            
        if sav_errors:
            errors['savings'] = sav_errors
            
        self.loan_valid = 'loan' not in errors
        self.savings_valid = 'savings' not in errors
        return errors


SECTION_CHOICES = [
    ('A', 'Section A – Advance Paid Today'),
    ('B', 'Section B – Cash Given Out Today'),
    ('C', 'Section C – INCOME'),
    ('D', 'Section D – EXPENSES'),
    ('E', 'Section E – Financial Reconciliation'),
]


class GroupPerformanceForm(models.Model):
    monthly_form = models.OneToOneField(MonthlyForm, on_delete=models.CASCADE, related_name='performance_form')
    notes = models.TextField(blank=True)
    
    # Next Meeting details
    next_meeting_date = models.DateField(null=True, blank=True)
    next_meeting_time = models.TimeField(null=True, blank=True)
    next_meeting_venue = models.CharField(max_length=255, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Performance – {self.monthly_form}"


class PerformanceEntry(models.Model):
    performance_form = models.ForeignKey(GroupPerformanceForm, on_delete=models.CASCADE, related_name='entries')
    section = models.CharField(max_length=1, choices=SECTION_CHOICES)
    description = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_paid = models.BooleanField(default=False)
    secondary_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tertiary_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['section', 'order']

    def __str__(self):
        return f"{self.get_section_display()} – {self.description}"

    def get_section_display(self):
        return dict(SECTION_CHOICES).get(self.section, self.section)


import datetime

class Expense(models.Model):
    date = models.DateField(default=datetime.date.today)
    name = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.name} - {self.amount}"
