from django.contrib import admin
from .models import SMTPAccount


@admin.register(SMTPAccount)
class SMTPAccountAdmin(admin.ModelAdmin):
    list_display = ["email_address", "smtp_host", "is_active", "health_status", "warmup_mode", "warmup_day", "sent_today", "daily_limit"]
    list_filter = ["is_active", "health_status", "warmup_mode"]
    search_fields = ["email_address", "domain"]
    readonly_fields = ["sent_today", "sent_this_hour", "last_reset_date", "last_hour_reset", "consecutive_bounces", "warmup_day"]
    fieldsets = (
        ("Connection", {"fields": ("email_address", "display_name", "smtp_host", "smtp_port", "smtp_username", "smtp_password", "use_tls", "use_ssl", "domain")}),
        ("IMAP (bounce/reply detection)", {"fields": ("imap_host", "imap_port", "imap_username", "imap_password"), "classes": ("collapse",)}),
        ("Limits & Counters", {"fields": ("daily_limit", "hourly_limit", "sent_today", "sent_this_hour", "last_reset_date", "last_hour_reset")}),
        ("Warmup", {"fields": ("warmup_mode", "warmup_day", "warmup_start_date")}),
        ("Status", {"fields": ("is_active", "health_status", "last_error", "consecutive_bounces")}),
    )
