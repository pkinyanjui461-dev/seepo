# Generated manually to add sync metadata to GroupPerformanceForm and PerformanceEntry.

import uuid

import django.utils.timezone
from django.db import migrations, models


def populate_group_performance_form_client_uuids(apps, schema_editor):
    GroupPerformanceForm = apps.get_model('finance', 'GroupPerformanceForm')

    for row in GroupPerformanceForm.objects.filter(client_uuid__isnull=True).iterator():
        row.client_uuid = uuid.uuid4()
        row.save(update_fields=['client_uuid'])


def populate_performance_entry_client_uuids(apps, schema_editor):
    PerformanceEntry = apps.get_model('finance', 'PerformanceEntry')

    for row in PerformanceEntry.objects.filter(client_uuid__isnull=True).iterator():
        row.client_uuid = uuid.uuid4()
        row.save(update_fields=['client_uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0011_memberrecord_sync_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='groupperformanceform',
            name='client_uuid',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='groupperformanceform',
            name='client_updated_at',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='performanceentry',
            name='client_uuid',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='performanceentry',
            name='client_updated_at',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now),
        ),
        migrations.RunPython(populate_group_performance_form_client_uuids, migrations.RunPython.noop),
        migrations.RunPython(populate_performance_entry_client_uuids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='groupperformanceform',
            name='client_uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='performanceentry',
            name='client_uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
