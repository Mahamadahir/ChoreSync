from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chore_sync', '0008_calendar_writable'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendar',
            name='channel_id',
            field=models.CharField(blank=True, help_text='Google webhook channel identifier (events.watch).', max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='calendar',
            name='resource_id',
            field=models.CharField(blank=True, help_text='Google resource identifier associated with the watch channel.', max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='calendar',
            name='watch_expires_at',
            field=models.DateTimeField(blank=True, help_text='When the current Google watch channel expires.', null=True),
        ),
        migrations.AddField(
            model_name='calendar',
            name='webhook_token',
            field=models.CharField(blank=True, help_text='Opaque token sent with watch channel to verify callbacks.', max_length=255, null=True),
        ),
    ]
