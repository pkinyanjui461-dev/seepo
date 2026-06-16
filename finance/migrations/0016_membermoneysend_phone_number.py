from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0015_membermoneysend'),
    ]

    operations = [
        migrations.AddField(
            model_name='membermoneysend',
            name='phone_number',
            field=models.CharField(blank=True, max_length=30),
        ),
    ]
