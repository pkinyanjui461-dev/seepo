import datetime
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from groups.models import Group
from finance.models import MonthlyForm, GroupPerformanceForm, PerformanceEntry

from django.contrib.auth.decorators import login_required, user_passes_test


def is_management_or_ict(user):
    return user.is_authenticated and user.role in ['ict', 'management', 'admin']


@login_required
@user_passes_test(is_management_or_ict)
def reports_overview(request):
    groups = Group.objects.all().order_by('name')
    
    # Filtering setup
    today = datetime.date.today()
    selected_month = int(request.GET.get('month', today.month))
    selected_year = int(request.GET.get('year', today.year))
    
    report_data = []
    total_office_account_all = 0
    total_group_account_all = 0
    total_office_debt_all = 0
    
    for g in groups:
        # Get form for specific month/year
        mform = g.monthly_forms.filter(month=selected_month, year=selected_year).first()
        
        office_account = 0
        group_account = 0
        office_debt = 0
        
        if mform and hasattr(mform, 'performance_form'):
            perf_form = mform.performance_form
            
            b_entry = perf_form.entries.filter(section='E', description='Total Banking').first()
            if b_entry:
                if g.banking_type == 'group':
                    group_account = b_entry.amount
                else:
                    office_account = b_entry.amount
                
            d_entry = perf_form.entries.filter(section='E', description='Total Debt').first()
            if d_entry:
                office_debt = d_entry.amount
                
        report_data.append({
            'group_name': g.name,
            'office_account': office_account,
            'group_account': group_account,
            'office_debt': office_debt
        })
        
        total_office_account_all += office_account
        total_group_account_all += group_account
        total_office_debt_all += office_debt
        
    # Generate list of years and months for the filter dropdowns
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
    groups = Group.objects.all().order_by('name')
    
    # Filtering setup
    today = datetime.date.today()
    selected_month = int(request.GET.get('month', today.month))
    selected_year = int(request.GET.get('year', today.year))
    
    report_data = []
    total_service_fee_all = 0
    total_passbook_all = 0
    total_loan_form_all = 0
    total_mpesa_all = 0
    total_entities_all = 0
    total_risk_fund_all = 0
    
    for g in groups:
        mform = g.monthly_forms.filter(month=selected_month, year=selected_year).first()
        
        service_fee = 0
        passbook = 0
        loan_form = 0
        mpesa = 0
        risk_fund = 0
        
        if mform and hasattr(mform, 'performance_form'):
            perf_form = mform.performance_form
            
            # Extract from Section D (Expenses)
            sf_entry = perf_form.entries.filter(section='D', description='Service Fee').first()
            if sf_entry: service_fee = sf_entry.amount
                
            lf_entry = perf_form.entries.filter(section='D', description='Loan Forms').first()
            if lf_entry: loan_form = lf_entry.amount
                
            mp_entry = perf_form.entries.filter(section='D', description='Mpesa Charges').first()
            if mp_entry: mpesa = mp_entry.amount

            # Extract from Section C (Income)
            pb_entry = perf_form.entries.filter(section='C', description='Pass Book').first()
            if pb_entry: passbook = pb_entry.amount
                
        if mform:
            # Risk Fund is calculated from fines_charges
            rf_total = mform.member_records.aggregate(total=Sum('fines_charges'))['total'] or 0
            risk_fund = rf_total
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
