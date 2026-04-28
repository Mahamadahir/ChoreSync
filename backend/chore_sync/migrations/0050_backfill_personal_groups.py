"""Create a personal group for every existing user who doesn't already have one."""
import uuid as _uuid
from django.db import migrations


def create_personal_groups(apps, schema_editor):
    User = apps.get_model('chore_sync', 'User')
    Group = apps.get_model('chore_sync', 'Group')
    GroupMembership = apps.get_model('chore_sync', 'GroupMembership')

    users_with_personal = set(
        GroupMembership.objects
        .filter(group__is_personal=True)
        .values_list('user_id', flat=True)
    )

    for user in User.objects.all():
        if user.id in users_with_personal:
            continue
        group = Group.objects.create(
            name='Personal',
            group_code=f'personal-{_uuid.uuid4().hex[:12]}',
            owner=user,
            is_personal=True,
        )
        GroupMembership.objects.create(user=user, group=group, role='moderator')


class Migration(migrations.Migration):

    dependencies = [
        ('chore_sync', '0049_group_is_personal'),
    ]

    operations = [
        migrations.RunPython(create_personal_groups, migrations.RunPython.noop),
    ]
