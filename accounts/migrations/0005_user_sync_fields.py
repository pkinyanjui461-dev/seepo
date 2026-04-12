from django.db import migrations, models
import django.utils.timezone
import uuid


def backfill_user_sync_fields(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    now = django.utils.timezone.now()
    seen = set()

    for user in User.objects.all().order_by('pk'):
        update_fields = []
        current_uuid = user.client_uuid

        if not current_uuid or str(current_uuid) in seen:
            new_uuid = uuid.uuid4()
            while str(new_uuid) in seen:
                new_uuid = uuid.uuid4()
            user.client_uuid = new_uuid
            current_uuid = new_uuid
            update_fields.append('client_uuid')

        seen.add(str(current_uuid))

        if not user.client_updated_at:
            user.client_updated_at = now
            update_fields.append('client_updated_at')

        if update_fields:
            user.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_notification'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='client_updated_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='user',
            name='client_uuid',
            field=models.UUIDField(blank=True, db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.RunPython(backfill_user_sync_fields, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='user',
            name='client_uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
