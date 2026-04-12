from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chore_sync', '0031_replace_auto_moderator_with_group_type'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserPushToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=200, unique=True)),
                ('platform', models.CharField(choices=[('ios', 'iOS'), ('android', 'Android')], default='ios', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='push_tokens',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
    ]
