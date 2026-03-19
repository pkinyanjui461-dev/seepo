from django.contrib import admin
from accounts.models import User
from groups.models import Group
from members.models import Member
from finance.models import MonthlyForm, MemberRecord, GroupPerformanceForm, PerformanceEntry


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'get_full_name', 'email', 'role', 'is_active']
    list_filter = ['role', 'is_active']


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'officer_name', 'date_created', 'member_count']
    search_fields = ['name', 'location']


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'group', 'phone', 'join_date', 'is_active']
    list_filter = ['group', 'is_active']
    search_fields = ['name', 'phone']


class MemberRecordInline(admin.TabularInline):
    model = MemberRecord
    extra = 0


@admin.register(MonthlyForm)
class MonthlyFormAdmin(admin.ModelAdmin):
    list_display = ['group', 'month', 'year', 'status', 'created_at']
    list_filter = ['group', 'status', 'year']
    inlines = [MemberRecordInline]


@admin.register(PerformanceEntry)
class PerformanceEntryAdmin(admin.ModelAdmin):
    list_display = ['performance_form', 'section', 'description', 'amount']
    list_filter = ['section']
