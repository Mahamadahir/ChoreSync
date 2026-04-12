from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chore_sync', '0025_add_notification_swap_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='tasktemplate',
            name='recur_end',
            field=models.DateField(
                blank=True,
                null=True,
                help_text='Optional date after which no new occurrences are generated.',
            ),
        ),
    ]
