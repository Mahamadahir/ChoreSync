from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chore_sync', '0007_event_external_etag_external_updated'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendar',
            name='writable',
            field=models.BooleanField(default=True, help_text='If False, skip pushing updates to this external calendar.'),
        ),
    ]
