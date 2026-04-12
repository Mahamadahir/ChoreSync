from django.core.management.base import BaseCommand
from chore_sync.models import Badge

BADGES = [
    {"name": "First Step",      "emoji": "👣", "description": "Complete your first task",               "criteria": {"tasks_completed": 1},   "points_value": 10},
    {"name": "Getting Started", "emoji": "🌱", "description": "Complete 5 tasks",                       "criteria": {"tasks_completed": 5},   "points_value": 20},
    {"name": "On a Roll",       "emoji": "🎯", "description": "Complete 25 tasks",                      "criteria": {"tasks_completed": 25},  "points_value": 50},
    {"name": "Century",         "emoji": "💯", "description": "Complete 100 tasks",                     "criteria": {"tasks_completed": 100}, "points_value": 100},
    {"name": "3-Day Streak",    "emoji": "🔥", "description": "Maintain a 3-day streak",                "criteria": {"streak_days": 3},       "points_value": 15},
    {"name": "Week Warrior",    "emoji": "⚡", "description": "Maintain a 7-day streak",                "criteria": {"streak_days": 7},       "points_value": 30},
    {"name": "Consistent",      "emoji": "📅", "description": "Maintain a 30-day streak",               "criteria": {"streak_days": 30},      "points_value": 100},
    {"name": "Point Collector", "emoji": "⭐", "description": "Earn 100 points",                        "criteria": {"total_points": 100},    "points_value": 10},
    {"name": "High Scorer",     "emoji": "🏆", "description": "Earn 500 points",                        "criteria": {"total_points": 500},    "points_value": 25},
    {"name": "Reliable",        "emoji": "✅", "description": "Achieve 80% on-time completion rate",    "criteria": {"on_time_rate": 0.8},    "points_value": 40},
    {"name": "Chef",            "emoji": "🍳", "description": "Complete 10 cooking tasks",              "criteria": {"category_count": {"category": "cooking",     "count": 10}}, "points_value": 30},
    {"name": "Clean Freak",     "emoji": "🧹", "description": "Complete 10 cleaning tasks",             "criteria": {"category_count": {"category": "cleaning",    "count": 10}}, "points_value": 30},
    {"name": "Handyman",        "emoji": "🔧", "description": "Complete 10 maintenance tasks",          "criteria": {"category_count": {"category": "maintenance", "count": 10}}, "points_value": 30},
    {"name": "Early Bird",      "emoji": "🌅", "description": "Complete 5 tasks before their deadline", "criteria": {"early_completions": 5}, "points_value": 25},
    {"name": "Good Samaritan",  "emoji": "🤝", "description": "Accept 3 emergency tasks",               "criteria": {"emergency_accepts": 3}, "points_value": 35},
    {"name": "Swap Master",     "emoji": "🔄", "description": "Complete 5 swapped tasks",               "criteria": {"swap_completions": 5},  "points_value": 25},
]


class Command(BaseCommand):
    help = "Seed the Badge table with default badges. Safe to re-run — skips existing names."

    def handle(self, *args, **options):
        created = 0
        for b in BADGES:
            _, c = Badge.objects.get_or_create(name=b["name"], defaults=b)
            if c:
                created += 1
                self.stdout.write(f"  Created: {b['emoji']} {b['name']}")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone — {created} created, {Badge.objects.count()} total badges in DB."
        ))
