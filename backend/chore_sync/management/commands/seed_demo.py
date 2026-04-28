"""
Management command: seed_demo
Populates the database with realistic demo data for showcasing ChoreSync features.

Usage:
    python manage.py seed_demo            # create everything fresh
    python manage.py seed_demo --wipe     # delete existing demo data first

Creates:
    - 4 users (alice, bob, carol, dave) in two groups
    - Internal calendars with calendar events blocking their time
    - Task templates (weekly, monthly, one-off) with occurrences
    - Marketplace listings
    - Task swap
    - Task preferences
    - UserStats for each user
"""
from __future__ import annotations

import random
from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from chore_sync.models import (
    Calendar,
    Event,
    Group,
    GroupMembership,
    MarketplaceListing,
    TaskOccurrence,
    TaskPreference,
    TaskTemplate,
    UserStats,
    TaskSwap,
    NotificationPreference,
)
from chore_sync.services.group_service import GroupOrchestrator
from chore_sync.services.task_lifecycle_service import TaskLifecycleService
from chore_sync.services.task_template_service import TaskTemplateService

User = get_user_model()

# ── Demo user definitions ─────────────────────────────────────────────────────

DEMO_USERS = [
    dict(username="alice_demo",  first_name="Alice",  last_name="Chen",    email="alice@demo.choresync",   password="Demo1234!"),
    dict(username="bob_demo",    first_name="Bob",    last_name="Martinez", email="bob@demo.choresync",    password="Demo1234!"),
    dict(username="carol_demo",  first_name="Carol",  last_name="Singh",   email="carol@demo.choresync",   password="Demo1234!"),
    dict(username="dave_demo",   first_name="Dave",   last_name="Okafor",  email="dave@demo.choresync",    password="Demo1234!"),
]

# ── Calendar event blocks (relative to today) ─────────────────────────────────

def _today_at(h: int, m: int = 0):
    """Return today's date at h:m UTC."""
    return timezone.now().replace(hour=h, minute=m, second=0, microsecond=0)


def _offset(days: int, h: int, m: int = 0):
    return _today_at(h, m) + timedelta(days=days)


# Each user gets a set of blocking events so the availability scoring has
# realistic data to work with.
USER_EVENTS: dict[str, list[dict]] = {
    "alice_demo": [
        dict(title="Morning Run",          start=_offset(0, 7),   end=_offset(0, 8)),
        dict(title="Team Standup",         start=_offset(1, 9),   end=_offset(1, 10)),
        dict(title="Design Review",        start=_offset(1, 14),  end=_offset(1, 16)),
        dict(title="Yoga Class",           start=_offset(2, 7),   end=_offset(2, 8, 30)),
        dict(title="Client Call",          start=_offset(3, 11),  end=_offset(3, 12)),
        dict(title="Weekly Planning",      start=_offset(7, 9),   end=_offset(7, 10)),
        dict(title="Doctor Appointment",   start=_offset(5, 10),  end=_offset(5, 11, 30)),
    ],
    "bob_demo": [
        dict(title="Gym Session",          start=_offset(0, 6),   end=_offset(0, 7, 30)),
        dict(title="Product Sprint",       start=_offset(1, 10),  end=_offset(1, 13)),
        dict(title="Lunch with Team",      start=_offset(2, 12),  end=_offset(2, 13, 30)),
        dict(title="Code Review",          start=_offset(3, 15),  end=_offset(3, 17)),
        dict(title="Date Night",           start=_offset(4, 19),  end=_offset(4, 22)),
        dict(title="Football Practice",    start=_offset(6, 17),  end=_offset(6, 19)),
    ],
    "carol_demo": [
        dict(title="Lecture: Statistics",  start=_offset(1, 8),   end=_offset(1, 10)),
        dict(title="Study Group",          start=_offset(2, 14),  end=_offset(2, 17)),
        dict(title="Part-time Shift",      start=_offset(3, 9),   end=_offset(3, 15)),
        dict(title="Tutorial Session",     start=_offset(4, 11),  end=_offset(4, 12)),
        dict(title="Library — thesis",     start=_offset(5, 13),  end=_offset(5, 18)),
    ],
    "dave_demo": [
        dict(title="Early Commute",        start=_offset(0, 7, 30), end=_offset(0, 8, 30)),
        dict(title="Ops War Room",         start=_offset(1, 9),   end=_offset(1, 12)),
        dict(title="On-call Shift",        start=_offset(2, 18),  end=_offset(3, 8)),
        dict(title="Kid Pickup",           start=_offset(4, 15),  end=_offset(4, 16)),
        dict(title="Weekend BBQ",          start=_offset(5, 12),  end=_offset(5, 20)),
    ],
}

# ── Task template definitions ──────────────────────────────────────────────────

NOW = timezone.now()

TEMPLATES_GROUP_A = [
    dict(
        name="Vacuum Living Room",
        category="cleaning",
        difficulty=2,
        estimated_mins=30,
        recurring_choice="weekly",
        next_due=NOW + timedelta(days=2),
        details="Including under the sofa cushions.",
        importance="core",
    ),
    dict(
        name="Clean Bathroom",
        category="cleaning",
        difficulty=3,
        estimated_mins=45,
        recurring_choice="weekly",
        next_due=NOW + timedelta(days=4),
        details="Scrub toilet, sink, and tiles.",
        importance="core",
    ),
    dict(
        name="Take Out Bins",
        category="other",
        difficulty=1,
        estimated_mins=10,
        recurring_choice="weekly",
        next_due=NOW + timedelta(days=1),
        details="Wheelie bin goes out Monday night.",
        importance="core",
    ),
    dict(
        name="Grocery Run",
        category="cooking",
        difficulty=2,
        estimated_mins=60,
        recurring_choice="every_n_days",
        recur_value=5,
        next_due=NOW + timedelta(days=3),
        details="Check shared list before going.",
        importance="core",
    ),
    dict(
        name="Cook Dinner",
        category="cooking",
        difficulty=3,
        estimated_mins=60,
        recurring_choice="custom",
        days_of_week=["mon", "wed", "fri"],
        next_due=NOW + timedelta(days=1),
        details="Serves everyone in the house.",
        importance="core",
    ),
    dict(
        name="Replace Boiler Filter",
        category="maintenance",
        difficulty=2,
        estimated_mins=20,
        recurring_choice="monthly",
        next_due=NOW + timedelta(days=14),
        details="Filter is in the cupboard under the stairs.",
        importance="additional",
    ),
    dict(
        name="Wipe Kitchen Surfaces",
        category="cleaning",
        difficulty=1,
        estimated_mins=15,
        recurring_choice="custom",
        days_of_week=["tue", "thu", "sun"],
        next_due=NOW + timedelta(days=1),
        details="Hob, counters, and splashback.",
        importance="core",
    ),
    dict(
        name="Do Laundry",
        category="laundry",
        difficulty=2,
        estimated_mins=20,
        recurring_choice="every_n_days",
        recur_value=3,
        next_due=NOW + timedelta(days=2),
        details="Hang clothes to dry when done.",
        importance="core",
    ),
]

TEMPLATES_GROUP_B = [
    dict(
        name="Mow the Lawn",
        category="maintenance",
        difficulty=3,
        estimated_mins=60,
        recurring_choice="every_n_days",
        recur_value=10,
        next_due=NOW + timedelta(days=3),
        details="Edge the borders too.",
        importance="core",
    ),
    dict(
        name="Wash Dishes",
        category="cleaning",
        difficulty=1,
        estimated_mins=20,
        recurring_choice="custom",
        days_of_week=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        next_due=NOW + timedelta(days=1),
        details="Don't leave them overnight.",
        importance="core",
    ),
    dict(
        name="Empty Dishwasher",
        category="cleaning",
        difficulty=1,
        estimated_mins=10,
        recurring_choice="custom",
        days_of_week=["mon", "wed", "fri", "sun"],
        next_due=NOW + timedelta(days=1),
        details="Put everything back in the right place.",
        importance="core",
    ),
    dict(
        name="Meal Prep Sunday",
        category="cooking",
        difficulty=4,
        estimated_mins=120,
        recurring_choice="weekly",
        next_due=NOW + timedelta(days=3),
        details="Batch cook lunches for the week.",
        importance="additional",
    ),
    dict(
        name="Clean Fridge",
        category="cleaning",
        difficulty=2,
        estimated_mins=30,
        recurring_choice="monthly",
        next_due=NOW + timedelta(days=7),
        details="Wipe shelves and check expiry dates.",
        importance="additional",
    ),
]


class Command(BaseCommand):
    help = "Seed demo users, groups, calendar events, and tasks for showcasing ChoreSync."

    def add_arguments(self, parser):
        parser.add_argument(
            "--wipe",
            action="store_true",
            help="Delete all existing demo data before seeding.",
        )

    def handle(self, *args, **options):
        if options["wipe"]:
            self._wipe()

        with transaction.atomic():
            users = self._create_users()
            alice, bob, carol, dave = (users[u] for u in ["alice_demo", "bob_demo", "carol_demo", "dave_demo"])

            # Group A: Alice (owner/moderator) + Bob + Carol
            group_a = self._create_group(
                owner=alice,
                name="Riverside Flat",
                members=[bob, carol],
            )
            # Group B: Dave (owner/moderator) + Carol (in both groups) + Bob
            group_b = self._create_group(
                owner=dave,
                name="Cedar House",
                members=[carol, bob],
            )

            # Calendars + events
            calendars = self._create_calendars_and_events(users)

            # Task templates + occurrences
            self._create_tasks(group_a, alice, TEMPLATES_GROUP_A, users=[alice, bob, carol])
            self._create_tasks(group_b, dave, TEMPLATES_GROUP_B, users=[dave, carol, bob])

            # User stats
            self._create_stats(users)

            # Marketplace listing — Bob puts one of his tasks up for grabs
            self._create_marketplace_listing(group_a)

            # Task swap — Carol requests a swap with Alice
            self._create_swap(group_a)

            # Task preferences
            self._create_preferences(users, group_a)

        self.stdout.write(self.style.SUCCESS("\nDemo seed complete. Credentials (all share password Demo1234!):\n"))
        for u in DEMO_USERS:
            self.stdout.write(f"  {u['username']:15s}  {u['email']}")
        self.stdout.write("")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _wipe(self):
        usernames = [u["username"] for u in DEMO_USERS]
        users = User.objects.filter(username__in=usernames)
        group_names = ["Riverside Flat", "Cedar House"]

        Group.objects.filter(name__in=group_names).delete()
        self.stdout.write("  Wiped demo groups.")

        users.delete()
        self.stdout.write("  Wiped demo users.")

    def _create_users(self) -> dict[str, User]:
        users = {}
        for u in DEMO_USERS:
            obj, created = User.objects.get_or_create(
                username=u["username"],
                defaults=dict(
                    email=u["email"],
                    first_name=u["first_name"],
                    last_name=u["last_name"],
                    email_verified=True,
                    timezone="Europe/London",
                ),
            )
            if created:
                obj.set_password(u["password"])
                obj.save(update_fields=["password"])
                self.stdout.write(f"  Created user: {obj.username}")
            else:
                self.stdout.write(f"  User exists, skipping: {obj.username}")

            # Ensure notification prefs exist
            NotificationPreference.objects.get_or_create(user=obj)
            users[u["username"]] = obj
        return users

    def _create_group(
        self,
        *,
        owner: User,
        name: str,
        members: list[User],
    ) -> Group:
        existing = Group.objects.filter(name=name).first()
        if existing:
            self.stdout.write(f"  Group exists, skipping: {name}")
            return existing

        svc = GroupOrchestrator()
        group = svc.create_group(
            owner=owner,
            name=name,
        )

        for member in members:
            GroupMembership.objects.get_or_create(user=member, group=group, defaults={"role": "member"})

        # Create UserStats for every member
        for user in [owner, *members]:
            UserStats.objects.get_or_create(
                user=user,
                group=group,
                defaults={"total_tasks_completed": 0, "total_points": 0},
            )

        self.stdout.write(f"  Created group: {name}")
        return group

    def _create_calendars_and_events(self, users: dict[str, User]) -> dict[str, Calendar]:
        calendars = {}
        for username, ev_list in USER_EVENTS.items():
            user = users[username]
            cal, _ = Calendar.objects.get_or_create(
                user=user,
                provider="internal",
                external_id=None,
                defaults=dict(
                    name=f"{user.first_name}'s Calendar",
                    color=random.choice(["#6366F1", "#10B981", "#F59E0B", "#EF4444"]),
                    timezone="Europe/London",
                ),
            )
            calendars[username] = cal

            for ev in ev_list:
                Event.objects.get_or_create(
                    calendar=cal,
                    title=ev["title"],
                    start=ev["start"],
                    defaults=dict(
                        end=ev["end"],
                        source="manual",
                        blocks_availability=True,
                        status="confirmed",
                    ),
                )
        self.stdout.write(f"  Created calendars and events for {len(users)} users.")
        return calendars

    def _create_tasks(
        self,
        group: Group,
        creator: User,
        template_defs: list[dict],
        users: list[User],
    ) -> None:
        svc = TaskTemplateService()
        lc = TaskLifecycleService()

        for tdef in template_defs:
            # Skip if already exists for this group
            if TaskTemplate.objects.filter(name=tdef["name"], group=group).exists():
                continue

            tmpl = svc.create_template(
                creator=creator,
                group_id=str(group.id),
                payload=dict(tdef),
            )
            self.stdout.write(f"    Template: {tmpl.name} ({group.name})")

            # Generate the first occurrence (assigns via fairness pipeline)
            try:
                occurrences = lc.generate_recurring_instances(task_template_id=str(tmpl.id))
                if occurrences:
                    self.stdout.write(f"      -> Occurrence assigned to {occurrences[0].assigned_to}")
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"      Occurrence skipped: {exc}"))

        # Seed a few completed occurrences for history / stats
        templates = TaskTemplate.objects.filter(group=group, active=True)
        for i, tmpl in enumerate(templates[:4]):
            past_deadline = NOW - timedelta(days=random.randint(2, 14))
            user = users[i % len(users)]
            occ, created = TaskOccurrence.objects.get_or_create(
                template=tmpl,
                deadline=past_deadline,
                defaults=dict(
                    assigned_to=user,
                    status="completed",
                    completed_at=past_deadline - timedelta(hours=1),
                    points_earned=tmpl.difficulty * 10,
                ),
            )
            if not created and occ.status != "completed":
                occ.status = "completed"
                occ.completed_at = past_deadline - timedelta(hours=1)
                occ.save(update_fields=["status", "completed_at"])

    def _create_stats(self, users: dict[str, User]) -> None:
        stats_data = {
            "alice_demo": dict(total_tasks_completed=24, total_points=310, on_time_completion_rate=0.83, current_streak_days=5),
            "bob_demo":   dict(total_tasks_completed=18, total_points=245, on_time_completion_rate=0.78, current_streak_days=3),
            "carol_demo": dict(total_tasks_completed=31, total_points=420, on_time_completion_rate=0.90, current_streak_days=7),
            "dave_demo":  dict(total_tasks_completed=12, total_points=160, on_time_completion_rate=0.92, current_streak_days=4),
        }
        for username, data in stats_data.items():
            user = users[username]
            for group in Group.objects.filter(members__user=user):
                stats, created = UserStats.objects.get_or_create(
                    user=user,
                    group=group,
                    defaults=data,
                )
                if not created:
                    for field, val in data.items():
                        setattr(stats, field, val)
                    stats.save(update_fields=list(data.keys()))

    def _create_marketplace_listing(self, group: Group) -> None:
        # Find a pending occurrence in this group to list
        occ = (
            TaskOccurrence.objects.filter(
                template__group=group,
                status="pending",
            )
            .exclude(marketplace_listing__isnull=False)
            .first()
        )
        if occ is None:
            self.stdout.write("  No pending occurrence available for marketplace listing.")
            return

        MarketplaceListing.objects.get_or_create(
            task_occurrence=occ,
            defaults=dict(
                listed_by=occ.assigned_to or group.owner,
                group=group,
                bonus_points=20,
                expires_at=NOW + timedelta(days=2),
            ),
        )
        self.stdout.write(f"  Created marketplace listing: {occ.template.name}")

    def _create_swap(self, group: Group) -> None:
        # Find a pending occurrence to swap
        occ = (
            TaskOccurrence.objects.filter(
                template__group=group,
                status="pending",
            )
            .exclude(swap_requests__isnull=False)
            .exclude(marketplace_listing__isnull=False)
            .first()
        )
        if occ is None:
            self.stdout.write("  No pending occurrence available for swap.")
            return

        requester = occ.assigned_to or group.owner
        TaskSwap.objects.get_or_create(
            task=occ,
            from_user=requester,
            defaults=dict(
                status="pending",
                swap_type="open_request",
                reason="Can anyone swap with me? I have a clash this week.",
            ),
        )
        self.stdout.write(f"  Created task swap request: {occ.template.name}")

    def _create_preferences(self, users: dict[str, User], group: Group) -> None:
        prefs = [
            ("alice_demo", "Vacuum Living Room",    "prefer"),
            ("alice_demo", "Cook Dinner",           "avoid"),
            ("bob_demo",   "Cook Dinner",           "prefer"),
            ("bob_demo",   "Clean Bathroom",        "avoid"),
            ("carol_demo", "Do Laundry",            "prefer"),
            ("carol_demo", "Take Out Bins",         "neutral"),
        ]
        for username, task_name, pref in prefs:
            user = users.get(username)
            tmpl = TaskTemplate.objects.filter(name=task_name, group=group).first()
            if user and tmpl:
                TaskPreference.objects.get_or_create(
                    user=user,
                    task_template=tmpl,
                    defaults={"preference": pref},
                )
        self.stdout.write(f"  Created task preferences.")
