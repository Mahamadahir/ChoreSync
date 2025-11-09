"""Shared shopping list and inventory coordination services."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InventoryService:
    """Keeps household consumables, shopping lists, and stock levels in sync."""

    def add_inventory_item(self, *, group_id: str, payload: dict) -> None:
        """Add a new tracked item to the group's inventory."""
        # TODO: Normalize units, persist thresholds, and emit ActivityStream entries.
        raise NotImplementedError("TODO: implement inventory item creation")

    def update_inventory_item(self, *, item_id: str, updates: dict) -> None:
        """Edit metadata, thresholds, or suppliers for an item."""
        # TODO: Enforce permissions, recalc depletion forecasts, and notify watchers.
        raise NotImplementedError("TODO: implement inventory item update")

    def remove_inventory_item(self, *, item_id: str) -> None:
        """Archive an item so it no longer appears in depletion alerts."""
        # TODO: Mark item inactive, clean up references, and log audit data.
        raise NotImplementedError("TODO: implement inventory item removal")

    def sync_shopping_list(self, *, group_id: str) -> None:
        """Generate a shopping list based on low inventory and upcoming tasks."""
        # TODO: Inspect TaskTemplateService + TaskScheduler data and output consolidated list entries.
        raise NotImplementedError("TODO: implement shopping list sync")

    def consume_item(self, *, item_id: str, quantity: float, consumer_id: str) -> None:
        """Record consumption to adjust remaining stock."""
        # TODO: Decrement stock levels transactionally, update forecasts, and raise depletion alerts.
        raise NotImplementedError("TODO: implement inventory consumption event")

    def reconcile_purchase(self, *, group_id: str, receipt_payload: dict) -> None:
        """Apply a purchase receipt to restock items and clear shopping list entries."""
        # TODO: Parse receipt data, map line items to inventory records, and update budgets.
        raise NotImplementedError("TODO: implement purchase reconciliation")
