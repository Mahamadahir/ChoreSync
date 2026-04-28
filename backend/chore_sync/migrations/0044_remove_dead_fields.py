"""
Remove fields that were never written or never read outside models.py.

- Calendar: sync_window_days, default_reminder_minutes
- Event: raw_payload
- UserStats: tasks_completed_this_week, tasks_completed_this_month
  (these were read by the API but never written; counts are now computed live)
- TaskAssignmentHistory: completed, completed_at
  (completion state is derived from the linked TaskOccurrence instead)
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chore_sync', '0043_move_streak_to_userstats'),
    ]

    operations = [
        migrations.RemoveField(model_name='calendar', name='sync_window_days'),
        migrations.RemoveField(model_name='calendar', name='default_reminder_minutes'),
        migrations.RemoveField(model_name='event', name='raw_payload'),
        migrations.RemoveField(model_name='userstats', name='tasks_completed_this_week'),
        migrations.RemoveField(model_name='userstats', name='tasks_completed_this_month'),
        migrations.RemoveField(model_name='taskassignmenthistory', name='completed'),
        migrations.RemoveField(model_name='taskassignmenthistory', name='completed_at'),
    ]
