import json
import uuid
from decimal import Decimal, InvalidOperation

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime, parse_time
from accounts.forms import LoginForm
from accounts.models import User


def is_admin(user):
    return user.is_authenticated and user.role in ['admin', 'ict']


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        from accounts.models import Notification
        Notification.objects.create(
            user=user,
            title="Welcome back!",
            message=f"Hello {user.first_name or user.username}, welcome to the SEEPO Dashboard."
        )
        return redirect(request.GET.get('next', 'dashboard'))
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
@user_passes_test(is_admin)
def user_list(request):
    users = User.objects.all().order_by('role', 'username')
    return render(request, 'accounts/user_list.html', {'users': users})


@login_required
@user_passes_test(is_admin)
def user_create(request):
    from accounts.forms import UserCreationForm
    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        messages.success(request, f'User "{user.username}" created successfully.')
        return redirect('user_list')
    return render(request, 'accounts/user_form.html', {'form': form, 'title': 'Create User'})


@login_required
@user_passes_test(is_admin)
def user_edit(request, pk):
    from accounts.forms import UserEditForm
    user = get_object_or_404(User, pk=pk)
    form = UserEditForm(request.POST or None, instance=user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'User "{user.username}" updated.')
        return redirect('user_list')
    return render(request, 'accounts/user_form.html', {'form': form, 'title': 'Edit User', 'edit_user': user})


@login_required
@user_passes_test(is_admin)
def user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "You cannot delete yourself.")
        return redirect('user_list')

    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'User "{username}" deleted.')
        return redirect('user_list')
    return render(request, 'accounts/user_confirm_delete.html', {'user_to_delete': user})


@login_required
@user_passes_test(is_admin)
def user_password_reset(request, pk):
    from accounts.forms import PasswordResetForm
    user = get_object_or_404(User, pk=pk)
    form = PasswordResetForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user.set_password(form.cleaned_data['new_password'])
        user.save()
        messages.success(request, f'Password for "{user.username}" has been reset.')
        return redirect('user_list')
    return render(request, 'accounts/password_reset_form.html', {'form': form, 'edit_user': user})


@login_required
def profile_view(request):
    from accounts.forms import ProfileUpdateForm
    form = ProfileUpdateForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('profile')
    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def settings_view(request):
    return render(request, 'accounts/settings.html')


@login_required
def search_view(request):
    query = request.GET.get('q', '')
    if query:
        from groups.models import Group
        from members.models import Member
        groups = Group.objects.filter(name__icontains=query)
        members = Member.objects.filter(name__icontains=query)
    else:
        groups = []
        members = []
    return render(request, 'accounts/search_results.html', {
        'groups': groups, 'members': members, 'query': query
    })


@login_required
def notification_list(request):
    from accounts.models import Notification

    if request.method == 'POST' and request.POST.get('action') == 'mark_all_read':
        updated = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        messages.success(request, f'Marked {updated} notification(s) as read.')
        return redirect('notification_list')

    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(
        request,
        'accounts/notification_list.html',
        {
            'notifications': notifications,
            'unread_total': notifications.filter(is_read=False).count(),
        },
    )


@login_required
def mark_notification_read(request, pk):
    from accounts.models import Notification
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()
    if notification.url:
        return redirect(notification.url)
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


DATA_ADMIN_ALLOWED_APPS = {'accounts', 'groups', 'members', 'finance', 'reports', 'offline_sync'}
DATA_ADMIN_GLOBAL_EXCLUDED_FIELDS = {'id'}
DATA_ADMIN_MODEL_FIELD_EXCLUDES = {
    ('accounts', 'user'): {'password', 'last_login', 'groups', 'user_permissions'},
}


def _data_admin_field_input_type(field):
    if isinstance(field, (models.ForeignKey, models.OneToOneField)):
        return 'select'
    if field.choices:
        return 'select'
    if isinstance(field, models.BooleanField):
        return 'checkbox'
    if isinstance(field, models.TextField):
        return 'textarea'
    if isinstance(field, models.DateTimeField):
        return 'datetime-local'
    if isinstance(field, models.DateField):
        return 'date'
    if isinstance(field, models.TimeField):
        return 'time'
    if isinstance(field, (models.IntegerField, models.BigIntegerField, models.PositiveIntegerField, models.PositiveSmallIntegerField, models.SmallIntegerField)):
        return 'number'
    if isinstance(field, (models.DecimalField, models.FloatField)):
        return 'number'
    return 'text'


def _data_admin_related_options(field):
    related_model = field.remote_field.model
    queryset = related_model._default_manager.all()[:200]
    return [{'value': str(obj.pk), 'label': str(obj)} for obj in queryset]


def _data_admin_field_options(field):
    if isinstance(field, (models.ForeignKey, models.OneToOneField)):
        return _data_admin_related_options(field)
    if field.choices:
        return [
            {'value': str(value), 'label': str(label)}
            for value, label in field.flatchoices
            if value not in (None, '')
        ]
    return []


def _data_admin_field_step(field):
    if isinstance(field, models.DecimalField):
        if field.decimal_places <= 0:
            return '1'
        return '0.' + ('0' * (field.decimal_places - 1)) + '1'
    if isinstance(field, (models.IntegerField, models.BigIntegerField, models.PositiveIntegerField, models.PositiveSmallIntegerField, models.SmallIntegerField)):
        return '1'
    if isinstance(field, models.FloatField):
        return 'any'
    return None


def _data_admin_editable_fields(model):
    excluded = DATA_ADMIN_MODEL_FIELD_EXCLUDES.get((model._meta.app_label, model._meta.model_name), set())
    fields = []

    for field in model._meta.get_fields():
        if not isinstance(field, models.Field):
            continue
        if field.auto_created:
            continue
        if not field.editable:
            continue
        if isinstance(field, models.ManyToManyField):
            continue
        if field.name in DATA_ADMIN_GLOBAL_EXCLUDED_FIELDS or field.name in excluded:
            continue
        fields.append(field)

    return fields


def _data_admin_field_specs(model):
    specs = []
    for field in _data_admin_editable_fields(model):
        specs.append(
            {
                'name': field.name,
                'label': str(field.verbose_name).replace('_', ' ').upper(),
                'input_type': _data_admin_field_input_type(field),
                'required': not field.blank and not field.null,
                'options': _data_admin_field_options(field),
                'step': _data_admin_field_step(field),
                'field': field,
            }
        )
    return specs


def _data_admin_format_value(field, value):
    if value is None:
        return ''

    if isinstance(field, models.BooleanField):
        return bool(value)

    if isinstance(field, (models.ForeignKey, models.OneToOneField)):
        return str(value.pk)

    if isinstance(field, models.DateTimeField):
        dt_value = value
        if timezone.is_aware(dt_value):
            dt_value = timezone.localtime(dt_value)
        return dt_value.strftime('%Y-%m-%dT%H:%M')

    if isinstance(field, models.DateField):
        return value.strftime('%Y-%m-%d')

    if isinstance(field, models.TimeField):
        return value.strftime('%H:%M')

    if isinstance(field, models.JSONField):
        return json.dumps(value)

    return str(value)


def _data_admin_coerce_value(field, raw_value):
    if isinstance(field, models.BooleanField):
        return str(raw_value).lower() in {'1', 'true', 'yes', 'on'}

    text = '' if raw_value is None else str(raw_value).strip()

    if isinstance(field, (models.ForeignKey, models.OneToOneField)):
        if not text:
            if field.null:
                return None
            raise ValueError('This relation is required.')

        try:
            return field.remote_field.model._default_manager.get(pk=text)
        except field.remote_field.model.DoesNotExist as exc:
            raise ValueError('Related record does not exist.') from exc

    if not text:
        if field.null:
            return None
        if isinstance(field, (models.CharField, models.TextField)):
            return ''
        if field.has_default():
            return field.get_default()
        raise ValueError('This field is required.')

    if field.choices:
        valid = {str(choice[0]) for choice in field.flatchoices if choice[0] not in (None, '')}
        if text not in valid:
            raise ValueError('Invalid choice.')
        return text

    if isinstance(field, models.DateTimeField):
        parsed = parse_datetime(text)
        if parsed is None:
            try:
                from datetime import datetime

                parsed = datetime.fromisoformat(text)
            except ValueError as exc:
                raise ValueError('Invalid datetime value.') from exc

        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    if isinstance(field, models.DateField):
        parsed = parse_date(text)
        if parsed is None:
            raise ValueError('Invalid date value.')
        return parsed

    if isinstance(field, models.TimeField):
        parsed = parse_time(text)
        if parsed is None:
            raise ValueError('Invalid time value.')
        return parsed

    if isinstance(field, (models.IntegerField, models.BigIntegerField, models.PositiveIntegerField, models.PositiveSmallIntegerField, models.SmallIntegerField)):
        try:
            return int(text)
        except (TypeError, ValueError) as exc:
            raise ValueError('Invalid integer value.') from exc

    if isinstance(field, models.DecimalField):
        try:
            return Decimal(text)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError('Invalid decimal value.') from exc

    if isinstance(field, models.FloatField):
        try:
            return float(text)
        except (TypeError, ValueError) as exc:
            raise ValueError('Invalid number value.') from exc

    if isinstance(field, models.UUIDField):
        try:
            return uuid.UUID(text)
        except (ValueError, TypeError) as exc:
            raise ValueError('Invalid UUID value.') from exc

    if isinstance(field, models.JSONField):
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError('Invalid JSON value.') from exc

    return text


def _data_admin_validation_messages(exc):
    if hasattr(exc, 'message_dict'):
        messages_list = []
        for field_name, field_errors in exc.message_dict.items():
            label = field_name.replace('_', ' ').upper()
            for item in field_errors:
                messages_list.append(f'{label}: {item}')
        return messages_list

    if hasattr(exc, 'messages'):
        return [str(message) for message in exc.messages]

    return [str(exc)]


def _data_admin_apply_payload(instance, field_specs, payload):
    errors = []
    for spec in field_specs:
        field = spec['field']
        try:
            coerced = _data_admin_coerce_value(field, payload.get(spec['name']))
            setattr(instance, field.name, coerced)
        except ValueError as exc:
            errors.append(f'{spec["label"]}: {exc}')
    return errors


def _data_admin_model_specs():
    specs = []
    for model in apps.get_models():
        meta = model._meta
        if meta.app_label not in DATA_ADMIN_ALLOWED_APPS:
            continue
        if not meta.managed or meta.proxy:
            continue

        field_specs = _data_admin_field_specs(model)
        specs.append(
            {
                'slug': f'{meta.app_label}.{meta.model_name}',
                'model': model,
                'title': f'{meta.app_label.upper()} / {meta.verbose_name_plural.upper()}',
                'subtitle': f'{meta.verbose_name_plural.title()} table',
                'count': model._default_manager.count(),
                'fields': field_specs,
            }
        )

    specs.sort(key=lambda item: item['title'])
    return specs


def _data_admin_row_cells(instance, field_specs):
    cells = []
    for spec in field_specs:
        field = spec['field']
        formatted = _data_admin_format_value(field, getattr(instance, field.name, None))
        cells.append(
            {
                'name': spec['name'],
                'label': spec['label'],
                'input_type': spec['input_type'],
                'required': spec['required'],
                'options': spec['options'],
                'step': spec['step'],
                'value': '' if spec['input_type'] == 'checkbox' else formatted,
                'checked': bool(formatted) if spec['input_type'] == 'checkbox' else False,
            }
        )
    return cells


def _data_admin_create_cells(field_specs):
    cells = []
    for spec in field_specs:
        field = spec['field']
        default_value = field.get_default() if field.has_default() else None
        formatted = _data_admin_format_value(field, default_value)
        cells.append(
            {
                'name': spec['name'],
                'label': spec['label'],
                'input_type': spec['input_type'],
                'required': spec['required'],
                'options': spec['options'],
                'step': spec['step'],
                'value': '' if spec['input_type'] == 'checkbox' else formatted,
                'checked': bool(formatted) if spec['input_type'] == 'checkbox' else False,
            }
        )
    return cells


@login_required
@user_passes_test(is_admin)
def data_admin_console(request):
    model_specs = _data_admin_model_specs()
    if not model_specs:
        messages.error(request, 'No managed models are available for Data Admin.')
        return redirect('dashboard')

    model_map = {item['slug']: item for item in model_specs}
    requested_slug = request.GET.get('model') or request.POST.get('model_slug')
    selected_model = model_map.get(requested_slug, model_specs[0])

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip().lower()
        selected_model = model_map.get(request.POST.get('model_slug'), selected_model)
        model = selected_model['model']
        field_specs = selected_model['fields']

        if action == 'delete':
            pk = request.POST.get('pk')
            instance = get_object_or_404(model, pk=pk)
            try:
                instance.delete()
                messages.success(request, f'Deleted {model._meta.verbose_name} #{pk}.')
            except Exception as exc:
                messages.error(request, f'Could not delete record: {exc}')

        elif action in {'create', 'update'}:
            if action == 'update':
                pk = request.POST.get('pk')
                instance = get_object_or_404(model, pk=pk)
            else:
                instance = model()

            payload_errors = _data_admin_apply_payload(instance, field_specs, request.POST)
            if payload_errors:
                for item in payload_errors:
                    messages.error(request, item)
            else:
                try:
                    instance.full_clean()
                    instance.save()
                    verb = 'Updated' if action == 'update' else 'Created'
                    messages.success(request, f'{verb} {model._meta.verbose_name} #{instance.pk}.')
                except ValidationError as exc:
                    for item in _data_admin_validation_messages(exc):
                        messages.error(request, item)
                except Exception as exc:
                    messages.error(request, f'Save failed: {exc}')

        redirect_url = f"{reverse('data_admin_console')}?model={selected_model['slug']}"
        page = request.POST.get('page')
        if page:
            redirect_url += f'&page={page}'
        return redirect(redirect_url)

    queryset = selected_model['model']._default_manager.all()
    try:
        queryset = queryset.order_by('-pk')
    except Exception:
        pass

    paginator = Paginator(queryset, 20)
    page_obj = paginator.get_page(request.GET.get('page') or 1)
    rows = [
        {'pk': instance.pk, 'cells': _data_admin_row_cells(instance, selected_model['fields'])}
        for instance in page_obj.object_list
    ]

    context = {
        'model_specs': model_specs,
        'selected_model': {
            **selected_model,
            'colspan': len(selected_model['fields']) + 2,
        },
        'rows': rows,
        'create_cells': _data_admin_create_cells(selected_model['fields']),
        'page_obj': page_obj,
    }
    return render(request, 'accounts/data_admin_console.html', context)
