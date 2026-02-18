from django.db import models
from leads.models import Lead, LeadList


class Campaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"

    class SendingDay(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    name = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    # Audience
    lead_list = models.ForeignKey(LeadList, on_delete=models.PROTECT, related_name="campaigns")

    # Sender identity
    from_name = models.CharField(max_length=200, default="North Cleaning Services GmbH")
    reply_to_email = models.EmailField(default="info@north-cleaning-services.de")

    # Sending schedule
    daily_send_limit = models.PositiveIntegerField(default=50)
    sending_window_start = models.TimeField(default="08:00")
    sending_window_end = models.TimeField(default="17:00")
    sending_days = models.JSONField(
        default=list,
        help_text="List of weekday integers (0=Mon, 6=Sun). Default Mon-Fri.",
    )
    timezone = models.CharField(max_length=50, default="Europe/Berlin")

    # Tracking
    track_opens = models.BooleanField(default=True)
    track_clicks = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.sending_days:
            self.sending_days = [0, 1, 2, 3, 4]  # Mon-Fri
        super().save(*args, **kwargs)

    @property
    def total_leads(self):
        return self.lead_list.leads.filter(
            unsubscribed=False,
            status__in=["new", "contacted"],
        ).count()

    @property
    def emails_sent(self):
        return self.email_logs.filter(status__in=["sent", "delivered", "opened", "clicked", "replied"]).count()

    @property
    def open_rate(self):
        sent = self.emails_sent
        if sent == 0:
            return 0
        opened = self.email_logs.filter(opened_at__isnull=False).count()
        return round((opened / sent) * 100, 1)

    @property
    def reply_rate(self):
        sent = self.emails_sent
        if sent == 0:
            return 0
        replied = self.email_logs.filter(status="replied").count()
        return round((replied / sent) * 100, 1)


class SequenceStep(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="steps")
    step_number = models.PositiveIntegerField()
    subject_template = models.CharField(max_length=500, help_text="Jinja2 template, e.g. Gebäudereinigung für {{business_name}}")
    body_template = models.TextField(help_text="Jinja2 HTML template. Use {{business_name}}, {{city}}, {{industry_text}}, {{unsubscribe_url}}")
    delay_days = models.PositiveIntegerField(default=0, help_text="Days after the previous step (0 = same day for step 1)")
    send_only_if_no_reply = models.BooleanField(default=True)

    class Meta:
        ordering = ["step_number"]
        unique_together = [("campaign", "step_number")]

    def __str__(self):
        return f"{self.campaign.name} — Step {self.step_number}"


class CampaignEnrollment(models.Model):
    """Tracks which leads are enrolled in which campaigns and at which step."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        STOPPED = "stopped", "Stopped (replied)"

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="enrollments")
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="enrollments")
    current_step = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    next_send_at = models.DateTimeField(null=True, blank=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("campaign", "lead")]
        ordering = ["next_send_at"]

    def __str__(self):
        return f"{self.lead} in {self.campaign} (step {self.current_step})"
