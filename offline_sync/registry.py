from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from accounts.models import User
from finance.models import Expense, MonthlyForm, MemberRecord
from groups.models import Group
from members.models import Member


@dataclass(frozen=True)
class SyncModelSpec:
    model: Any
    order: int
    serialize: Callable[[Any], dict[str, Any]]
    apply_payload: Callable[[dict[str, Any], Any], dict[str, Any]]


_registry: dict[str, SyncModelSpec] = {}
_initialized = False


def _parse_client_updated_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        parsed = datetime.fromtimestamp(float(value), tz=dt_timezone.utc)
    else:
        parsed = parse_datetime(str(value or '').strip())

    if parsed is None:
        return timezone.now()

    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())

    return parsed


def _parse_required_date(value: Any, field_name: str):
    parsed = parse_date(str(value or '').strip())
    if parsed is None:
        raise ValueError(f'{field_name} is required and must be YYYY-MM-DD.')
    return parsed


def _parse_decimal(value: Any, field_name: str) -> Decimal:
    try:
        return Decimal(str(value if value is not None else '0'))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f'{field_name} is invalid.')


def _parse_required_int(value: Any, field_name: str) -> int:
    try:
        result = int(str(value or '').strip())
        if result <= 0:
            raise ValueError()
        return result
    except (TypeError, ValueError):
        raise ValueError(f'{field_name} is required and must be a positive integer.')


def _parse_int(value: Any, field_name: str, default: int = 0) -> int:
    try:
        if value is None or str(value).strip() == '':
            return default
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _resolve_group(group_client_uuid: str) -> Group:
    if not group_client_uuid:
        raise ValueError('group_client_uuid is required.')
    return Group.objects.get(client_uuid=group_client_uuid)


def _serialize_group(group: Group) -> dict[str, Any]:
    return {
        'server_id': group.pk,
        'client_uuid': str(group.client_uuid),
        'client_updated_at': group.client_updated_at.isoformat(),
        'updated_at': group.updated_at.isoformat(),
        'name': group.name,
        'location': group.location,
        'date_created': group.date_created.isoformat(),
        'officer_name': group.officer_name,
        'banking_type': group.banking_type,
    }


def _apply_group(payload: dict[str, Any], request) -> dict[str, Any]:
    name = str(payload.get('name', '')).strip()
    location = str(payload.get('location', '')).strip()
    officer_name = str(payload.get('officer_name', '')).strip()
    if not name or not location or not officer_name:
        raise ValueError('name, location, and officer_name are required.')

    banking_choices = {choice[0] for choice in Group.BANKING_CHOICES}
    banking_type = str(payload.get('banking_type') or 'office').strip()
    if banking_type not in banking_choices:
        banking_type = 'office'

    return {
        'name': name,
        'location': location,
        'date_created': _parse_required_date(payload.get('date_created'), 'date_created'),
        'officer_name': officer_name,
        'banking_type': banking_type,
        'client_updated_at': _parse_client_updated_at(payload.get('client_updated_at')),
    }


def _serialize_member(member: Member) -> dict[str, Any]:
    return {
        'server_id': member.pk,
        'client_uuid': str(member.client_uuid),
        'client_updated_at': member.client_updated_at.isoformat(),
        'updated_at': member.updated_at.isoformat(),
        'group_client_uuid': str(member.group.client_uuid),
        'member_number': member.member_number,
        'name': member.name,
        'phone': member.phone,
        'join_date': member.join_date.isoformat(),
        'is_active': member.is_active,
    }


def _apply_member(payload: dict[str, Any], request) -> dict[str, Any]:
    group = _resolve_group(str(payload.get('group_client_uuid', '')).strip())
    name = str(payload.get('name', '')).strip()
    if not name:
        raise ValueError('name is required.')

    member_number_raw = payload.get('member_number')
    if member_number_raw in (None, ''):
        member_number = None
    else:
        try:
            member_number = int(member_number_raw)
        except (TypeError, ValueError):
            raise ValueError('member_number is invalid.')

    client_uuid = str(payload.get('client_uuid', '')).strip()
    if member_number is not None:
        duplicate_qs = Member.objects.filter(group=group, member_number=member_number)
        if client_uuid:
            duplicate_qs = duplicate_qs.exclude(client_uuid=client_uuid)
        if duplicate_qs.exists():
            raise ValueError(
                f'member_number {member_number} already exists in this group. '
                'Use a different member number.'
            )

    return {
        'group': group,
        'member_number': member_number,
        'name': name,
        'phone': str(payload.get('phone', '')).strip(),
        'join_date': _parse_required_date(payload.get('join_date'), 'join_date'),
        'is_active': _to_bool(payload.get('is_active', True)),
        'client_updated_at': _parse_client_updated_at(payload.get('client_updated_at')),
    }


def _serialize_monthly_form(monthly_form: MonthlyForm) -> dict[str, Any]:
    return {
        'server_id': monthly_form.pk,
        'client_uuid': str(monthly_form.client_uuid),
        'client_updated_at': monthly_form.client_updated_at.isoformat(),
        'updated_at': monthly_form.updated_at.isoformat(),
        'group_client_uuid': str(monthly_form.group.client_uuid),
        'month': monthly_form.month,
        'year': monthly_form.year,
        'status': monthly_form.status,
        'notes': monthly_form.notes,
    }


def _apply_monthly_form(payload: dict[str, Any], request) -> dict[str, Any]:
    group = _resolve_group(str(payload.get('group_client_uuid', '')).strip())

    month_raw = payload.get('month')
    year_raw = payload.get('year')
    if month_raw is None or year_raw is None:
        raise ValueError('month and year are required and must be numeric.')

    if str(month_raw).strip() == '' or str(year_raw).strip() == '':
        raise ValueError('month and year are required and must be numeric.')

    try:
        month = int(str(month_raw))
        year = int(str(year_raw))
    except (TypeError, ValueError):
        raise ValueError('month and year are required and must be numeric.')

    if month < 1 or month > 12:
        raise ValueError('month must be between 1 and 12.')

    status_choices = {choice[0] for choice in MonthlyForm.STATUS_CHOICES}
    status = str(payload.get('status') or 'draft').strip()
    if status not in status_choices:
        status = 'draft'

    defaults = {
        'group': group,
        'month': month,
        'year': year,
        'status': status,
        'notes': str(payload.get('notes', '')).strip(),
        'client_updated_at': _parse_client_updated_at(payload.get('client_updated_at')),
    }

    if request.user.is_authenticated:
        defaults['created_by'] = request.user

    return defaults


def _serialize_expense(expense: Expense) -> dict[str, Any]:
    return {
        'server_id': expense.pk,
        'client_uuid': str(expense.client_uuid),
        'client_updated_at': expense.client_updated_at.isoformat(),
        'updated_at': expense.updated_at.isoformat(),
        'date': expense.date.isoformat(),
        'name': expense.name,
        'amount': str(expense.amount),
        'notes': expense.notes,
    }


def _apply_expense(payload: dict[str, Any], request) -> dict[str, Any]:
    name = str(payload.get('name', '')).strip()
    if not name:
        raise ValueError('name is required.')

    defaults = {
        'date': _parse_required_date(payload.get('date'), 'date'),
        'name': name,
        'amount': _parse_decimal(payload.get('amount'), 'amount'),
        'notes': str(payload.get('notes', '')).strip(),
        'client_updated_at': _parse_client_updated_at(payload.get('client_updated_at')),
    }

    if request.user.is_authenticated:
        defaults['created_by'] = request.user

    return defaults


def _serialize_user(user: User) -> dict[str, Any]:
    return {
        'server_id': user.pk,
        'client_uuid': str(user.client_uuid),
        'client_updated_at': user.client_updated_at.isoformat(),
        'updated_at': user.updated_at.isoformat(),
        'phone_number': user.phone_number,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'role': user.role,
        'is_active': user.is_active,
    }


def _serialize_member_record(member_record: MemberRecord) -> dict[str, Any]:
    return {
        'server_id': member_record.pk,
        'monthly_form_id': member_record.monthly_form.pk,
        'member_id': member_record.member.pk,
        'order': member_record.order,
        'savings_share_bf': str(member_record.savings_share_bf),
        'loan_balance_bf': str(member_record.loan_balance_bf),
        'total_repaid': str(member_record.total_repaid),
        'principal': str(member_record.principal),
        'loan_interest': str(member_record.loan_interest),
        'shares_this_month': str(member_record.shares_this_month),
        'withdrawals': str(member_record.withdrawals),
        'fines_charges': str(member_record.fines_charges),
        'savings_share_cf': str(member_record.savings_share_cf),
        'loan_balance_cf': str(member_record.loan_balance_cf),
        'savings_valid': member_record.savings_valid,
        'loan_valid': member_record.loan_valid,
    }


def _apply_member_record(payload: dict[str, Any], request) -> dict[str, Any]:
    monthly_form_id = _parse_required_int(payload.get('monthly_form_id'), 'monthly_form_id')
    member_id = _parse_required_int(payload.get('member_id'), 'member_id')

    return {
        'monthly_form_id': monthly_form_id,
        'member_id': member_id,
        'order': _parse_int(payload.get('order'), 'order', 0),
        'savings_share_bf': _parse_decimal(payload.get('savings_share_bf'), 'savings_share_bf'),
        'loan_balance_bf': _parse_decimal(payload.get('loan_balance_bf'), 'loan_balance_bf'),
        'total_repaid': _parse_decimal(payload.get('total_repaid'), 'total_repaid'),
        'principal': _parse_decimal(payload.get('principal'), 'principal'),
        'loan_interest': _parse_decimal(payload.get('loan_interest'), 'loan_interest'),
        'shares_this_month': _parse_decimal(payload.get('shares_this_month'), 'shares_this_month'),
        'withdrawals': _parse_decimal(payload.get('withdrawals'), 'withdrawals'),
        'fines_charges': _parse_decimal(payload.get('fines_charges'), 'fines_charges'),
        'savings_share_cf': _parse_decimal(payload.get('savings_share_cf'), 'savings_share_cf'),
        'loan_balance_cf': _parse_decimal(payload.get('loan_balance_cf'), 'loan_balance_cf'),
        'savings_valid': bool(payload.get('savings_valid', True)),
        'loan_valid': bool(payload.get('loan_valid', True)),
    }


def _apply_user(payload: dict[str, Any], request) -> dict[str, Any]:
    if not request.user.is_authenticated or not (
        request.user.is_superuser or request.user.role in ('admin', 'ict')
    ):
        raise ValueError('Only administrators can sync users.')

    phone_number = str(payload.get('phone_number', '')).strip()
    username = str(payload.get('username', '')).strip()
    if not phone_number or not username:
        raise ValueError('phone_number and username are required.')

    role_choices = {choice[0] for choice in User.ROLE_CHOICES}
    role = str(payload.get('role') or 'officer').strip()
    if role not in role_choices:
        role = 'officer'

    defaults = {
        'phone_number': phone_number,
        'username': username,
        'first_name': str(payload.get('first_name', '')).strip(),
        'last_name': str(payload.get('last_name', '')).strip(),
        'email': str(payload.get('email', '')).strip(),
        'role': role,
        'is_active': _to_bool(payload.get('is_active', True)),
        'client_updated_at': _parse_client_updated_at(payload.get('client_updated_at')),
    }

    password = str(payload.get('password', '')).strip()
    if password:
        defaults['password'] = password

    return defaults


def register_models() -> None:
    global _initialized

    if _initialized:
        return

    _registry.update(
        {
            'group': SyncModelSpec(
                model=Group,
                order=1,
                serialize=_serialize_group,
                apply_payload=_apply_group,
            ),
            'member': SyncModelSpec(
                model=Member,
                order=2,
                serialize=_serialize_member,
                apply_payload=_apply_member,
            ),
            'monthly_form': SyncModelSpec(
                model=MonthlyForm,
                order=3,
                serialize=_serialize_monthly_form,
                apply_payload=_apply_monthly_form,
            ),
            'member_record': SyncModelSpec(
                model=MemberRecord,
                order=4,
                serialize=_serialize_member_record,
                apply_payload=_apply_member_record,
            ),
            'expense': SyncModelSpec(
                model=Expense,
                order=5,
                serialize=_serialize_expense,
                apply_payload=_apply_expense,
            ),
            'user': SyncModelSpec(
                model=User,
                order=6,
                serialize=_serialize_user,
                apply_payload=_apply_user,
            ),
        }
    )
    _initialized = True


def get_sync_spec(model_name: str) -> SyncModelSpec | None:
    return _registry.get(model_name)


def get_ordered_model_names() -> list[str]:
    return [name for name, _ in sorted(_registry.items(), key=lambda item: item[1].order)]
