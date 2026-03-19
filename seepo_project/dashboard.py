from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count


@login_required
def dashboard(request):
    from groups.models import Group
    from members.models import Member
    from finance.models import MemberRecord, MonthlyForm
    from accounts.models import User

    groups = Group.objects.all()
    total_groups = groups.count()
    total_members = Member.objects.filter(is_active=True).count()

    # Financial overview
    savings_qs = MemberRecord.objects.aggregate(total=Sum('savings_share_cf'))
    loans_qs = MemberRecord.objects.aggregate(total=Sum('loan_balance_cf'))
    total_savings = savings_qs['total'] or 0
    total_loans = loans_qs['total'] or 0

    # Chart data: savings per group
    chart_labels = []
    chart_savings = []
    chart_loans = []
    for g in groups:
        chart_labels.append(g.name)
        s = MemberRecord.objects.filter(monthly_form__group=g).aggregate(t=Sum('savings_share_cf'))['t'] or 0
        l = MemberRecord.objects.filter(monthly_form__group=g).aggregate(t=Sum('loan_balance_cf'))['t'] or 0
        chart_savings.append(float(s))
        chart_loans.append(float(l))

    # Officer Activity (for admins)
    officer_activity = []
    if request.user.role in ['admin', 'ict']:
        officer_activity = User.objects.filter(role='officer').annotate(
            form_count=Count('monthlyform')
        ).order_by('-form_count')

    return render(request, 'dashboard.html', {
        'total_groups': total_groups,
        'total_members': total_members,
        'total_savings': total_savings,
        'total_loans': total_loans,
        'groups': groups[:5],  # Recent groups
        'chart_labels': chart_labels,
        'chart_savings': chart_savings,
        'chart_loans': chart_loans,
        'officer_activity': officer_activity,
    })
