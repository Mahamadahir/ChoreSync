from django.db import migrations


def cleanup_calendar_duplicates(apps, schema_editor):
    Calendar = apps.get_model('chore_sync', 'Calendar')
    # Remove placeholder rows created by exchange_code before the real external_id was known.
    # Anyone who completed the select step already has a real-ID row; these are safe to delete.
    deleted, _ = Calendar.objects.filter(provider='google', external_id='primary').delete()
    if deleted:
        print(f"  Deleted {deleted} orphan 'primary' placeholder calendar row(s).")

    # Internal calendars should never push events to an external provider.
    updated = Calendar.objects.filter(provider='internal', push_enabled=True).update(push_enabled=False)
    if updated:
        print(f"  Set push_enabled=False on {updated} internal calendar(s).")


class Migration(migrations.Migration):

    dependencies = [
        ('chore_sync', '0026_tasktemplate_recur_end'),
    ]

    operations = [
        migrations.RunPython(cleanup_calendar_duplicates, migrations.RunPython.noop),
    ]
