import uuid
from decimal import Decimal

from django.db import models
from django.utils import timezone
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
    client_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    client_updated_at = models.DateTimeField(default=timezone.now, db_index=True)
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
    client_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    client_updated_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now, db_index=True)

    monthly_form = models.ForeignKey(MonthlyForm, on_delete=models.CASCADE, related_name='member_records')
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    order = models.PositiveSmallIntegerField(default=0)

    # Financial columns
    savings_share_bf = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    loan_balance_bf = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    total_repaid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    principal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    loan_interest = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    shares_this_month = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    withdrawals = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    fines_charges = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    savings_share_cf = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    loan_balance_cf = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))

    # Validation flags
    savings_valid = models.BooleanField(default=True)
    loan_valid = models.BooleanField(default=True)

    # Override flags
    savings_bf_overridden = models.BooleanField(default=False)
    loan_bf_overridden = models.BooleanField(default=False)

    class Meta:
        ordering = ['order', 'member__name']
        unique_together = ('monthly_form', 'member')

    def __str__(self):
        return f"{self.member.name} – {self.monthly_form}"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            kwargs['update_fields'] = set(update_fields) | {'updated_at'}
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)

    def calculate(self):
        """Backend calculation mirror of JS logic."""
        from decimal import Decimal, ROUND_HALF_UP

        # Round the user input values
        self.savings_share_bf = Decimal(str(self.savings_share_bf)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        self.loan_balance_bf = Decimal(str(self.loan_balance_bf)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        self.principal = Decimal(str(self.principal)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        self.total_repaid = Decimal(str(self.total_repaid)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        self.withdrawals = Decimal(str(self.withdrawals)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        self.fines_charges = Decimal(str(self.fines_charges)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

        # Calculated fields
        self.loan_interest = (self.loan_balance_bf * Decimal('0.015')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        # If total repaid is 0, shares this month is 0.
        # If principal is 0 OR there are withdrawals, interest/principal is NOT deducted from repaid.
        if self.total_repaid <= 0:
            self.shares_this_month = Decimal('0')
        elif self.principal == 0 or self.withdrawals > 0:
            self.shares_this_month = self.total_repaid
        else:
            # Deduct principal and interest, but don't let shares go negative
            calc_shares = self.total_repaid - (self.principal + self.loan_interest)
            self.shares_this_month = max(Decimal('0'), calc_shares)
        self.savings_share_cf = (self.savings_share_bf + self.shares_this_month - self.withdrawals).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        self.loan_balance_cf = (self.loan_balance_bf - self.principal).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

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

        # Savings rule: savings_cf == savings_bf + shares - withdrawals
        if self.savings_share_cf != (self.savings_share_bf + self.shares_this_month - self.withdrawals):
            sav_errors.append(f"Mismatch. Expected: {self.savings_share_bf + self.shares_this_month - self.withdrawals}, Current: {self.savings_share_cf}")

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
    client_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    client_updated_at = models.DateTimeField(default=timezone.now, db_index=True)
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

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            kwargs['update_fields'] = set(update_fields) | {'client_updated_at'}
        self.client_updated_at = timezone.now()
        super().save(*args, **kwargs)


class PerformanceEntry(models.Model):
    client_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    client_updated_at = models.DateTimeField(default=timezone.now, db_index=True)
    performance_form = models.ForeignKey(GroupPerformanceForm, on_delete=models.CASCADE, related_name='entries')
    section = models.CharField(max_length=1, choices=SECTION_CHOICES)
    description = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    is_paid = models.BooleanField(default=False)
    secondary_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    tertiary_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['section', 'order']

    def __str__(self):
        return f"{self.get_section_display()} – {self.description}"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            kwargs['update_fields'] = set(update_fields) | {'client_updated_at'}
        self.client_updated_at = timezone.now()
        super().save(*args, **kwargs)

    def get_section_display(self):
        return dict(SECTION_CHOICES).get(self.section, self.section)


import datetime

class Expense(models.Model):
    date = models.DateField(default=datetime.date.today)
    name = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    client_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    client_updated_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.name} - {self.amount}"


class CashReceipt(models.Model):
    receipt_number = models.CharField(max_length=80, unique=True)
    receipt_date = models.DateField(default=datetime.date.today)
    officer = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='cash_receipts')
    officer_name = models.CharField(max_length=200)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='cash_receipts')
    receipt_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    total_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    expected_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    amount_deposited = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    missing_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    excess_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    notes = models.TextField(blank=True)
    client_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    client_updated_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_cash_receipts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-receipt_date', 'group__name']
        unique_together = ('receipt_date', 'group')

    def __str__(self):
        return f"{self.receipt_number} - {self.group.name}"

    @property
    def status(self):
        if self.missing_amount > 0:
            return 'short'
        if self.excess_amount > 0:
            return 'over'
        return 'balanced'

    def calculate(self):
        self.total_expenses = sum((expense.amount for expense in self.expenses.all()), Decimal('0'))
        self.expected_amount = self.receipt_amount - self.total_expenses
        expected_deposit = max(self.expected_amount, Decimal('0'))
        self.missing_amount = max(expected_deposit - self.amount_deposited, Decimal('0'))
        self.excess_amount = max(self.amount_deposited - expected_deposit, Decimal('0'))

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            kwargs['update_fields'] = set(update_fields) | {'client_updated_at'}
        self.client_updated_at = timezone.now()
        if self.pk:
            self.calculate()
        else:
            self.total_expenses = self.total_expenses or Decimal('0')
            self.expected_amount = self.receipt_amount - self.total_expenses
            expected_deposit = max(self.expected_amount, Decimal('0'))
            self.missing_amount = max(expected_deposit - self.amount_deposited, Decimal('0'))
            self.excess_amount = max(self.amount_deposited - expected_deposit, Decimal('0'))
        super().save(*args, **kwargs)


class CashReceiptExpense(models.Model):
    cash_receipt = models.ForeignKey(CashReceipt, on_delete=models.CASCADE, related_name='expenses')
    name = models.CharField(max_length=160)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'pk']

    def __str__(self):
        return f"{self.name} - {self.amount}"


class MemberMoneySend(models.Model):
    send_date = models.DateField(default=datetime.date.today, db_index=True)
    member_name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=30, blank=True)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='member_money_sends')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_sent = models.BooleanField(default=False, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_member_money_sends')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['send_date', 'group__name', 'member_name']

    def __str__(self):
        return f"{self.member_name} - {self.group.name} - {self.amount}"
