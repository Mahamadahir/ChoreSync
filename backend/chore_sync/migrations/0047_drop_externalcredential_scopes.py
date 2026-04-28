from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chore_sync', '0046_remove_group_reassignment_rule'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='externalcredential',
            name='scopes',
        ),
    ]
