from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chore_sync', '0023_add_chatbot_session'),
    ]

    operations = [
        # Add suggestion_expires_at
        migrations.AddField(
            model_name='taskoccurrence',
            name='suggestion_expires_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='When the pre-assignment suggestion notification expires (auto-assigns after this).',
            ),
        ),
        # Add suggestion_declined_ids
        migrations.AddField(
            model_name='taskoccurrence',
            name='suggestion_declined_ids',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='List of user IDs who declined this suggestion (used for fallback assignment).',
            ),
        ),
        # Add 'suggested' as a valid status value
        migrations.AlterField(
            model_name='taskoccurrence',
            name='status',
            field=models.CharField(
                choices=[
                    ('suggested', 'Suggested'),
                    ('pending', 'Pending'),
                    ('in_progress', 'In Progress'),
                    ('snoozed', 'Snoozed'),
                    ('completed', 'Completed'),
                    ('overdue', 'Overdue'),
                    ('reassigned', 'Reassigned'),
                ],
                default='suggested',
                max_length=20,
            ),
        ),
    ]
