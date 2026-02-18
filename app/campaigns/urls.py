from django.urls import path
from . import views

app_name = "campaigns"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("campaigns/", views.CampaignListView.as_view(), name="list"),
    path("campaigns/add/", views.CampaignCreateView.as_view(), name="create"),
    path("campaigns/<int:pk>/", views.CampaignDetailView.as_view(), name="detail"),
    path("campaigns/<int:pk>/edit/", views.CampaignUpdateView.as_view(), name="edit"),
    path("campaigns/<int:pk>/delete/", views.CampaignDeleteView.as_view(), name="delete"),
    path("campaigns/<int:pk>/start/", views.campaign_start, name="start"),
    path("campaigns/<int:pk>/pause/", views.campaign_pause, name="pause"),
    path("campaigns/<int:campaign_pk>/steps/add/", views.sequence_step_create, name="step-create"),
    path("campaigns/<int:campaign_pk>/steps/<int:step_pk>/edit/", views.sequence_step_edit, name="step-edit"),
    path("analytics/", views.analytics_view, name="analytics"),
]
