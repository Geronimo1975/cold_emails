import re
from django.db import models
from django.utils import timezone


class LeadTag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default="#6B7280")  # hex color

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class LeadList(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def lead_count(self):
        return self.leads.count()


class Lead(models.Model):
    class Industry(models.TextChoices):
        HAUSVERWALTUNG = "hausverwaltung", "Hausverwaltung"
        IMMOBILIEN = "immobilien", "Immobilien"
        FACILITY_MANAGEMENT = "facility_management", "Facility Management"
        GEWERBE = "gewerbe", "Gewerbebetrieb"
        OTHER = "other", "Sonstige"

    class Source(models.TextChoices):
        DATAFORSEO = "dataforseo", "DataforSEO"
        MANUAL = "manual", "Manuell"
        CSV_IMPORT = "csv_import", "CSV Import"
        WEBSITE_FORM = "website_form", "Website-Formular"

    class Status(models.TextChoices):
        NEW = "new", "Neu"
        CONTACTED = "contacted", "Kontaktiert"
        REPLIED = "replied", "Geantwortet"
        INTERESTED = "interested", "Interessiert"
        NOT_INTERESTED = "not_interested", "Kein Interesse"
        BOUNCED = "bounced", "Bounced"
        UNSUBSCRIBED = "unsubscribed", "Abgemeldet"

    # Business info
    business_name = models.CharField(max_length=300)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    address = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=10, blank=True)

    # Contact person (optional)
    contact_person = models.CharField(max_length=200, blank=True)
    position = models.CharField(max_length=200, blank=True)

    # Classification
    industry = models.CharField(max_length=30, choices=Industry.choices, default=Industry.OTHER)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)

    # Relations
    lead_list = models.ForeignKey(LeadList, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")
    tags = models.ManyToManyField(LeadTag, blank=True, related_name="leads")

    # DSGVO
    gdpr_legal_basis = models.CharField(
        max_length=100,
        default="legitimate_interest_b2b",
        help_text="Art. 6 Abs. 1 lit. f DSGVO — berechtigtes Interesse (B2B)",
    )
    unsubscribed = models.BooleanField(default=False)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Extra data (from DataforSEO etc.)
    extra_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["status"]),
            models.Index(fields=["industry"]),
        ]

    def __str__(self):
        return f"{self.business_name} <{self.email}>"

    def unsubscribe(self):
        self.unsubscribed = True
        self.unsubscribed_at = timezone.now()
        self.status = self.Status.UNSUBSCRIBED
        self.save(update_fields=["unsubscribed", "unsubscribed_at", "status"])

    @staticmethod
    def is_generic_b2b_email(email: str) -> bool:
        """
        Returns True if email is a generic B2B address (info@, kontakt@, etc.).
        Rejects personal emails like firstname.lastname@ to comply with DSGVO.
        """
        local = email.split("@")[0].lower()
        generic_prefixes = {
            "info", "kontakt", "contact", "office", "verwaltung",
            "mail", "post", "sekretariat", "empfang", "reception",
            "anfrage", "anfragen", "service", "support", "hallo",
            "hello", "team", "admin", "management", "geschaeftsfuehrung",
            "buchhaltung", "buchung", "booking",
        }
        if local in generic_prefixes:
            return True
        # Reject if it looks like firstname.lastname (two words separated by . or _)
        personal_pattern = re.compile(r"^[a-z]{2,}\.[a-z]{2,}$|^[a-z]{2,}_[a-z]{2,}$")
        if personal_pattern.match(local):
            return False
        return True

    def get_industry_display_de(self):
        mapping = {
            "hausverwaltung": "Hausverwaltung",
            "immobilien": "Immobilienfirma",
            "facility_management": "Facility-Management-Unternehmen",
            "gewerbe": "Gewerbebetrieb",
            "other": "Unternehmen",
        }
        return mapping.get(self.industry, "Unternehmen")
