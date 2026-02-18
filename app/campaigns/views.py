from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from .models import Campaign, SequenceStep, CampaignEnrollment
from leads.models import Lead, LeadList
from tracking.models import EmailLog


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        ctx["active_campaigns"] = Campaign.objects.filter(status="active").count()
        ctx["sent_today"] = EmailLog.objects.filter(sent_at__date=today).count()
        ctx["total_leads"] = Lead.objects.filter(unsubscribed=False).count()
        ctx["recent_campaigns"] = Campaign.objects.order_by("-created_at")[:5]
        from datetime import timedelta
        from django.db.models.functions import TruncDate
        last_7 = today - timedelta(days=6)
        ctx["daily_sent"] = list(
            EmailLog.objects.filter(sent_at__date__gte=last_7)
            .annotate(date=TruncDate("sent_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )
        ctx["open_rate"] = _global_open_rate()
        ctx["reply_rate"] = _global_reply_rate()
        return ctx


def _global_open_rate():
    total = EmailLog.objects.filter(status__in=["sent","delivered","opened","clicked","replied"]).count()
    if not total:
        return 0
    return round((EmailLog.objects.filter(opened_at__isnull=False).count() / total) * 100, 1)


def _global_reply_rate():
    total = EmailLog.objects.filter(status__in=["sent","delivered","opened","clicked","replied"]).count()
    if not total:
        return 0
    return round((EmailLog.objects.filter(status="replied").count() / total) * 100, 1)


class CampaignListView(LoginRequiredMixin, ListView):
    model = Campaign
    template_name = "campaigns/list.html"
    context_object_name = "campaigns"


class CampaignDetailView(LoginRequiredMixin, DetailView):
    model = Campaign
    template_name = "campaigns/detail.html"
    context_object_name = "campaign"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        campaign = self.object
        ctx["steps"] = campaign.steps.all()
        ctx["enrollments"] = CampaignEnrollment.objects.filter(campaign=campaign).select_related("lead")[:20]
        ctx["recent_logs"] = EmailLog.objects.filter(campaign=campaign).select_related("lead","sequence_step").order_by("-sent_at")[:20]
        ctx["stats"] = {"sent": campaign.emails_sent, "open_rate": campaign.open_rate, "reply_rate": campaign.reply_rate, "total_leads": campaign.total_leads}
        return ctx


class CampaignCreateView(LoginRequiredMixin, CreateView):
    model = Campaign
    template_name = "campaigns/form.html"
    fields = ["name","description","lead_list","from_name","reply_to_email","daily_send_limit","sending_window_start","sending_window_end","sending_days","track_opens","track_clicks"]
    success_url = reverse_lazy("campaigns:list")

    def form_valid(self, form):
        messages.success(self.request, f"Campaign '{form.instance.name}' created.")
        return super().form_valid(form)


class CampaignUpdateView(LoginRequiredMixin, UpdateView):
    model = Campaign
    template_name = "campaigns/form.html"
    fields = ["name","description","lead_list","from_name","reply_to_email","daily_send_limit","sending_window_start","sending_window_end","sending_days","track_opens","track_clicks"]

    def get_success_url(self):
        return reverse_lazy("campaigns:detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, "Campaign updated.")
        return super().form_valid(form)


class CampaignDeleteView(LoginRequiredMixin, DeleteView):
    model = Campaign
    template_name = "campaigns/confirm_delete.html"
    success_url = reverse_lazy("campaigns:list")


@login_required
def campaign_start(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    if campaign.status in [Campaign.Status.DRAFT, Campaign.Status.PAUSED]:
        campaign.status = Campaign.Status.ACTIVE
        campaign.save(update_fields=["status"])
        from sending.tasks import enroll_leads_in_campaign
        enroll_leads_in_campaign.delay(campaign.pk)
        messages.success(request, f"Campaign '{campaign.name}' started.")
    return redirect("campaigns:detail", pk=pk)


@login_required
def campaign_pause(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    if campaign.status == Campaign.Status.ACTIVE:
        campaign.status = Campaign.Status.PAUSED
        campaign.save(update_fields=["status"])
        messages.success(request, f"Campaign '{campaign.name}' paused.")
    return redirect("campaigns:detail", pk=pk)


@login_required
def sequence_step_create(request, campaign_pk):
    campaign = get_object_or_404(Campaign, pk=campaign_pk)
    if request.method == "POST":
        SequenceStep.objects.create(
            campaign=campaign,
            step_number=int(request.POST.get("step_number", 1)),
            subject_template=request.POST.get("subject_template", ""),
            body_template=request.POST.get("body_template", ""),
            delay_days=int(request.POST.get("delay_days", 0)),
        )
        messages.success(request, "Step added.")
        return redirect("campaigns:detail", pk=campaign_pk)
    return render(request, "campaigns/step_form.html", {"campaign": campaign})


@login_required
def sequence_step_edit(request, campaign_pk, step_pk):
    step = get_object_or_404(SequenceStep, pk=step_pk, campaign_id=campaign_pk)
    if request.method == "POST":
        step.subject_template = request.POST.get("subject_template", step.subject_template)
        step.body_template = request.POST.get("body_template", step.body_template)
        step.delay_days = int(request.POST.get("delay_days", step.delay_days))
        step.save()
        messages.success(request, "Step updated.")
        return redirect("campaigns:detail", pk=campaign_pk)
    return render(request, "campaigns/step_form.html", {"campaign": step.campaign, "step": step})


@login_required
def analytics_view(request):
    from datetime import timedelta
    from django.db.models.functions import TruncDate
    campaigns = Campaign.objects.all()
    selected_campaign_id = request.GET.get("campaign")
    today = timezone.localdate()
    last_30 = today - timedelta(days=29)
    qs = EmailLog.objects.filter(sent_at__date__gte=last_30)
    if selected_campaign_id:
        qs = qs.filter(campaign_id=selected_campaign_id)
    daily_stats = list(
        qs.annotate(date=TruncDate("sent_at"))
        .values("date")
        .annotate(
            sent=Count("id"),
            opened=Count("id", filter=Q(opened_at__isnull=False)),
            clicked=Count("id", filter=Q(clicked_at__isnull=False)),
            replied=Count("id", filter=Q(status="replied")),
        )
        .order_by("date")
    )
    return render(request, "dashboard/analytics.html", {
        "campaigns": campaigns,
        "selected_campaign_id": selected_campaign_id,
        "daily_stats": daily_stats,
    })
