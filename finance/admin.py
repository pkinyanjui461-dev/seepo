from django.contrib import admin

from finance.models import CashReceipt, CashReceiptExpense, Expense, GroupPerformanceForm, MemberRecord, MonthlyForm, PerformanceEntry


class CashReceiptExpenseInline(admin.TabularInline):
    model = CashReceiptExpense
    extra = 0


@admin.register(CashReceipt)
class CashReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'receipt_date', 'officer_name', 'group', 'expected_amount', 'amount_deposited', 'missing_amount')
    list_filter = ('receipt_date', 'group')
    search_fields = ('receipt_number', 'officer_name', 'group__name')
    inlines = [CashReceiptExpenseInline]


admin.site.register(MonthlyForm)
admin.site.register(MemberRecord)
admin.site.register(GroupPerformanceForm)
admin.site.register(PerformanceEntry)
admin.site.register(Expense)
