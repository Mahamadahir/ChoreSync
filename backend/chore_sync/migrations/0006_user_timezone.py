from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chore_sync', '0005_emaillog_passwordresettoken'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='timezone',
            field=models.CharField(default='UTC', help_text='Preferred timezone for this user', max_length=50),
        ),
    ]
