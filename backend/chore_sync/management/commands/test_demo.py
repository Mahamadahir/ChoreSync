from __future__ import annotations

import json
import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from chore_sync.models import Calendar, Event, NotificationPreference
from chore_sync.management.commands.seed_demo import (
    DEMO_USERS,
    TEMPLATES_GROUP_A,
    TEMPLATES_GROUP_B,
    USER_EVENTS,
)

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Seed only the demo users and internal calendar blocking events, then "
        "print the task-template payloads that seed_demo would have created."
    )

    def handle(self, *args, **options):
        if options["wipe"]:
            self._wipe()

        with transaction.atomic():
            users = self._create_users()
            self._create_calendars_and_events(users)

        self.stdout.write(
            self.style.SUCCESS(
                "\nTest demo seed complete. Credentials (all share password Demo1234!):\n"
            )
        )
        for user in DEMO_USERS:
            self.stdout.write(f"  {user['username']:15s}  {user['email']}")

        self.stdout.write("\nTask templates that `seed_demo` would create:\n")
        self.stdout.write(json.dumps(self._task_template_payload(), indent=2))
        self.stdout.write("")

    def add_arguments(self, parser):
        parser.add_argument(
            "--wipe",
            action="store_true",
            help="Delete the demo users first, which also cascades their calendars and events.",
        )

    def _wipe(self) -> None:
        usernames = [user["username"] for user in DEMO_USERS]
        deleted_count, _ = User.objects.filter(username__in=usernames).delete()
        self.stdout.write(f"  Wiped demo users and related data ({deleted_count} records deleted).")

    def _create_users(self) -> dict[str, User]:
        users = {}
        for demo_user in DEMO_USERS:
            obj, created = User.objects.get_or_create(
                username=demo_user["username"],
                defaults=dict(
                    email=demo_user["email"],
                    first_name=demo_user["first_name"],
                    last_name=demo_user["last_name"],
                    email_verified=True,
                    timezone="Europe/London",
                ),
            )
            if created:
                obj.set_password(demo_user["password"])
                obj.save(update_fields=["password"])
                self.stdout.write(f"  Created user: {obj.username}")
            else:
                self.stdout.write(f"  User exists, skipping: {obj.username}")

            NotificationPreference.objects.get_or_create(user=obj)
            users[demo_user["username"]] = obj
        return users

    def _create_calendars_and_events(self, users: dict[str, User]) -> None:
        for username, events in USER_EVENTS.items():
            user = users[username]
            calendar, _ = Calendar.objects.get_or_create(
                user=user,
                provider="internal",
                external_id=None,
                defaults=dict(
                    name=f"{user.first_name}'s Calendar",
                    color=random.choice(["#6366F1", "#10B981", "#F59E0B", "#EF4444"]),
                    timezone="Europe/London",
                ),
            )

            for event in events:
                Event.objects.get_or_create(
                    calendar=calendar,
                    title=event["title"],
                    start=event["start"],
                    defaults=dict(
                        end=event["end"],
                        source="manual",
                        blocks_availability=True,
                        status="confirmed",
                    ),
                )

        self.stdout.write(f"  Created calendars and events for {len(users)} users.")

    def _task_template_payload(self) -> dict[str, object]:
        return {
            "task_templates": {
                "Riverside Flat": [self._serialize_template(template) for template in TEMPLATES_GROUP_A],
                "Cedar House": [self._serialize_template(template) for template in TEMPLATES_GROUP_B],
            }
        }

    def _serialize_template(self, template: dict[str, object]) -> dict[str, object]:
        serialized = dict(template)
        next_due = serialized.get("next_due")
        if next_due is not None:
            serialized["next_due"] = next_due.isoformat()
        return serialized
