from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chore_sync', '0018_add_reminder_windows'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MarketplaceListing',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bonus_points', models.PositiveIntegerField(default=0)),
                ('expires_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('task_occurrence', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='marketplace_listing', to='chore_sync.taskoccurrence')),
                ('listed_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='marketplace_listings', to=settings.AUTH_USER_MODEL)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='marketplace_listings', to='chore_sync.group')),
            ],
            options={
                'ordering': ['expires_at'],
            },
        ),
    ]
