"""Task Marketplace service for ChoreSync."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from chore_sync.models import Group, GroupMembership, MarketplaceListing, TaskOccurrence, UserStats


@dataclass
class MarketplaceService:

    def list_task(self, *, user, occurrence_id: str, bonus_points: int = 0) -> MarketplaceListing:
        occurrence = TaskOccurrence.objects.select_related('template__group', 'assigned_to').filter(
            id=occurrence_id
        ).first()
        if occurrence is None:
            raise ValueError("Task not found.")
        if str(occurrence.assigned_to_id) != str(user.id):
            raise PermissionError("You can only list tasks assigned to you.")
        if occurrence.status not in ('pending', 'snoozed'):
            raise ValueError("Only pending or snoozed tasks can be listed.")
        # Must have at least 2 hours until deadline
        if occurrence.deadline - timezone.now() < timedelta(hours=2):
            raise ValueError("Cannot list tasks due in less than 2 hours.")
        if MarketplaceListing.objects.filter(task_occurrence=occurrence).exists():
            raise ValueError("Task is already listed on the marketplace.")

        with transaction.atomic():
            listing = MarketplaceListing.objects.create(
                task_occurrence=occurrence,
                listed_by=user,
                group=occurrence.template.group,
                bonus_points=max(0, int(bonus_points)),
                expires_at=timezone.now() + timedelta(hours=24),
            )

        # Notify all other group members
        from chore_sync.services.notification_service import NotificationService
        members = GroupMembership.objects.filter(
            group=occurrence.template.group
        ).exclude(user=user)
        for m in members:
            NotificationService().emit_notification(
                recipient_id=str(m.user_id),
                notification_type='marketplace_claim',
                title=f"New task on marketplace: {occurrence.template.name}",
                content=(
                    f"{user.username} listed '{occurrence.template.name}' on the marketplace"
                    + (f" with {bonus_points} bonus points!" if bonus_points else ".")
                ),
                task_occurrence_id=occurrence.id,
            )
        return listing

    def claim_task(self, *, user, listing_id: int) -> TaskOccurrence:
        with transaction.atomic():
            listing = MarketplaceListing.objects.select_for_update().select_related(
                'task_occurrence__template__group', 'listed_by'
            ).filter(id=listing_id).first()
            if listing is None:
                raise ValueError("Listing not found.")
            if listing.expires_at < timezone.now():
                raise ValueError("This listing has expired.")
            if str(listing.listed_by_id) == str(user.id):
                raise PermissionError("You cannot claim your own listing.")
            if not GroupMembership.objects.filter(user=user, group=listing.group).exists():
                raise PermissionError("You are not a member of this group.")

            occurrence = listing.task_occurrence
            original_user = listing.listed_by
            bonus_pts = listing.bonus_points

            # Reassign
            occurrence.assigned_to = user
            occurrence.reassignment_reason = 'swap'
            occurrence.save(update_fields=['assigned_to', 'reassignment_reason'])

            # Award bonus points to claimer
            if bonus_pts > 0:
                stats, _ = UserStats.objects.get_or_create(
                    user=user, household=listing.group
                )
                stats.total_points += bonus_pts
                stats.save(update_fields=['total_points'])

            listing.delete()

        # Notify both parties
        from chore_sync.services.notification_service import NotificationService
        svc = NotificationService()
        svc.emit_notification(
            recipient_id=str(original_user.id),
            notification_type='marketplace_claim',
            title=f"Your task was claimed: {occurrence.template.name}",
            content=f"{user.username} claimed '{occurrence.template.name}' from the marketplace.",
            task_occurrence_id=occurrence.id,
        )
        svc.emit_notification(
            recipient_id=str(user.id),
            notification_type='marketplace_claim',
            title=f"You claimed: {occurrence.template.name}",
            content=(
                f"You claimed '{occurrence.template.name}'"
                + (f" and earned {bonus_pts} bonus points!" if bonus_pts > 0 else ".")
            ),
            task_occurrence_id=occurrence.id,
        )
        return occurrence

    def list_active(self, *, group_id: str, actor_id: str) -> list:
        if not GroupMembership.objects.filter(user_id=actor_id, group_id=group_id).exists():
            raise PermissionError("Not a member of this group.")
        return list(
            MarketplaceListing.objects.select_related(
                'task_occurrence__template', 'listed_by'
            ).filter(
                group_id=group_id,
                expires_at__gt=timezone.now(),
            )
        )
