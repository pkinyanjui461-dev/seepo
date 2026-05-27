import datetime
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from groups.models import Group
from finance.models import MonthlyForm, GroupPerformanceForm, PerformanceEntry

from django.contrib.auth.decorators import login_required, user_passes_test


from django.utils import timezone
from django.db.models import Sum, Q, Prefetch

def is_management_or_ict(user):
    return user.is_authenticated and user.role in ['ict', 'management', 'admin']

@login_required
@user_passes_test(is_management_or_ict)
def reports_overview(request):
    today = timezone.localdate()
    selected_month = int(request.GET.get('month', today.month))
    selected_year = int(request.GET.get('year', today.year))
    
    mforms_prefetch = Prefetch(
        'monthly_forms',
        queryset=MonthlyForm.objects.filter(month=selected_month, year=selected_year).select_related('performance_form').prefetch_related(
            Prefetch(
                'performance_form__entries',
                queryset=PerformanceEntry.objects.filter(section='E', description__in=['Total Banking', 'Total Debt']),
                to_attr='relevant_entries'
            )
        ),
        to_attr='current_mforms'
    )
    
    groups = Group.objects.all().order_by('name').prefetch_related(mforms_prefetch)
    
    report_data = []
    total_office_account_all = 0
    total_group_account_all = 0
    total_office_debt_all = 0
    
    for g in groups:
        office_account = 0
        group_account = 0
        office_debt = 0
        
        mform = g.current_mforms[0] if g.current_mforms else None
        
        if mform and hasattr(mform, 'performance_form') and mform.performance_form:
            for entry in getattr(mform.performance_form, 'relevant_entries', []):
                if entry.description == 'Total Banking':
                    if g.banking_type == 'group':
                        group_account = entry.amount
                    else:
                        office_account = entry.amount
                elif entry.description == 'Total Debt':
                    office_debt = entry.amount
                    
        report_data.append({
            'group_name': g.name,
            'office_account': office_account,
            'group_account': group_account,
            'office_debt': office_debt
        })
        
        total_office_account_all += office_account
        total_group_account_all += group_account
        total_office_debt_all += office_debt
        
    available_years = list(range(today.year - 5, today.year + 2))
    months = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]
    
    context = {
        'report_data': report_data,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'months': months,
        'available_years': available_years,
        'total_office_account_all': total_office_account_all,
        'total_group_account_all': total_group_account_all,
        'total_office_debt_all': total_office_debt_all
    }
    
    return render(request, 'reports/overview.html', context)


@login_required
@user_passes_test(is_management_or_ict)
def entities_report(request):
    today = timezone.localdate()
    selected_month = int(request.GET.get('month', today.month))
    selected_year = int(request.GET.get('year', today.year))
    
    mforms_prefetch = Prefetch(
        'monthly_forms',
        queryset=MonthlyForm.objects.filter(
            month=selected_month, year=selected_year
        ).annotate(
            risk_fund_total=Sum('member_records__fines_charges')
        ).select_related('performance_form').prefetch_related(
            Prefetch(
                'performance_form__entries',
                queryset=PerformanceEntry.objects.filter(
                    Q(section='D', description__in=['Service Fee', 'Loan Forms', 'Mpesa Charges']) |
                    Q(section='C', description='Pass Book')
                ),
                to_attr='relevant_entries'
            )
        ),
        to_attr='current_mforms'
    )
    
    groups = Group.objects.all().order_by('name').prefetch_related(mforms_prefetch)
    
    report_data = []
    total_service_fee_all = 0
    total_passbook_all = 0
    total_loan_form_all = 0
    total_mpesa_all = 0
    total_entities_all = 0
    total_risk_fund_all = 0
    
    for g in groups:
        service_fee = 0
        passbook = 0
        loan_form = 0
        mpesa = 0
        risk_fund = 0
        
        mform = g.current_mforms[0] if g.current_mforms else None
        
        if mform and hasattr(mform, 'performance_form') and mform.performance_form:
            for entry in getattr(mform.performance_form, 'relevant_entries', []):
                if entry.section == 'D' and entry.description == 'Service Fee': service_fee = entry.amount
                elif entry.section == 'D' and entry.description == 'Loan Forms': loan_form = entry.amount
                elif entry.section == 'D' and entry.description == 'Mpesa Charges': mpesa = entry.amount
                elif entry.section == 'C' and entry.description == 'Pass Book': passbook = entry.amount
                
        if mform:
            risk_fund = getattr(mform, 'risk_fund_total', 0) or 0
            
        totals_entities = service_fee + passbook + loan_form + mpesa
        
        report_data.append({
            'group_name': g.name,
            'service_fee': service_fee,
            'passbook': passbook,
            'loan_form': loan_form,
            'mpesa': mpesa,
            'totals_entities': totals_entities,
            'risk_fund': risk_fund
        })
        
        total_service_fee_all += service_fee
        total_passbook_all += passbook
        total_loan_form_all += loan_form
        total_mpesa_all += mpesa
        total_entities_all += totals_entities
        total_risk_fund_all += risk_fund
        
    available_years = list(range(today.year - 5, today.year + 2))
    months = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]
    
    context = {
        'report_data': report_data,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'months': months,
        'available_years': available_years,
        'total_service_fee_all': total_service_fee_all,
        'total_passbook_all': total_passbook_all,
        'total_loan_form_all': total_loan_form_all,
        'total_mpesa_all': total_mpesa_all,
        'total_entities_all': total_entities_all,
        'total_risk_fund_all': total_risk_fund_all
    }
    
    return render(request, 'reports/entities_report.html', context)
