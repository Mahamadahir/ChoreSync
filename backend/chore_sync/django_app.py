from django.apps import AppConfig

class ChoreSyncConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chore_sync"
    label = "chore_sync"  # optional, ensures unique label
