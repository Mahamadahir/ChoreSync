from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chore_sync', '0045_cleanup_stale_fields'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='group',
            name='reassignment_rule',
        ),
    ]
