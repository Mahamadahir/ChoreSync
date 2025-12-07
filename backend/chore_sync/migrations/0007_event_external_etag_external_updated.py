from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chore_sync', '0006_user_timezone'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='external_etag',
            field=models.CharField(blank=True, help_text='Provider etag for conflict detection.', max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='event',
            name='external_updated',
            field=models.DateTimeField(blank=True, help_text='Last updated timestamp from provider (ISO).', null=True),
        ),
    ]
