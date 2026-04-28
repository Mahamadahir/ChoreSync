from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chore_sync', '0039_add_task_voting'),
    ]

    operations = [
        # Normalise any legacy values to on_create before constraining choices.
        migrations.RunSQL(
            sql="UPDATE chore_sync_group SET reassignment_rule = 'on_create' "
                "WHERE reassignment_rule IN ('after_n_tasks', 'after_n_weeks');",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name='group',
            name='reassignment_rule',
            field=models.CharField(
                max_length=50,
                choices=[('on_create', 'Every time a new task is created')],
                default='on_create',
            ),
        ),
        migrations.RemoveField(
            model_name='group',
            name='reassignment_value',
        ),
        migrations.RemoveField(
            model_name='group',
            name='last_reassigned_at',
        ),
    ]
