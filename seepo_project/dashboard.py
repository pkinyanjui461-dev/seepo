import calendar
import re
from datetime import date

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.urls import reverse
from django.utils import timezone


MONTH_FIELD_MAP = [
    ('january', 1),
    ('february', 2),
    ('march', 3),
    ('april', 4),
    ('may', 5),
    ('june', 6),
    ('july', 7),
    ('august', 8),
    ('september', 9),
    ('october', 10),
    ('november', 11),
    ('december', 12),
]

DAY_PATTERN = re.compile(r'(\d{1,2})')


def _extract_day_of_month(value):
    if value is None:
        return None

    text = str(value).strip()
    if not text or text in {'-', '--'}:
        return None

    match = DAY_PATTERN.search(text)
    if not match:
        return None

    day = int(match.group(1))
    if day < 1 or day > 31:
        return None
    return day


def _build_meeting_sections(today):
    from groups.models import DiaryEntry

    buckets = {
        'upcoming': [],
        'ongoing': [],
        'success': [],
        'past': [],
    }

    diaries = DiaryEntry.objects.select_related('group').all()
    for diary in diaries:
        for month_field, month_number in MONTH_FIELD_MAP:
            raw_day_value = getattr(diary, month_field, None)
            day = _extract_day_of_month(raw_day_value)
            if not day:
                continue

            days_in_month = calendar.monthrange(today.year, month_number)[1]
            if day > days_in_month:
                continue

            meeting_date = date(today.year, month_number, day)
            delta_days = (meeting_date - today).days
            venue = str((diary.venue or '').strip())
            group_location = str((diary.group.location or '').strip())
            payload = {
                'group_id': diary.group.pk,
                'group_name': diary.group.name,
                'group_location': group_location,
                'venue': venue or group_location,
                'meeting_time': str((diary.time or '').strip()),
                'weekday': meeting_date.strftime('%A'),
                'month_name': calendar.month_name[month_number],
                'raw_day_value': str(raw_day_value or '').strip(),
                'group_url': reverse('group_detail', args=[diary.group.pk]),
                'meeting_date': meeting_date,
                'display_date': meeting_date.strftime('%d %b %Y'),
            }

            if 1 <= delta_days <= 7:
                buckets['upcoming'].append(payload)
            elif delta_days == 0:
                buckets['ongoing'].append(payload)
            elif -7 <= delta_days < 0:
                buckets['success'].append(payload)
            elif delta_days < -7:
                buckets['past'].append(payload)

    buckets['upcoming'].sort(key=lambda item: (item['meeting_date'], item['group_name'].lower()))
    buckets['ongoing'].sort(key=lambda item: item['group_name'].lower())
    buckets['success'].sort(key=lambda item: (item['meeting_date'], item['group_name'].lower()), reverse=True)
    buckets['past'].sort(key=lambda item: (item['meeting_date'], item['group_name'].lower()), reverse=True)

    section_meta = [
        {
            'slug': 'upcoming',
            'title': 'Upcoming (7 Days)',
            'status_label': 'Upcoming',
            'empty_label': 'No meetings in the next 7 days.',
        },
        {
            'slug': 'ongoing',
            'title': 'Ongoing (Today)',
            'status_label': 'Ongoing',
            'empty_label': 'No meetings happening today.',
        },
        {
            'slug': 'success',
            'title': 'Success (Last 7 Days)',
            'status_label': 'Success',
            'empty_label': 'No completed meetings in the last 7 days.',
        },
        {
            'slug': 'past',
            'title': 'Past Meetings',
            'status_label': 'Past',
            'empty_label': 'No older past meetings.',
        },
    ]

    sections = []
    for meta in section_meta:
        items = buckets[meta['slug']]
        sections.append(
            {
                **meta,
                'count': len(items),
                'items': items[:6],
            }
        )

    return sections


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

    meeting_sections = _build_meeting_sections(timezone.localdate())

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
        'meeting_sections': meeting_sections,
    })
