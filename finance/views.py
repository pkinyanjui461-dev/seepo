import json
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from groups.models import Group
from members.models import Member
from finance.models import (
    MonthlyForm, MemberRecord, GroupPerformanceForm, PerformanceEntry, SECTION_CHOICES
)
from finance.forms import MonthlyFormForm
from finance.utils import generate_pdf_response
from django.conf import settings
import calendar


@login_required
def monthly_form_list(request, group_pk):
    group = get_object_or_404(Group, pk=group_pk)
    forms = group.monthly_forms.all()
    return render(request, 'finance/monthly_form_list.html', {'group': group, 'forms': forms})


@login_required
def monthly_form_create(request, group_pk):
    group = get_object_or_404(Group, pk=group_pk)
    form = MonthlyFormForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        mform = form.save(commit=False)
        mform.group = group
        mform.created_by = request.user
        
        # Check for duplicates before saving to give a friendly error
        from django.db import IntegrityError
        month = mform.month
        year = mform.year
        if MonthlyForm.objects.filter(group=group, month=month, year=year).exists():
            month_name = calendar.month_name[month]
            messages.error(request, f'A form for {month_name} {year} already exists for this group.')
            return render(request, 'finance/monthly_form_form.html', {
                'form': form, 'group': group, 'title': 'Create Monthly Form'
            })
        
        mform.save()
        
        # Determine the most recent previous form for this group
        # Sort by year descending, month descending
        previous_form = group.monthly_forms.exclude(pk=mform.pk).order_by('-year', '-month').first()
        
        # Build a fast lookup dict of previous member records
        prev_records = {}
        if previous_form:
            prev_records = {r.member_id: r for r in previous_form.member_records.all()}

        # Auto-create MemberRecord rows for all active members
        members = group.member_set.filter(is_active=True)
        for i, member in enumerate(members):
            savings_bf = Decimal('0')
            loan_bf = Decimal('0')
            
            # Auto-carry forward logic
            if previous_form and member.id in prev_records:
                prev_record = prev_records[member.id]
                savings_bf = prev_record.savings_share_cf
                loan_bf = prev_record.loan_balance_cf
                
                # ALSO add loans given in Performance Form Section B
                if hasattr(previous_form, 'performance_form'):
                    p_entry = previous_form.performance_form.entries.filter(section='B', description=member.name).first()
                    if p_entry:
                        loan_bf += p_entry.secondary_amount
                
            record, created = MemberRecord.objects.get_or_create(
                monthly_form=mform, 
                member=member,
                defaults={
                    'order': i,
                    'savings_share_bf': savings_bf,
                    'loan_balance_bf': loan_bf
                }
            )
            # Ensure the CF/calculations trigger on save
            if created:
                record.calculate()
                record.save()
                
        messages.success(request, 'Monthly form created successfully.')
        return redirect('monthly_form_detail', pk=mform.pk)
    
    return render(request, 'finance/monthly_form_form.html', {
        'form': form, 'group': group, 'title': 'Create Monthly Form'
    })


@login_required
def monthly_form_detail(request, pk):
    mform = get_object_or_404(MonthlyForm, pk=pk)
    group = mform.group
    records = mform.member_records.select_related('member').order_by('order', 'member__name')

    # Ensure all active members have a record
    existing_member_ids = records.values_list('member_id', flat=True)
    new_members = group.member_set.filter(is_active=True).exclude(id__in=existing_member_ids)
    
    # If a previous form exists, grab default carry forwards for newly added active members too
    previous_form = group.monthly_forms.exclude(pk=mform.pk).order_by('-year', '-month').first()
    prev_records = {}
    if previous_form:
        prev_records = {r.member_id: r for r in previous_form.member_records.all()}

    for i, member in enumerate(new_members):
        savings_bf = Decimal('0')
        loan_bf = Decimal('0')
        if previous_form and member.id in prev_records:
            prev_record = prev_records[member.id]
            savings_bf = prev_record.savings_share_cf
            loan_bf = prev_record.loan_balance_cf

            # ALSO add loans given in Performance Form Section B
            if hasattr(previous_form, 'performance_form'):
                p_entry = previous_form.performance_form.entries.filter(section='B', description=member.name).first()
                if p_entry:
                    loan_bf += p_entry.secondary_amount
            
        record = MemberRecord.objects.create(
            monthly_form=mform, 
            member=member, 
            order=records.count() + i,
            savings_share_bf=savings_bf,
            loan_balance_bf=loan_bf
        )
        record.calculate()
        record.save()
        
    records = mform.member_records.select_related('member').order_by('order', 'member__name')

    # Totals
    def total(field):
        return sum(getattr(r, field) for r in records) or 0

    totals = {
        'savings_share_bf': total('savings_share_bf'),
        'loan_balance_bf': total('loan_balance_bf'),
        'total_repaid': total('total_repaid'),
        'principal': total('principal'),
        'loan_interest': total('loan_interest'),
        'shares_this_month': total('shares_this_month'),
        'withdrawals': total('withdrawals'),
        'fines_charges': total('fines_charges'),
        'savings_share_cf': total('savings_share_cf'),
        'loan_balance_cf': total('loan_balance_cf'),
    }

    # Totals validation
    totals_loan_valid = totals['loan_balance_bf'] == (totals['principal'] + totals['loan_balance_cf'])
    totals_savings_valid = totals['savings_share_cf'] == (totals['savings_share_bf'] + totals['shares_this_month'] - totals['withdrawals'])

    try:
        perf_form = mform.performance_form
    except GroupPerformanceForm.DoesNotExist:
        perf_form = None

    return render(request, 'finance/monthly_form_detail.html', {
        'mform': mform,
        'group': group,
        'records': records,
        'totals': totals,
        'totals_loan_valid': totals_loan_valid,
        'totals_savings_valid': totals_savings_valid,
        'perf_form': perf_form,
    })


@login_required
@require_POST
def save_member_record(request, record_pk):
    """AJAX endpoint: save a single member record row."""
    record = get_object_or_404(MemberRecord, pk=record_pk)
    try:
        data = json.loads(request.body)
        fields = ['savings_share_bf', 'loan_balance_bf', 'total_repaid', 'principal',
                  'loan_interest', 'shares_this_month', 'withdrawals', 'fines_charges', 'savings_share_cf', 'loan_balance_cf']
        for f in fields:
            if f in data:
                try:
                    setattr(record, f, Decimal(str(data[f])))
                except (InvalidOperation, TypeError):
                    setattr(record, f, Decimal('0'))
        errors = record.validate()
        record.save()
        return JsonResponse({'success': True, 'errors': errors, 'record_id': record.pk})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def performance_form_view(request, mform_pk):
    mform = get_object_or_404(MonthlyForm, pk=mform_pk)
    perf_form, created = GroupPerformanceForm.objects.get_or_create(monthly_form=mform)
    
    from finance.utils import ensure_performance_form_initialized
    banking_bf, debt_bf = ensure_performance_form_initialized(perf_form)

    # For existing forms, these will be the default fallback for the template
    initial_banking_bf = banking_bf
    initial_debt_bf = debt_bf

    # Get active members for this group/month to display in Section A
    members = mform.member_records.select_related('member').order_by('order', 'member__name')

    if request.method == 'POST':
        # Save section entries from POST
        perf_form.entries.all().delete()
        sections = request.POST.getlist('section')
        descriptions = request.POST.getlist('description')
        amounts = request.POST.getlist('amount')
        
        # New fields for Section A checkboxes, secondary amounts, and Section B tertiary amounts
        is_paid_list = request.POST.getlist('is_paid')
        secondary_amounts = request.POST.getlist('secondary_amount')
        tertiary_amounts = request.POST.getlist('tertiary_amount')

        for i, (sec, desc, amt) in enumerate(zip(sections, descriptions, amounts)):
            if desc.strip():
                try:
                    amount = Decimal(amt or '0')
                except InvalidOperation:
                    amount = Decimal('0')
                
                # Safely get is_paid and secondary_amount for this row (if they exist)
                is_paid = False
                if i < len(is_paid_list):
                    is_paid = is_paid_list[i].lower() == 'true'
                
                try:
                    sec_amt_val = secondary_amounts[i] if i < len(secondary_amounts) else '0'
                    secondary_amount = Decimal(sec_amt_val or '0')
                except InvalidOperation:
                    secondary_amount = Decimal('0')
                    
                try:
                    tert_amt_val = tertiary_amounts[i] if i < len(tertiary_amounts) else '0'
                    tertiary_amount = Decimal(tert_amt_val or '0')
                except InvalidOperation:
                    tertiary_amount = Decimal('0')

                PerformanceEntry.objects.create(
                    performance_form=perf_form, 
                    section=sec, 
                    description=desc, 
                    amount=amount,
                    is_paid=is_paid,
                    secondary_amount=secondary_amount,
                    tertiary_amount=tertiary_amount,
                    order=i
                )
        
        # Save Next Meeting values
        nm_date = request.POST.get('next_meeting_date')
        nm_time = request.POST.get('next_meeting_time')
        nm_venue = request.POST.get('next_meeting_venue')
        
        if nm_date:
            try:
                from datetime import datetime
                d_obj = datetime.strptime(nm_date, '%Y-%m-%d').date()
                perf_form.next_meeting_date = d_obj
                
                # Sync to DiaryEntry
                from groups.models import DiaryEntry
                diary, _ = DiaryEntry.objects.get_or_create(group=mform.group)
                
                # Update venue/time if provided
                if nm_venue: diary.venue = nm_venue
                if nm_time: diary.time = nm_time
                
                # Get month field name
                month_name = d_obj.strftime('%B').lower()
                # Day formatting (e.g. 15 -> 15th)
                day = d_obj.day
                suffix = 'th' if 11<=day<=13 else {1:'st',2:'nd',3:'rd'}.get(day%10, 'th')
                day_str = f"{day}{suffix}"
                
                if hasattr(diary, month_name):
                    setattr(diary, month_name, day_str)
                diary.save()
            except (ValueError, TypeError):
                pass
                
        if nm_time:
            try:
                perf_form.next_meeting_time = nm_time
            except (ValueError, TypeError):
                pass
                
        if nm_venue:
            perf_form.next_meeting_venue = nm_venue
            
        perf_form.notes = request.POST.get('comments', '')
        perf_form.save()

        messages.success(request, 'Performance form saved.')
        return redirect('performance_form', mform_pk=mform.pk)

    entries_by_section = {}
    for code, label in SECTION_CHOICES:
        # For section A, we will construct total slightly differently in JS, but backend total is total amount
        entries = perf_form.entries.filter(section=code)
        # Advance total only counts PAID ones. Others sum normally.
        if code == 'A':
            total = sum(e.amount for e in entries if e.is_paid)
            secondary_total = sum(e.secondary_amount for e in entries)
            tertiary_total = Decimal('0')
        elif code == 'B':
            total = sum(e.amount for e in entries)
            secondary_total = sum(e.secondary_amount for e in entries)
            tertiary_total = sum(e.tertiary_amount for e in entries)
        else:
            total = sum(e.amount for e in entries)
            secondary_total = Decimal('0')
            tertiary_total = Decimal('0')

        entries_by_section[code] = {
            'label': label,
            'entries': entries,
            'total': total,
            'secondary_total': secondary_total,
            'tertiary_total': tertiary_total
        }

    from django.db.models import Sum, Q
    accounting_totals = mform.member_records.aggregate(
        total_repaid=Sum('total_repaid'),
        total_savings_cf=Sum('savings_share_cf'),
        total_loans_cf=Sum('loan_balance_cf')
    )
    accounting_total_repaid = accounting_totals['total_repaid'] or Decimal('0')
    total_savings_cf = accounting_totals['total_savings_cf'] or Decimal('0')
    total_loans_cf = accounting_totals['total_loans_cf'] or Decimal('0')

    return render(request, 'finance/performance_form.html', {
        'mform': mform,
        'perf_form': perf_form,
        'entries_by_section': entries_by_section,
        'section_choices': SECTION_CHOICES,
        'members': members,
        'accounting_total_repaid': accounting_total_repaid,
        'initial_banking_bf': initial_banking_bf,
        'initial_debt_bf': initial_debt_bf,
        'total_savings_cf': total_savings_cf,
        'total_loans_cf': total_loans_cf,
    })


@login_required
@require_POST
def monthly_form_delete(request, pk):
    from django.urls import reverse
    mform = get_object_or_404(MonthlyForm, pk=pk)
    group = mform.group
    mform.delete()
    messages.success(request, 'Accounting form deleted successfully.')
    return redirect(f"{reverse('group_detail', args=[group.pk])}?tab=forms")


@login_required
def api_dashboard_stats(request):
    from django.db.models import Sum
    """JSON endpoint for dashboard chart aggregate data based on latest active month."""
    groups = Group.objects.all()
    
    # Target the most recent month that actually has performance entries populated that are not automatic carry-forwards
    from django.db.models import Q
    latest_global_form = MonthlyForm.objects.filter(
        Q(performance_form__entries__description__in=['Service Fee', 'Pass Book', 'Loan Forms', 'Mpesa Charges'], performance_form__entries__amount__gt=0) |
        Q(member_records__fines_charges__gt=0)
    ).order_by('-year', '-month').first()
    
    # Fallback to current month if no forms at all
    from datetime import date
    target_year = latest_global_form.year if latest_global_form else date.today().year
    target_month = latest_global_form.month if latest_global_form else date.today().month

    total_banking = 0
    total_office_debt = 0
    total_service_fee = 0
    total_passbook = 0
    total_loan_form = 0
    total_mpesa = 0
    total_risk_fund = 0
    
    for g in groups:
        latest_form = g.monthly_forms.filter(year=target_year, month=target_month).first()
        
        if latest_form and hasattr(latest_form, 'performance_form'):
            perf_form = latest_form.performance_form
            
            b_entry = perf_form.entries.filter(section='E', description='Total Banking').first()
            if b_entry: total_banking += float(b_entry.amount)
            
            d_entry = perf_form.entries.filter(section='E', description='Total Debt').first()
            if d_entry: total_office_debt += float(d_entry.amount)

            sf_entry = perf_form.entries.filter(section='D', description='Service Fee').first()
            if sf_entry: total_service_fee += float(sf_entry.amount)
            
            lf_entry = perf_form.entries.filter(section='D', description='Loan Forms').first()
            if lf_entry: total_loan_form += float(lf_entry.amount)
            
            mp_entry = perf_form.entries.filter(section='D', description='Mpesa Charges').first()
            if mp_entry: total_mpesa += float(mp_entry.amount)

            pb_entry = perf_form.entries.filter(section='C', description='Pass Book').first()
            if pb_entry: total_passbook += float(pb_entry.amount)
            
        if latest_form:
            # Risk Fund is calculated from all fines and charges for that month
            rf_total = latest_form.member_records.aggregate(total=Sum('fines_charges'))['total'] or 0
            total_risk_fund += float(rf_total)

    totals_entities = total_service_fee + total_passbook + total_loan_form + total_mpesa

    return JsonResponse({
        'target_month': target_month,
        'target_year': target_year,
        'banking': total_banking,
        'office_debt': total_office_debt,
        'service_fee': total_service_fee,
        'passbook': total_passbook,
        'loan_form': total_loan_form,
        'mpesa': total_mpesa,
        'totals_entities': totals_entities,
        'risk_fund': total_risk_fund
    })
def _get_monthly_form_data(mform):
    """Helper to get common records and totals for PDF contexts."""
    records = mform.member_records.select_related('member').order_by('order', 'member__name')
    def total(field):
        return sum(getattr(r, field) for r in records) or 0
    totals = {
        'savings_share_bf': total('savings_share_bf'),
        'loan_balance_bf': total('loan_balance_bf'),
        'total_repaid': total('total_repaid'),
        'principal': total('principal'),
        'loan_interest': total('loan_interest'),
        'shares_this_month': total('shares_this_month'),
        'withdrawals': total('withdrawals'),
        'fines_charges': total('fines_charges'),
        'savings_share_cf': total('savings_share_cf'),
        'loan_balance_cf': total('loan_balance_cf'),
    }
    totals['is_blank_mode'] = (totals['total_repaid'] == 0)
    return records, totals

def _get_perf_summary(mform, totals, sections):
    """Calculates Group Summary values matching the web interface formulas."""
    shares = totals.get('savings_share_cf', 0)
    adv = sum(e.tertiary_amount for e in sections.get('B', [])) + sum(e.amount for e in sections.get('A', []) if not e.is_paid)
    loans = totals.get('loan_balance_cf', 0) + sum(e.secondary_amount for e in sections.get('B', []))
    banking = sum(e.amount for e in sections.get('E', []) if e.description == 'Total Banking')
    office_debt = sum(e.amount for e in sections.get('E', []) if e.description == 'Total Debt')
    trf = adv + loans + banking
    interest = trf - (shares + office_debt)
    
    return {
        'shares': shares,
        'loans': loans,
        'adv': adv,
        'banking': banking,
        'trf': trf,
        'interest': interest,
        'office_debt': office_debt,
    }


@login_required
def monthly_form_pdf(request, pk):
    """Generates PDF for the Accounting Sheet (Member Records)."""
    mform = get_object_or_404(MonthlyForm, pk=pk)
    
    from finance.models import GroupPerformanceForm
    from finance.utils import ensure_performance_form_initialized
    perf_form, _ = GroupPerformanceForm.objects.get_or_create(monthly_form=mform)
    ensure_performance_form_initialized(perf_form)
    
    records, totals = _get_monthly_form_data(mform)
    padding = range(max(0, 15 - records.count()))
    
    # Calculate performance summary for the header
    entries = perf_form.entries.all().order_by('section', 'order')
    sections = {
        'B': [e for e in entries if e.section == 'B'],
        'E': [e for e in entries if e.section == 'E'],
    }
    perf_summary = _get_perf_summary(mform, totals, sections)
    
    from django.utils.text import slugify
    filename = slugify(f"accounting_sheet_{mform.group.name}_{mform.get_month_name()}_{mform.year}") + ".pdf"
    inline = request.GET.get('inline') == '1'
    return generate_pdf_response('pdf/accounting_sheet_pdf.html', {
        'mform': mform,
        'records': records,
        'totals': totals,
        'padding': padding,
        'perf_summary': perf_summary,
        'base_dir': settings.BASE_DIR,
    }, filename, inline=inline)

@login_required
def performance_form_pdf(request, pk):
    """Generates PDF for the Monthly Performance Form."""
    mform = get_object_or_404(MonthlyForm, pk=pk)
    perf_form, _ = GroupPerformanceForm.objects.get_or_create(monthly_form=mform)
    
    from finance.utils import ensure_performance_form_initialized
    ensure_performance_form_initialized(perf_form)
    
    records, totals = _get_monthly_form_data(mform)
    
    # Performance specific logic
    entries = perf_form.entries.all().order_by('section', 'order')
    sections = {
        'A': [e for e in entries if e.section == 'A'],
        'B': [e for e in entries if e.section == 'B'],
        'C': [e for e in entries if e.section == 'C'],
        'D': [e for e in entries if e.section == 'D'],
        'E': [e for e in entries if e.section == 'E'],
    }
    section_totals = {
        'A_bf': sum(e.amount for e in sections['A']),
        'A_paid': sum(e.secondary_amount for e in sections['A']),
        'A_fines': sum(e.tertiary_amount for e in sections['A']),
        'B_with': sum(e.amount for e in sections['B']),
        'B_loan': sum(e.secondary_amount for e in sections['B']),
        'B_adv': sum(e.tertiary_amount for e in sections['B']),
        'C': sum(e.amount for e in sections['C']),
        'D': sum(e.amount for e in sections['D']),
    }
    # Dynamic synchronization for Section C and D (Automatic fields)
    a_paid_total = sum(e.amount for e in sections['A'] if e.is_paid)
    for e in sections['C']:
        if e.description == 'Total Repaid': e.amount = totals.get('total_repaid', 0)
        elif e.description == 'Advance Paid': e.amount = a_paid_total
    
    for e in sections['D']:
        if e.description == 'Withdrawals': e.amount = section_totals['B_with']
        elif e.description == 'Loans Given': e.amount = section_totals['B_loan']
        elif e.description == 'Advance Given': e.amount = section_totals['B_adv']
    
    # Recalculate totals after dynamic overrides
    section_totals['C'] = sum(e.amount for e in sections['C'])
    section_totals['D'] = sum(e.amount for e in sections['D'])

    adv_total = sum(e.amount for e in sections['A'] if e.is_paid)
    perf_summary = _get_perf_summary(mform, totals, sections)

    
    from django.utils.text import slugify
    filename = slugify(f"performance_form_{mform.group.name}_{mform.get_month_name()}_{mform.year}") + ".pdf"
    inline = request.GET.get('inline') == '1'

    # Build a name -> member_number lookup for the PDF template
    from members.models import Member
    member_num_map = {
        m.name: m.member_number
        for m in Member.objects.filter(group=mform.group)
        if m.member_number is not None
    }

    return generate_pdf_response('pdf/performance_form_pdf.html', {
        'mform': mform,
        'perf_form': perf_form,
        'records': records,
        'totals': totals,
        'sections': sections,
        'section_totals': section_totals,
        'perf_summary': perf_summary,
        'base_dir': settings.BASE_DIR,
        'member_num_map': member_num_map,
    }, filename, inline=inline, use_reportlab=True)

@login_required
def combined_monthly_report_pdf(request, pk):
    """Generates a two-page PDF: Page 1 Accounting Sheet, Page 2 Performance Form."""
    mform = get_object_or_404(MonthlyForm, pk=pk)
    perf_form, _ = GroupPerformanceForm.objects.get_or_create(monthly_form=mform)
    
    from finance.utils import ensure_performance_form_initialized
    ensure_performance_form_initialized(perf_form)
    
    records, totals = _get_monthly_form_data(mform)
    
    from finance.utils import render_to_pdf, render_performance_form_reportlab, merge_pdf_bytes, generate_pdf_response
    
    # 1. Page 1: Accounting Sheet Bytes
    padding = range(max(0, 15 - records.count()))
    
    # Calculate performance summary for the first page header
    entries = perf_form.entries.all().order_by('section', 'order')
    sections = {
        'B': [e for e in entries if e.section == 'B'],
        'E': [e for e in entries if e.section == 'E'],
    }
    perf_summary = _get_perf_summary(mform, totals, sections)
    
    accounting_pdf = render_to_pdf('pdf/accounting_sheet_pdf.html', {
        'mform': mform,
        'records': records,
        'totals': totals,
        'padding': padding,
        'perf_summary': perf_summary,
        'base_dir': settings.BASE_DIR,
    })
    
    # 2. Page 2: Performance Form Bytes
    entries = perf_form.entries.all().order_by('section', 'order')
    sections = {
        'A': [e for e in entries if e.section == 'A'],
        'B': [e for e in entries if e.section == 'B'],
        'C': [e for e in entries if e.section == 'C'],
        'D': [e for e in entries if e.section == 'D'],
        'E': [e for e in entries if e.section == 'E'],
    }
    section_totals = {
        'A_bf': sum(e.amount for e in sections['A']),
        'A_paid': sum(e.secondary_amount for e in sections['A']),
        'A_fines': sum(e.tertiary_amount for e in sections['A']),
        'B_with': sum(e.amount for e in sections['B']),
        'B_loan': sum(e.secondary_amount for e in sections['B']),
        'B_adv': sum(e.tertiary_amount for e in sections['B']),
        'C': sum(e.amount for e in sections['C']),
        'D': sum(e.amount for e in sections['D']),
    }
    # Dynamic synchronization for Section C and D (Automatic fields)
    a_paid_total = sum(e.amount for e in sections['A'] if e.is_paid)
    for e in sections['C']:
        if e.description == 'Total Repaid': e.amount = totals.get('total_repaid', 0)
        elif e.description == 'Advance Paid': e.amount = a_paid_total
    
    for e in sections['D']:
        if e.description == 'Withdrawals': e.amount = section_totals['B_with']
        elif e.description == 'Loans Given': e.amount = section_totals['B_loan']
        elif e.description == 'Advance Given': e.amount = section_totals['B_adv']
    
    # Recalculate totals after dynamic overrides
    section_totals['C'] = sum(e.amount for e in sections['C'])
    section_totals['D'] = sum(e.amount for e in sections['D'])

    adv_total = sum(e.amount for e in sections['A'] if e.is_paid)
    perf_summary = _get_perf_summary(mform, totals, sections)

    performance_pdf = render_performance_form_reportlab({
        'mform': mform, 'perf_form': perf_form, 'records': records, 'totals': totals,
        'sections': sections, 'section_totals': section_totals, 'perf_summary': perf_summary,
        'base_dir': settings.BASE_DIR,
    })
    
    # 3. Merge
    merged_pdf = merge_pdf_bytes([accounting_pdf, performance_pdf])
    
    from django.utils.text import slugify
    filename = slugify(f"full_report_{mform.group.name}_{mform.get_month_name()}_{mform.year}") + ".pdf"
    inline = request.GET.get('inline') == '1'
    return generate_pdf_response(None, {}, filename, inline=inline, pdf_content=merged_pdf)

from finance.models import Expense
from finance.forms import ExpenseForm
import datetime

from django.db import models

@login_required
def expense_list(request):
    today = datetime.date.today()
    selected_month = int(request.GET.get('month', today.month))
    selected_year = int(request.GET.get('year', today.year))

    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.created_by = request.user
            expense.save()
            messages.success(request, 'Expense recorded successfully.')
            return redirect(f"{request.path}?month={selected_month}&year={selected_year}")
    else:
        form = ExpenseForm()

    expenses = Expense.objects.filter(date__month=selected_month, date__year=selected_year)
    total_amount = sum(exp.amount for exp in expenses)
    existing_names = Expense.objects.values_list('name', flat=True).distinct()

    # Calculate "TOTALS ENTITIES" from Performance Entries
    from finance.models import PerformanceEntry
    entities_income = PerformanceEntry.objects.filter(
        performance_form__monthly_form__month=selected_month,
        performance_form__monthly_form__year=selected_year
    ).filter(
        models.Q(section='D', description__in=['Service Fee', 'Loan Forms', 'Mpesa Charges']) |
        models.Q(section='C', description='Pass Book')
    ).aggregate(total=models.Sum('amount'))['total'] or 0

    profit = entities_income - total_amount

    months = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]
    available_years = list(range(today.year - 5, today.year + 2))

    context = {
        'expenses': expenses,
        'form': form,
        'total_amount': total_amount,
        'existing_names': existing_names,
        'entities_income': entities_income,
        'profit': profit,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'months': months,
        'available_years': available_years,
    }
    return render(request, 'finance/expense_list.html', context)

@login_required
@require_POST
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    expense.delete()
    messages.success(request, 'Expense deleted successfully.')
    return redirect(request.META.get('HTTP_REFERER', 'expense_list'))
