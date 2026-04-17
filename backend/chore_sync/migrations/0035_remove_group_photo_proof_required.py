from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chore_sync', '0034_taskassignmenthistory_score_breakdown'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='group',
            name='photo_proof_required',
        ),
    ]
