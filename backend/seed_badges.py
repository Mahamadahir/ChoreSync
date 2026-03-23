"""
Seed badges from a JSON file.

Usage:
    conda run -n choreSync python seed_badges.py badges.json
    conda run -n choreSync python seed_badges.py badges.json --clear
"""
import json
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chore_sync.settings")
django.setup()

from chore_sync.models import Badge  # noqa: E402


def seed(path: str, clear: bool = False) -> None:
    if clear:
        deleted, _ = Badge.objects.all().delete()
        print(f"Cleared {deleted} existing badges.")

    with open(path) as f:
        badges = json.load(f)

    created = updated = 0
    for b in badges:
        obj, is_new = Badge.objects.update_or_create(
            name=b["name"],
            defaults={
                "description": b.get("description", ""),
                "emoji":       b.get("emoji", ""),
                "criteria":    b["criteria"],
                "points_value": b.get("points_value", 0),
            },
        )
        if is_new:
            created += 1
        else:
            updated += 1

    print(f"Done. {created} created, {updated} updated. Total: {Badge.objects.count()} badges.")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "badges.json"
    clear = "--clear" in sys.argv
    seed(path, clear=clear)
