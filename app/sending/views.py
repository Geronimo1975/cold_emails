import smtplib

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django_filters.views import FilterView
import django_filters

from .models import SMTPAccount
from tracking.models import EmailLog


class SmtpAccountFilter(django_filters.FilterSet):
    class Meta:
        model = SMTPAccount
        fields = ["is_active", "health_status", "warmup_mode"]


class SmtpAccountListView(LoginRequiredMixin, ListView):
    model = SMTPAccount
    template_name = "settings/smtp_accounts.html"
    context_object_name = "accounts"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from sending.warmup import get_warmup_status
        ctx["warmup_statuses"] = {a.pk: get_warmup_status(a) for a in ctx["accounts"]}
        return ctx


class SmtpAccountCreateView(LoginRequiredMixin, CreateView):
    model = SMTPAccount
    template_name = "settings/smtp_account_form.html"
    fields = [
        "email_address", "display_name", "smtp_host", "smtp_port",
        "smtp_username", "smtp_password", "use_tls", "use_ssl",
        "imap_host", "imap_port", "imap_username", "imap_password",
        "domain", "daily_limit", "hourly_limit", "warmup_mode",
    ]
    success_url = reverse_lazy("sending:account-list")

    def form_valid(self, form):
        messages.success(self.request, "SMTP account added successfully.")
        return super().form_valid(form)


class SmtpAccountUpdateView(LoginRequiredMixin, UpdateView):
    model = SMTPAccount
    template_name = "settings/smtp_account_form.html"
    fields = [
        "email_address", "display_name", "smtp_host", "smtp_port",
        "smtp_username", "smtp_password", "use_tls", "use_ssl",
        "imap_host", "imap_port", "imap_username", "imap_password",
        "domain", "daily_limit", "hourly_limit", "warmup_mode", "is_active",
    ]
    success_url = reverse_lazy("sending:account-list")

    def form_valid(self, form):
        messages.success(self.request, "SMTP account updated.")
        return super().form_valid(form)


class SmtpAccountDeleteView(LoginRequiredMixin, DeleteView):
    model = SMTPAccount
    template_name = "settings/smtp_account_confirm_delete.html"
    success_url = reverse_lazy("sending:account-list")


@login_required
def test_smtp_connection(request, pk):
    try:
        account = SMTPAccount.objects.get(pk=pk)
    except SMTPAccount.DoesNotExist:
        return JsonResponse({"success": False, "error": "Account not found"})

    try:
        if account.use_ssl:
            server = smtplib.SMTP_SSL(account.smtp_host, account.smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(account.smtp_host, account.smtp_port, timeout=10)
            if account.use_tls:
                server.starttls()
        server.login(account.smtp_username, account.smtp_password)
        server.quit()
        account.health_status = SMTPAccount.HealthStatus.HEALTHY
        account.last_error = ""
        account.save(update_fields=["health_status", "last_error"])
        return JsonResponse({"success": True, "message": "Connection successful"})
    except Exception as e:
        account.health_status = SMTPAccount.HealthStatus.ERROR
        account.last_error = str(e)
        account.save(update_fields=["health_status", "last_error"])
        return JsonResponse({"success": False, "error": str(e)})


class EmailLogListView(LoginRequiredMixin, ListView):
    model = EmailLog
    template_name = "settings/email_logs.html"
    context_object_name = "logs"
    paginate_by = 50

    def get_queryset(self):
        qs = EmailLog.objects.select_related("lead", "campaign", "sequence_step").order_by("-queued_at")
        campaign_id = self.request.GET.get("campaign")
        status = self.request.GET.get("status")
        if campaign_id:
            qs = qs.filter(campaign_id=campaign_id)
        if status:
            qs = qs.filter(status=status)
        return qs
