import logging
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from leads.models import Lead, LeadList
from leads.importers import import_leads_from_dataforseo
from campaigns.models import Campaign, CampaignEnrollment
from tracking.models import EmailLog
from .serializers import (
    LeadSerializer, LeadBulkImportSerializer,
    CampaignStatsSerializer, ReplyWebhookSerializer,
)

logger = logging.getLogger(__name__)


class LeadCreateView(APIView):
    """POST /api/leads/ — add a single lead (from n8n)"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LeadSerializer(data=request.data)
        if serializer.is_valid():
            lead = serializer.save()
            return Response(LeadSerializer(lead).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LeadBulkImportView(APIView):
    """POST /api/leads/import/ — bulk import leads (from n8n / DataforSEO workflow)"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        lead_list_id = request.data.get("lead_list_id")
        lead_list = None
        if lead_list_id:
            try:
                lead_list = LeadList.objects.get(pk=lead_list_id)
            except LeadList.DoesNotExist:
                return Response({"error": "LeadList not found"}, status=404)

        leads_data = request.data.get("leads", [])
        source = request.data.get("source", "dataforseo")

        if not leads_data:
            return Response({"error": "No leads provided"}, status=400)

        result = import_leads_from_dataforseo(leads_data, lead_list=lead_list)
        return Response(result, status=status.HTTP_200_OK)


class CampaignStatsView(APIView):
    """GET /api/campaigns/<id>/stats/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            campaign = Campaign.objects.get(pk=pk)
        except Campaign.DoesNotExist:
            return Response({"error": "Campaign not found"}, status=404)
        serializer = CampaignStatsSerializer(campaign)
        return Response(serializer.data)


class ReplyWebhookView(APIView):
    """POST /api/webhooks/reply/ — n8n notifies us of a reply"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReplyWebhookSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        data = serializer.validated_data
        lead_email = data["lead_email"]

        try:
            lead = Lead.objects.get(email__iexact=lead_email)
        except Lead.DoesNotExist:
            return Response({"error": "Lead not found"}, status=404)

        # Mark lead as replied
        lead.status = Lead.Status.REPLIED
        lead.save(update_fields=["status"])

        # Stop all active enrollments for this lead
        CampaignEnrollment.objects.filter(lead=lead, status="active").update(status="stopped")

        # Update EmailLog
        campaign_id = data.get("campaign_id")
        log_qs = EmailLog.objects.filter(lead=lead, status__in=["sent","delivered","opened","clicked"])
        if campaign_id:
            log_qs = log_qs.filter(campaign_id=campaign_id)
        log_qs.update(status="replied", replied_at=timezone.now())

        logger.info(f"[Reply] {lead_email} marked as replied")
        return Response({"status": "ok", "lead_id": lead.pk})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def campaign_list_api(request):
    """GET /api/campaigns/ — list all campaigns with stats"""
    campaigns = Campaign.objects.all()
    serializer = CampaignStatsSerializer(campaigns, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def lead_stats_api(request):
    """GET /api/leads/stats/ — overall lead statistics"""
    return Response({
        "total": Lead.objects.count(),
        "new": Lead.objects.filter(status="new").count(),
        "contacted": Lead.objects.filter(status="contacted").count(),
        "replied": Lead.objects.filter(status="replied").count(),
        "interested": Lead.objects.filter(status="interested").count(),
        "bounced": Lead.objects.filter(status="bounced").count(),
        "unsubscribed": Lead.objects.filter(unsubscribed=True).count(),
    })
