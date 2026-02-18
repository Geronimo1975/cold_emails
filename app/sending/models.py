from django.db import models
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedCharField


class SMTPAccount(models.Model):
    class HealthStatus(models.TextChoices):
        HEALTHY = "healthy", "Healthy"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"
        PAUSED = "paused", "Paused"

    # Connection
    email_address = models.EmailField(unique=True)
    display_name = models.CharField(max_length=200, default="North Cleaning Services GmbH")
    smtp_host = models.CharField(max_length=200)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_username = models.CharField(max_length=200)
    smtp_password = EncryptedCharField(max_length=500)
    use_tls = models.BooleanField(default=True)
    use_ssl = models.BooleanField(default=False)

    # IMAP for reply/bounce detection
    imap_host = models.CharField(max_length=200, blank=True)
    imap_port = models.PositiveIntegerField(default=993)
    imap_username = models.CharField(max_length=200, blank=True)
    imap_password = EncryptedCharField(max_length=500, blank=True)

    # Domain (for grouping)
    domain = models.CharField(max_length=200, blank=True, help_text="Sending domain, e.g. north-cleaning-services.de")

    # Limits
    daily_limit = models.PositiveIntegerField(default=50)
    hourly_limit = models.PositiveIntegerField(default=10)
    sent_today = models.PositiveIntegerField(default=0)
    sent_this_hour = models.PositiveIntegerField(default=0)
    last_reset_date = models.DateField(null=True, blank=True)
    last_hour_reset = models.DateTimeField(null=True, blank=True)

    # Warmup
    warmup_mode = models.BooleanField(default=True)
    warmup_day = models.PositiveIntegerField(default=0)
    warmup_start_date = models.DateField(null=True, blank=True)

    # Status
    is_active = models.BooleanField(default=True)
    health_status = models.CharField(max_length=10, choices=HealthStatus.choices, default=HealthStatus.HEALTHY)
    last_error = models.TextField(blank=True)
    consecutive_bounces = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["email_address"]
        verbose_name = "SMTP Account"
        verbose_name_plural = "SMTP Accounts"

    def __str__(self):
        return self.email_address

    def reset_daily_counter(self):
        today = timezone.localdate()
        if self.last_reset_date != today:
            self.sent_today = 0
            self.last_reset_date = today
            self.save(update_fields=["sent_today", "last_reset_date"])

    def reset_hourly_counter(self):
        now = timezone.now()
        if self.last_hour_reset is None or (now - self.last_hour_reset).total_seconds() >= 3600:
            self.sent_this_hour = 0
            self.last_hour_reset = now
            self.save(update_fields=["sent_this_hour", "last_hour_reset"])

    @property
    def effective_daily_limit(self):
        """Returns the actual limit considering warmup phase."""
        if not self.warmup_mode:
            return self.daily_limit
        day = self.warmup_day
        if day <= 3:
            return 5
        elif day <= 7:
            return 10
        elif day <= 14:
            return 25
        else:
            self.warmup_mode = False
            self.save(update_fields=["warmup_mode"])
            return self.daily_limit

    def can_send(self) -> bool:
        self.reset_daily_counter()
        self.reset_hourly_counter()
        return (
            self.is_active
            and self.health_status != self.HealthStatus.ERROR
            and self.sent_today < self.effective_daily_limit
            and self.sent_this_hour < self.hourly_limit
        )
