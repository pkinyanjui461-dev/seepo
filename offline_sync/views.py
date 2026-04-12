import json
from datetime import datetime, timezone as dt_timezone
from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import SyncLog
from .registry import get_ordered_model_names, get_sync_spec


def _client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _log_event(direction, model_name, records_count=0, conflicts_count=0, errors=None, client_ip=None):
    SyncLog.objects.create(
        direction=direction,
        model_name=model_name,
        records_count=records_count,
        conflicts_count=conflicts_count,
        errors=errors or [],
        client_ip=client_ip,
    )


def _normalize_sync_push_error(model_name, exc):
    message = str(exc or '').strip()
    lowered = message.lower()

    if (
        model_name == 'member'
        and 'duplicate key value violates unique constraint' in lowered
        and 'member_number' in lowered
        and 'group_id' in lowered
    ):
        return 'member_number already exists in this group. Use a different member number.'

    return message or 'Unknown server error.'


def debug_only(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not settings.DEBUG:
            return HttpResponseForbidden('Debug sync endpoints are disabled.')
        return view_func(request, *args, **kwargs)

    return _wrapped


@login_required
@require_GET
def sync_ping(request):
    return JsonResponse({'online': True, 'ts': int(timezone.now().timestamp())})


@login_required
@require_GET
def sync_pull(request):
    model_name = request.GET.get('model', '').strip()
    spec = get_sync_spec(model_name)
    if not spec:
        return JsonResponse({'error': 'Unsupported model.'}, status=400)
    if model_name == 'user' and not (request.user.is_superuser or request.user.role in ('admin', 'ict')):
        return JsonResponse({'error': 'Forbidden for this model.'}, status=403)

    since_raw = request.GET.get('since', '0')
    try:
        since_ts = float(since_raw)
    except (TypeError, ValueError):
        since_ts = 0

    queryset = spec.model.objects.all().order_by('updated_at', 'pk')
    if since_ts > 0:
        since_dt = datetime.fromtimestamp(since_ts, tz=dt_timezone.utc)
        queryset = queryset.filter(updated_at__gt=since_dt)

    records = [spec.serialize(instance) for instance in queryset]
    current_ts = int(timezone.now().timestamp())
    _log_event('pull', model_name, records_count=len(records), client_ip=_client_ip(request))

    return JsonResponse({'records': records, 'count': len(records), 'ts': current_ts})


@login_required
@require_POST
def sync_push(request):
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    model_name = str(payload.get('model', '')).strip()
    records = payload.get('records', [])
    if not isinstance(records, list):
        return JsonResponse({'error': 'records must be an array.'}, status=400)

    spec = get_sync_spec(model_name)
    if not spec:
        return JsonResponse({'error': 'Unsupported model.'}, status=400)
    if model_name == 'user' and not (request.user.is_superuser or request.user.role in ('admin', 'ict')):
        return JsonResponse({'error': 'Forbidden for this model.'}, status=403)

    synced = 0
    conflicts = 0
    errors = []
    records_saved = []

    for index, record in enumerate(records):
        try:
            if not isinstance(record, dict):
                raise ValueError('Record must be an object.')

            client_uuid = str(record.get('client_uuid', '')).strip()
            if not client_uuid:
                raise ValueError('client_uuid is required.')

            defaults = spec.apply_payload(record, request)
            incoming_client_updated_at = defaults.get('client_updated_at')
            raw_password = defaults.pop('password', None)

            existing = spec.model.objects.filter(client_uuid=client_uuid).first()
            if existing:
                existing_client_updated_at = getattr(existing, 'client_updated_at', None)
                if (
                    existing_client_updated_at
                    and incoming_client_updated_at
                    and incoming_client_updated_at < existing_client_updated_at
                ):
                    conflicts += 1
                    continue

                for field_name, value in defaults.items():
                    setattr(existing, field_name, value)
                if raw_password and hasattr(existing, 'set_password'):
                    existing.set_password(raw_password)
                existing.save()
                instance = existing
            else:
                instance = spec.model(client_uuid=client_uuid, **defaults)
                if raw_password and hasattr(instance, 'set_password'):
                    instance.set_password(raw_password)
                instance.save()

            synced += 1
            records_saved.append({'client_uuid': client_uuid, 'server_id': instance.pk})
        except Exception as exc:
            errors.append({'index': index, 'error': _normalize_sync_push_error(model_name, exc)})

    _log_event(
        'push',
        model_name,
        records_count=synced,
        conflicts_count=conflicts,
        errors=errors,
        client_ip=_client_ip(request),
    )

    return JsonResponse(
        {
            'synced': synced,
            'conflicts': conflicts,
            'errors': errors,
            'records_saved': records_saved,
        }
    )


@login_required
@debug_only
@require_GET
def debug_queue(request):
    logs = SyncLog.objects.all()[:200]
    serialized = [
        {
            'id': log.pk,
            'direction': log.direction,
            'model_name': log.model_name,
            'records_count': log.records_count,
            'conflicts_count': log.conflicts_count,
            'errors': log.errors,
            'client_ip': log.client_ip,
            'created_at': log.created_at.isoformat(),
        }
        for log in logs
    ]
    return JsonResponse({'logs': serialized, 'count': len(serialized)})


@login_required
@debug_only
@require_GET
def debug_status(request):
    counts = {}
    for model_name in get_ordered_model_names():
        spec = get_sync_spec(model_name)
        if spec:
            counts[model_name] = spec.model.objects.count()

    return JsonResponse(
        {
            'models': counts,
            'sync_log_count': SyncLog.objects.count(),
            'debug_enabled': settings.DEBUG,
            'ts': int(timezone.now().timestamp()),
        }
    )


@login_required
@debug_only
@require_POST
def debug_clear(request):
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        payload = {}

    deleted_records = 0
    model_name = str(payload.get('model', '')).strip()

    if model_name:
        spec = get_sync_spec(model_name)
        if not spec:
            return JsonResponse({'error': 'Unsupported model.'}, status=400)
        deleted_records, _ = spec.model.objects.all().delete()

    deleted_logs, _ = SyncLog.objects.all().delete()

    return JsonResponse(
        {
            'cleared_model': model_name or None,
            'deleted_records': deleted_records,
            'deleted_logs': deleted_logs,
        }
    )


@require_GET
def service_worker(request):
    offline_group_urls = []
    try:
        from groups.models import Group

        group_ids = Group.objects.values_list('pk', flat=True)[:300]
        for group_id in group_ids:
            offline_group_urls.extend(
                [
                    f'/groups/{group_id}/',
                    f'/groups/{group_id}/edit/',
                    f'/members/group/{group_id}/',
                    f'/members/group/{group_id}/add/',
                    f'/finance/group/{group_id}/forms/',
                    f'/finance/group/{group_id}/forms/create/',
                ]
            )
    except Exception:
        offline_group_urls = []

    response = render(request, 'offline_sync/sw.js', {'offline_group_urls': offline_group_urls})
    response['Content-Type'] = 'application/javascript'
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@require_GET
def web_manifest(request):
    manifest = {
        'id': '/',
        'name': 'SEEPO Accounting',
        'short_name': 'SEEPO',
        'description': 'Offline-capable accounting and sync-enabled field workflows for SEEPO.',
        'start_url': '/?source=pwa',
        'scope': '/',
        'display': 'standalone',
        'display_override': ['standalone', 'minimal-ui', 'browser'],
        'background_color': '#ffffff',
        'theme_color': '#6C5DD3',
        'icons': [
            {
                'src': '/static/img/pwa-icon-192.png',
                'sizes': '192x192',
                'type': 'image/png',
                'purpose': 'any maskable',
            },
            {
                'src': '/static/img/pwa-icon-512.png',
                'sizes': '512x512',
                'type': 'image/png',
                'purpose': 'any maskable',
            },
        ],
    }

    response = JsonResponse(manifest)
    response['Content-Type'] = 'application/manifest+json'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@require_GET
def offline_fallback(request):
    return render(request, 'offline_sync/offline.html')
