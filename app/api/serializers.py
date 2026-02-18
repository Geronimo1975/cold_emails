from rest_framework import serializers
from leads.models import Lead, LeadList
from campaigns.models import Campaign, CampaignEnrollment
from tracking.models import EmailLog


class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            "id","business_name","email","phone","website","address","city",
            "postal_code","contact_person","position","industry","source",
            "status","unsubscribed","created_at","updated_at",
        ]
        read_only_fields = ["id","created_at","updated_at"]

    def validate_email(self, value):
        if not Lead.is_generic_b2b_email(value):
            raise serializers.ValidationError(
                "Personal email addresses are not accepted (DSGVO compliance). Only generic B2B emails allowed."
            )
        return value.lower()


class LeadBulkImportSerializer(serializers.Serializer):
    leads = LeadSerializer(many=True)
    lead_list_id = serializers.IntegerField(required=False, allow_null=True)
    source = serializers.ChoiceField(choices=Lead.Source.choices, default="dataforseo")


class CampaignStatsSerializer(serializers.ModelSerializer):
    emails_sent = serializers.IntegerField(read_only=True)
    open_rate = serializers.FloatField(read_only=True)
    reply_rate = serializers.FloatField(read_only=True)
    total_leads = serializers.IntegerField(read_only=True)

    class Meta:
        model = Campaign
        fields = ["id","name","status","emails_sent","open_rate","reply_rate","total_leads"]


class ReplyWebhookSerializer(serializers.Serializer):
    lead_email = serializers.EmailField()
    campaign_id = serializers.IntegerField(required=False)
    message_id = serializers.CharField(required=False, allow_blank=True)
    reply_text = serializers.CharField(required=False, allow_blank=True)


class EmailLogSerializer(serializers.ModelSerializer):
    lead_email = serializers.CharField(source="lead.email", read_only=True)
    campaign_name = serializers.CharField(source="campaign.name", read_only=True)

    class Meta:
        model = EmailLog
        fields = ["id","lead_email","campaign_name","status","subject","sent_at","opened_at","clicked_at","tracking_id"]
