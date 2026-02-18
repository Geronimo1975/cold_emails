from django.contrib import admin
from .models import EmailLog, TrackingEvent


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ["subject","lead","campaign","status","sent_at","opened_at","clicked_at"]
    list_filter = ["status","campaign"]
    search_fields = ["lead__email","subject","tracking_id"]
    readonly_fields = ["tracking_id","message_id","queued_at","sent_at","opened_at","clicked_at"]
    date_hierarchy = "queued_at"


@admin.register(TrackingEvent)
class TrackingEventAdmin(admin.ModelAdmin):
    list_display = ["event_type","email_log","occurred_at","ip_address"]
    list_filter = ["event_type"]
    readonly_fields = ["occurred_at"]
