"""
Cleanup migration:
  - Rename UserStats.household  → UserStats.group
  - Rename UserBadge.household  → UserBadge.group
  - Remove MarketplaceListing.group  (derivable via task_occurrence.template.group)
  - Remove Notification.sent_at     (duplicate of created_at)
  - Protect notification history: SET_NULL on group/task_occurrence/task_proposal/message FKs
  - Add choices= to Notification.type (no schema change, state only)
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chore_sync', '0044_remove_dead_fields'),
    ]

    operations = [
        # ── UserStats: household → group ──────────────────────────────────
        migrations.RenameField(
            model_name='userstats',
            old_name='household',
            new_name='group',
        ),
        migrations.AlterUniqueTogether(
            name='userstats',
            unique_together={('user', 'group')},
        ),

        # ── UserBadge: household → group ──────────────────────────────────
        migrations.RenameField(
            model_name='userbadge',
            old_name='household',
            new_name='group',
        ),
        migrations.AlterUniqueTogether(
            name='userbadge',
            unique_together={('user', 'badge', 'group')},
        ),

        # ── MarketplaceListing: drop redundant group FK ───────────────────
        migrations.RemoveField(
            model_name='marketplacelisting',
            name='group',
        ),

        # ── Notification: drop sent_at (duplicate of created_at) ─────────
        migrations.RemoveField(
            model_name='notification',
            name='sent_at',
        ),

        # ── Notification: protect history on target deletion (SET_NULL) ───
        migrations.AlterField(
            model_name='notification',
            name='group',
            field=models.ForeignKey(
                blank=True,
                help_text='Group this notification relates to (if any).',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='notifications',
                to='chore_sync.group',
            ),
        ),
        migrations.AlterField(
            model_name='notification',
            name='task_occurrence',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='notifications',
                to='chore_sync.taskoccurrence',
            ),
        ),
        migrations.AlterField(
            model_name='notification',
            name='task_proposal',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='notifications',
                to='chore_sync.taskproposal',
            ),
        ),
        migrations.AlterField(
            model_name='notification',
            name='message',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='notifications',
                to='chore_sync.message',
            ),
        ),

        # ── Notification.type: add choices (state-only, no schema change) ─
        migrations.AlterField(
            model_name='notification',
            name='type',
            field=models.CharField(
                max_length=50,
                choices=[
                    ('task_assigned', 'Task assigned'),
                    ('task_swap', 'Task swap'),
                    ('group_invite', 'Group invite'),
                    ('task_proposal', 'Task proposal'),
                    ('message', 'Message'),
                    ('deadline_reminder', 'Deadline reminder'),
                    ('emergency_reassignment', 'Emergency reassignment'),
                    ('badge_earned', 'Badge earned'),
                    ('marketplace_claim', 'Marketplace claim'),
                    ('suggestion_pattern', 'Smart suggestion: pattern'),
                    ('suggestion_availability', 'Smart suggestion: availability'),
                    ('suggestion_preference', 'Smart suggestion: preference'),
                    ('suggestion_streak', 'Smart suggestion: streak'),
                    ('suggestion_fairness', 'Smart suggestion: fairness'),
                    ('calendar_sync_complete', 'Calendar sync complete'),
                    ('task_suggestion', 'Task pre-assignment suggestion'),
                ],
            ),
        ),
    ]
