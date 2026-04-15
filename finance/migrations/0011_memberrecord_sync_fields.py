# Generated manually to add sync metadata to MemberRecord.

import uuid

import django.utils.timezone
from django.db import migrations, models


def populate_member_record_client_uuids(apps, schema_editor):
    MemberRecord = apps.get_model('finance', 'MemberRecord')

    for row in MemberRecord.objects.filter(client_uuid__isnull=True).iterator():
        row.client_uuid = uuid.uuid4()
        row.save(update_fields=['client_uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0010_expense_client_updated_at_expense_client_uuid_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='memberrecord',
            name='client_uuid',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='memberrecord',
            name='client_updated_at',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='memberrecord',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='memberrecord',
            name='updated_at',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now),
        ),
        migrations.RunPython(populate_member_record_client_uuids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='memberrecord',
            name='client_uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
