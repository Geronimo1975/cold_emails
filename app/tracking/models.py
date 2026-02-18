import uuid
from django.db import models


class EmailLog(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        OPENED = "opened", "Opened"
        CLICKED = "clicked", "Clicked"
        REPLIED = "replied", "Replied"
        BOUNCED = "bounced", "Bounced"
        FAILED = "failed", "Failed"
        UNSUBSCRIBED = "unsubscribed", "Unsubscribed"

    # Relations
    lead = models.ForeignKey("leads.Lead", on_delete=models.CASCADE, related_name="email_logs")
    campaign = models.ForeignKey("campaigns.Campaign", on_delete=models.CASCADE, related_name="email_logs")
    sequence_step = models.ForeignKey("campaigns.SequenceStep", on_delete=models.CASCADE, related_name="email_logs")
    smtp_account = models.ForeignKey("sending.SMTPAccount", on_delete=models.SET_NULL, null=True, related_name="email_logs")
    enrollment = models.ForeignKey("campaigns.CampaignEnrollment", on_delete=models.CASCADE, null=True, related_name="email_logs")

    # Tracking
    tracking_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    message_id = models.CharField(max_length=500, blank=True, help_text="SMTP Message-ID header")

    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)

    # Email content snapshot
    subject = models.CharField(max_length=500)
    from_email = models.CharField(max_length=300)

    # Timestamps
    queued_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    bounced_at = models.DateTimeField(null=True, blank=True)

    # Error info
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-queued_at"]
        indexes = [
            models.Index(fields=["lead", "campaign"]),
            models.Index(fields=["status"]),
            models.Index(fields=["sent_at"]),
        ]

    def __str__(self):
        return f"[{self.status}] {self.subject} → {self.lead.email}"


class TrackingEvent(models.Model):
    class EventType(models.TextChoices):
        OPEN = "open", "Open"
        CLICK = "click", "Click"
        UNSUBSCRIBE = "unsubscribe", "Unsubscribe"
        BOUNCE = "bounce", "Bounce"
        REPLY = "reply", "Reply"

    email_log = models.ForeignKey(EmailLog, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    occurred_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    url_clicked = models.TextField(blank=True)
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-occurred_at"]

    def __str__(self):
        return f"{self.event_type} — {self.email_log}"
