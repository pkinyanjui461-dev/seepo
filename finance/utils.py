import io
from django.template.loader import render_to_string
from django.http import HttpResponse
from xhtml2pdf import pisa
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
import pypdf
from decimal import Decimal

def ensure_performance_form_initialized(perf_form):
    """
    Ensures that a GroupPerformanceForm has its required entries (A, B, E)
    initialized with carry-over values from the previous month.
    """
    from django.db.models import Q
    from finance.models import MonthlyForm, PerformanceEntry
    
    mform = perf_form.monthly_form
    
    # 1. Find previous month's form (handling year transitions and gaps)
    prev_mform = MonthlyForm.objects.filter(
        group=perf_form.monthly_form.group
    ).filter(
        Q(year__lt=perf_form.monthly_form.year) | 
        Q(year=perf_form.monthly_form.year, month__lt=perf_form.monthly_form.month)
    ).order_by('-year', '-month').first()

    banking_bf = Decimal('0')
    debt_bf = Decimal('0')
    carry_over_balances = {}

    if prev_mform and hasattr(prev_mform, 'performance_form'):
        prev_perf = prev_mform.performance_form
        # 1. Collect unpaid advances from Section A
        for entry in prev_perf.entries.filter(section='A', is_paid=False):
            increase = entry.amount
            carry_over_balances[entry.description] = carry_over_balances.get(entry.description, Decimal('0')) + increase
        
        # 2. Collect advances given in Section B (tertiary_amount)
        for entry in prev_perf.entries.filter(section='B'):
            if entry.tertiary_amount > 0:
                increase = (entry.tertiary_amount * Decimal('1.1')).quantize(Decimal('1'), rounding='ROUND_HALF_UP')
                carry_over_balances[entry.description] = carry_over_balances.get(entry.description, Decimal('0')) + increase

        # 3. Collect Section E Banking and Debt C/F (Source for new month)
        b_cf_entry = prev_perf.entries.filter(section='E', description='Total Banking').first()
        if b_cf_entry: banking_bf = b_cf_entry.amount
        d_cf_entry = prev_perf.entries.filter(section='E', description='Total Debt').first()
        if d_cf_entry: debt_bf = d_cf_entry.amount

    # 2. Initialize A & B if empty
    has_a_b = perf_form.entries.filter(section__in=['A', 'B']).exists()
    if not has_a_b:
        members_recs = mform.member_records.select_related('member').annotate(
            member_number_missing=Case(
                When(member__member_number__isnull=True, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        ).order_by('member_number_missing', 'member__member_number', 'member__name', 'pk')
        for i, mrec in enumerate(members_recs):
            # NEW: Use member number as the primary identifier in description for A and B
            member_num = str(mrec.member.member_number)
            name = mrec.member.name

            # Try to get carry over by number first, then by name
            amount = carry_over_balances.get(member_num)
            if amount is None:
                amount = carry_over_balances.get(name, Decimal('0'))

            PerformanceEntry.objects.create(
                performance_form=perf_form, section='A', description=member_num, amount=amount, is_paid=False, order=i
            )
            PerformanceEntry.objects.create(
                performance_form=perf_form, section='B', description=member_num, amount=0, secondary_amount=0, tertiary_amount=0, order=i
            )

    # 3. Initialize C if missing
    has_c = perf_form.entries.filter(section='C').exists()
    if not has_c:
        c_labels = ['Previous Banking', 'Total Repaid', 'Advance Paid', 'Project', 'Meals/Hall', 'Pass Book', 'Fines', 'Risk Fund', 'Bank Withdrawal', 'Debt Out']
        for i, label in enumerate(c_labels):
            amt = banking_bf if label == 'Previous Banking' else Decimal('0')
            PerformanceEntry.objects.create(
                performance_form=perf_form, section='C', description=label, amount=amt, order=i
            )

    # 4. Initialize D if missing
    has_d = perf_form.entries.filter(section='D').exists()
    if not has_d:
        d_labels = ['Withdrawals', 'Loans Given', 'Advance Given', 'Principal Paid', 'Service Fee', 'Pass Book', 'Meals/Hall', 'Loan Forms', 'Interest', 'Risk Fund', 'Mpesa Charges', 'Bank Charges', 'Banking Today', 'Registration']
        for i, label in enumerate(d_labels):
            PerformanceEntry.objects.create(
                performance_form=perf_form, section='D', description=label, amount=Decimal('0'), order=i
            )

    # 5. Initialize E if missing OR if it was saved with old labels/incomplete
    has_e = perf_form.entries.filter(section='E').count() >= 3
    if not has_e:
        perf_form.entries.filter(section='E').delete()
        e_labels = ["Debt B/F", "Total Banking", "Total Debt"]
        for i, label in enumerate(e_labels):
            amt = Decimal('0')
            if label == "Debt B/F": amt = debt_bf
            elif label == "Total Banking": amt = banking_bf
            PerformanceEntry.objects.create(
                performance_form=perf_form, section='E', description=label, amount=amt, order=i
            )

    # Return the balances as requested by the view
    final_banking_bf = Decimal('0')
    final_debt_bf = Decimal('0')
    b_entry = perf_form.entries.filter(section='C', description='Previous Banking').first()
    if b_entry: final_banking_bf = b_entry.amount
    d_entry = perf_form.entries.filter(section='E', description='Debt B/F').first()
    if d_entry: final_debt_bf = d_entry.amount

    return final_banking_bf, final_debt_bf

def merge_pdf_bytes(pdf_list):
    """
    Merges multiple PDF byte strings into one.
    """
    merger = pypdf.PdfWriter()
    for pdf_data in pdf_list:
        if pdf_data:
            merger.append(io.BytesIO(pdf_data))

    output = io.BytesIO()
    merger.write(output)
    return output.getvalue()

def render_to_pdf(template_src, context_dict={}):
    """
    Renders a template into a PDF using xhtml2pdf (pisa).
    """
    html_string = render_to_string(template_src, context_dict)
    result = io.BytesIO()
    pisa_result = pisa.pisaDocument(io.BytesIO(html_string.encode("UTF-8")), result)
    if not getattr(pisa_result, 'err', 0):
        return result.getvalue()
    return None

def render_to_pdf_weasy(template_src, context_dict={}):
    """
    Renders a template into a PDF using WeasyPrint.
    """
    try:
        weasyprint_module = importlib.import_module('weasyprint')
        html_class = getattr(weasyprint_module, 'HTML', None)
        if html_class is None:
            return None
        html_string = render_to_string(template_src, context_dict)
        return html_class(string=html_string).write_pdf()
    except Exception:
        return None

def render_performance_form_reportlab(context_dict):
    """
    Renders the Performance Form PDF using ReportLab for pixel-perfect layout.
    """
    buffer = io.BytesIO()
    # Aggressive margins to fit everything
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=4*mm, leftMargin=4*mm, topMargin=4*mm, bottomMargin=4*mm)
    elements = []
    styles = getSampleStyleSheet()

    # Professional Colors
    HEADER_BG = colors.HexColor("#2C3E50") # Dark Slate
    TEXT_WHITE = colors.white
    BORDER_COLOR = colors.HexColor("#34495E")

    # Custom styles
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, alignment=1, spaceAfter=8*mm, textColor=HEADER_BG, fontName='Helvetica-Bold')
    label_style = ParagraphStyle('LabelStyle', fontSize=7, leading=8)

    # 1. Title Only
    elements.append(Paragraph("GROUPS MONTHLY PERFORMANCE", title_style))

    mform = context_dict.get('mform')
    perf_form = context_dict.get('perf_form')
    sections = context_dict.get('sections', {})
    section_totals = context_dict.get('section_totals', {})
    perf_summary = context_dict.get('perf_summary', {})

    # Table Grid Styles
    common_style = [
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,0), (-1,-1), 7),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ]

    # Section A + Fines (Unified) - Matching Web exactly
    a_entries = sections.get('A', [])
    # M.NO | B/F | PAID | FINE
    a_data = [['SECTION A (ADVANCES) & FINES', '', '', ''], ['M.NO', 'B/F', 'PAID', 'FINE']]
    for e in a_entries:
        a_data.append([
            e.description,
            f"{e.amount:.0f}" if e.amount else "",
            f"{e.secondary_amount:.0f}" if hasattr(e, 'secondary_amount') and e.secondary_amount else "",
            f"{e.tertiary_amount:.0f}" if hasattr(e, 'tertiary_amount') and e.tertiary_amount else ""
        ])
    while len(a_data) < 12: a_data.append(["", "", "", ""])
    a_data.append(['TOTAL', f"{section_totals.get('A_bf', 0):.0f}", f"{section_totals.get('A_paid', 0):.0f}", f"{section_totals.get('A_fines', 0):.0f}"])
    a_data.append(['TOTAL PAID TODAY:', '', ''])
    a_data.append(['PAID THROUGH SAVINGS:', '', ''])

    # Section B (Sequential)
    # M.NO | WITHDRAWAL | LOANS | ADVANCE
    b_entries = sections.get('B', [])
    b_data = [['SECTION B (CASH OUT)', '', '', ''], ['M.NO', 'WITHDRAWAL', 'LOANS', 'ADVANCE']]
    for e in b_entries:
        b_data.append([
            e.description,
            f"{e.amount:.0f}" if e.amount else "",
            f"{e.secondary_amount:.0f}" if hasattr(e, 'secondary_amount') and e.secondary_amount else "",
            f"{e.tertiary_amount:.0f}" if hasattr(e, 'tertiary_amount') and e.tertiary_amount else ""
        ])
    while len(b_data) < 12: b_data.append(["", "", "", ""])
    b_data.append(['TOTAL', f"{section_totals.get('B_with', 0):.0f}", f"{section_totals.get('B_loan', 0):.0f}", f"{section_totals.get('B_adv', 0):.0f}"])

    # Table Creation & Styling
    a_table = Table(a_data, colWidths=[35*mm, 15*mm, 15*mm, 15*mm], rowHeights=[5*mm]*2 + [4*mm]*(len(a_data)-5) + [5*mm]*3)
    a_table.setStyle(TableStyle(common_style + [
        ('BACKGROUND', (0,0), (-1,1), HEADER_BG), ('TEXTCOLOR', (0,0), (-1,1), TEXT_WHITE),
        ('SPAN', (0,0), (3,0)), ('SPAN', (0,-2), (2,-2)), ('SPAN', (0,-1), (2,-1)),
        ('ALIGN', (0,2), (0,-4), 'LEFT'), ('FONTSIZE', (0,2), (0,-4), 7),
        ('FONTNAME', (0,-3), (0,-1), 'Helvetica-Bold'), ('ALIGN', (0,-2), (0,-1), 'RIGHT')
    ]))

    b_table = Table(b_data, colWidths=[35*mm, 18*mm, 18*mm, 18*mm], rowHeights=[5*mm]*2 + [4*mm]*(len(b_data)-3) + [5*mm])
    b_table.setStyle(TableStyle(common_style + [
        ('BACKGROUND', (0,0), (-1,1), HEADER_BG), ('TEXTCOLOR', (0,0), (-1,1), TEXT_WHITE),
        ('SPAN', (0,0), (3,0)), ('ALIGN', (0,2), (0,-2), 'LEFT'), ('FONTSIZE', (0,2), (0,-2), 7)
    ]))

    elements.append(Table([[a_table, b_table]], colWidths=[85*mm, 95*mm], style=[('VALIGN', (0,0), (-1,-1), 'TOP')]))
    elements.append(Spacer(1, 4*mm))

    # 4. Sections C, D, E (Professional Design)
    # Section C: Income - Matching Web Labels Exactly
    c_labels = [
        'Previous Banking', 'Total Repaid', 'Advance Paid', 'Project', 'Meals/Hall',
        'Pass Book', 'Fines', 'Risk Fund', 'Bank Withdrawal', 'Debt Out'
    ]
    c_data = [['SECTION C (INCOME)', '', ''], ['NO', 'DETAILS', 'AMOUNT (KSHS)']]
    for i, label in enumerate(c_labels):
        amt = next((e.amount for e in sections.get('C', []) if e.description.upper() == label.upper()), 0)
        c_data.append([str(i+1), label, f"{amt:.0f}" if amt else ""])
    c_data.append(['', 'TOTAL C:', f"{section_totals.get('C', 0):.0f}"])

    # Section D: Expenses - Matching Web Labels Exactly
    d_labels = [
        'Withdrawals', 'Loans Given', 'Advance Given', 'Principal Paid', 'Service Fee', 'Pass Book',
        'Meals/Hall', 'Loan Forms', 'Interest', 'Risk Fund', 'Mpesa Charges',
        'Bank Charges', 'Banking Today', 'Registration'
    ]
    d_data = [['SECTION D (EXPENSES)', '', ''], ['NO', 'DETAILS', 'AMOUNT (KSHS)']]
    for i, label in enumerate(d_labels):
        amt = next((e.amount for e in sections.get('D', []) if e.description.upper() == label.upper()), 0)
        d_data.append([str(i+1), label, f"{amt:.0f}" if amt else ""])
    d_data.append(['', 'TOTAL D:', f"{section_totals.get('D', 0):.0f}"])

    # Section E: Reconciliation (Automation-inspired UI)
    e_entries = sections.get('E', [])
    e_data: list[list[Any]] = [['SECTION E (RECONCILIATION)']]
    for e in e_entries:
        amt_str = f"{e.amount:.0f}" if e and e.amount else " "
        e_data.append([Paragraph(f"<b>{e.description.upper()}: </b><div align='right'>{amt_str}</div>", label_style)])
    while len(e_data) < 7: e_data.append([Paragraph(" ", label_style)])

    c_table = Table(c_data, colWidths=[8*mm, 35*mm, 18*mm], rowHeights=[5*mm]*len(c_data))
    c_table.setStyle(TableStyle(common_style + [
        ('BACKGROUND', (0,0), (-1,1), HEADER_BG), ('TEXTCOLOR', (0,0), (-1,1), TEXT_WHITE),
        ('SPAN', (0,0), (2,0)), ('ALIGN', (1,2), (1,-2), 'LEFT'), ('FONTNAME', (1,-1), (1,-1), 'Helvetica-Bold')
    ]))

    d_table = Table(d_data, colWidths=[8*mm, 35*mm, 18*mm], rowHeights=[5*mm]*len(d_data))
    d_table.setStyle(TableStyle(common_style + [
        ('BACKGROUND', (0,0), (-1,1), HEADER_BG), ('TEXTCOLOR', (0,0), (-1,1), TEXT_WHITE),
        ('SPAN', (0,0), (2,0)), ('ALIGN', (1,2), (1,-2), 'LEFT'), ('FONTNAME', (1,-1), (1,-1), 'Helvetica-Bold')
    ]))

    e_table = Table(e_data, colWidths=[65*mm], rowHeights=[5*mm]*len(e_data))
    e_table.setStyle(TableStyle(common_style + [
        ('BACKGROUND', (0,0), (0,0), HEADER_BG), ('TEXTCOLOR', (0,0), (0,0), TEXT_WHITE),
        ('ALIGN', (0,1), (-1,-1), 'LEFT'), ('VALIGN', (0,1), (-1,-1), 'MIDDLE')
    ]))

    elements.append(Table([[c_table, d_table, e_table]], colWidths=[65*mm, 65*mm, 65*mm], style=[('VALIGN', (0,0), (-1,-1), 'TOP')]))
    elements.append(Spacer(1, 4*mm))

    # 5. Footer (Final Layout)
    meeting_data = [['NEXT MEETING DETAILS', ''], ['DATE', perf_form.next_meeting_date.strftime('%d/%m/%Y') if perf_form and perf_form.next_meeting_date else ''], ['TIME', perf_form.next_meeting_time.strftime('%H:%M') if perf_form and perf_form.next_meeting_time else ''], ['VENUE', perf_form.next_meeting_venue if perf_form and perf_form.next_meeting_venue else ''], ['STAGE/AREA', '']]
    meeting_table = Table(meeting_data, colWidths=[40*mm, 50*mm], rowHeights=[5*mm]*5)
    meeting_table.setStyle(TableStyle(common_style + [('BACKGROUND', (0,0), (-1,0), HEADER_BG), ('TEXTCOLOR', (0,0), (-1,0), TEXT_WHITE), ('SPAN', (0,0), (1,0)), ('ALIGN', (0,1), (0,-1), 'LEFT')]))

    elements.append(Table([[meeting_table, ""]], colWidths=[95*mm, 85*mm], style=[('VALIGN', (0,0), (-1,-1), 'TOP'), ('ALIGN', (0,0), (-1,-1), 'LEFT')]))
    elements.append(Spacer(1, 4*mm))

    # 6. Absolute Bottom Note
    elements.append(Table([['NOTE', perf_form.notes if perf_form and perf_form.notes else '']], colWidths=[20*mm, 175*mm], rowHeights=[10*mm], style=common_style + [('BACKGROUND', (0,0), (0,0), HEADER_BG), ('TEXTCOLOR', (0,0), (0,0), TEXT_WHITE), ('ALIGN', (1,0), (1,0), 'LEFT')]))

    doc.build(elements)
    pdf_value = buffer.getvalue()
    buffer.close()
    return pdf_value

def generate_pdf_response(template_src, context_dict, filename, inline=False, use_weasy=False, use_reportlab=False, pdf_content=None):
    """
    Generates a Django HttpResponse with a PDF file.
    """
    if pdf_content:
        pdf = pdf_content
    elif use_reportlab:
        pdf = render_performance_form_reportlab(context_dict)
    elif use_weasy:
        pdf = render_to_pdf_weasy(template_src, context_dict)
    else:
        pdf = render_to_pdf(template_src, context_dict)

    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        disposition = 'inline' if inline else 'attachment'
        response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
        response['Content-Length'] = len(pdf)
        return response
    return HttpResponse("Error generating PDF", status=500)
