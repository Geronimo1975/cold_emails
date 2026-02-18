from django.urls import path
from . import views

app_name = "api"

urlpatterns = [
    path("leads/", views.LeadCreateView.as_view(), name="api-lead-create"),
    path("leads/import/", views.LeadBulkImportView.as_view(), name="api-lead-bulk-import"),
    path("leads/stats/", views.lead_stats_api, name="api-lead-stats"),
    path("campaigns/", views.campaign_list_api, name="api-campaign-list"),
    path("campaigns/<int:pk>/stats/", views.CampaignStatsView.as_view(), name="api-campaign-stats"),
    path("webhooks/reply/", views.ReplyWebhookView.as_view(), name="api-webhook-reply"),
]
