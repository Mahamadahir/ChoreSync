"""
Management command: register_google_webhooks

Registers (or renews) Google Calendar push-notification watch channels for every
Calendar row that has a GoogleCalendarSync entry but no active channel_id.

Safe to re-run — skips calendars that already have a valid (non-expired) channel.

Usage:
    python manage.py register_google_webhooks
    python manage.py register_google_webhooks --force   # renew even if still valid
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Register Google Calendar webhook watch channels for all synced calendars."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Renew channels even if they are still active.',
        )

    def handle(self, *args, **options):
        import datetime
        from django.conf import settings
        from chore_sync.models import Calendar, GoogleCalendarSync
        from chore_sync.services.google_calendar_service import GoogleCalendarService

        callback = getattr(settings, 'GOOGLE_WEBHOOK_CALLBACK_URL', '')
        if not callback:
            self.stderr.write(self.style.ERROR(
                'GOOGLE_WEBHOOK_CALLBACK_URL is not set. Add it to secrets.prod.env and restart.'
            ))
            return

        self.stdout.write(f'Webhook callback URL: {callback}')

        force = options['force']
        now = datetime.datetime.now(datetime.timezone.utc)
        margin = datetime.timedelta(minutes=30)

        calendars = (
            Calendar.objects
            .filter(provider='google', google_sync__isnull=False)
            .select_related('google_sync', 'user')
        )

        if not calendars.exists():
            self.stdout.write('No Google calendars with a sync row found.')
            return

        registered = 0
        skipped = 0
        failed = 0

        for cal in calendars:
            sync = cal.google_sync
            if not force and sync.channel_id and sync.watch_expires_at and (sync.watch_expires_at - now) > margin:
                self.stdout.write(f'  SKIP  {cal.name!r} — channel active until {sync.watch_expires_at}')
                skipped += 1
                continue
            try:
                svc = GoogleCalendarService(cal.user)
                svc.ensure_watch_channel(cal)
                # Reload to get updated channel_id
                sync.refresh_from_db()
                if sync.channel_id:
                    self.stdout.write(self.style.SUCCESS(
                        f'  OK    {cal.name!r} — channel {sync.channel_id[:8]}… expires {sync.watch_expires_at}'
                    ))
                    registered += 1
                else:
                    self.stderr.write(f'  WARN  {cal.name!r} — ensure_watch_channel ran but no channel_id saved '
                                      f'(is GOOGLE_WEBHOOK_CALLBACK_URL reachable from the internet?)')
                    failed += 1
            except Exception as exc:
                self.stderr.write(f'  FAIL  {cal.name!r} — {exc}')
                failed += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nDone — {registered} registered, {skipped} skipped, {failed} failed.'
        ))
