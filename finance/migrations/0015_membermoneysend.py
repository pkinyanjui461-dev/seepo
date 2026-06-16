import datetime

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('groups', '0004_group_client_updated_at_group_client_uuid'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('finance', '0014_cashreceipt_cashreceiptexpense'),
    ]

    operations = [
        migrations.CreateModel(
            name='MemberMoneySend',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('send_date', models.DateField(db_index=True, default=datetime.date.today)),
                ('member_name', models.CharField(max_length=200)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('is_sent', models.BooleanField(db_index=True, default=False)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_member_money_sends', to=settings.AUTH_USER_MODEL)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='member_money_sends', to='groups.group')),
            ],
            options={
                'ordering': ['send_date', 'group__name', 'member_name'],
            },
        ),
    ]
