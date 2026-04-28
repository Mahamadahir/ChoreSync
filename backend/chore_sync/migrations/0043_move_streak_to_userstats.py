"""
Move streak tracking from User to UserStats.

- Adds UserStats.last_streak_date (the only field needed for streak logic)
- Removes User.on_time_streak_days, User.longest_on_time_streak_days, User.last_streak_date

Data migration: not needed — UserStats.current_streak_days and longest_streak_days
already mirror the User values (written in the same transaction). last_streak_date
defaults to NULL, which causes the first post-migration completion to reset the
streak to 1 for each group, which is the correct safe behaviour.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chore_sync', '0042_auth_event_token_refreshed_choice'),
    ]

    operations = [
        # Add last_streak_date to UserStats
        migrations.AddField(
            model_name='userstats',
            name='last_streak_date',
            field=models.DateField(
                blank=True,
                null=True,
                help_text='Date on which the streak was last updated for this group.',
            ),
        ),
        # Remove the three redundant fields from User
        migrations.RemoveField(model_name='user', name='on_time_streak_days'),
        migrations.RemoveField(model_name='user', name='longest_on_time_streak_days'),
        migrations.RemoveField(model_name='user', name='last_streak_date'),
    ]
