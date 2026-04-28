from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chore_sync', '0048_alter_calendar_external_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='is_personal',
            field=models.BooleanField(default=False, db_index=True),
        ),
    ]
