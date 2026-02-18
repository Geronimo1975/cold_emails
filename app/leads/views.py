import csv
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
import django_filters
from django_filters.views import FilterView
from .models import Lead, LeadList, LeadTag
from .importers import import_leads_from_csv


class LeadFilter(django_filters.FilterSet):
    business_name = django_filters.CharFilter(lookup_expr="icontains")
    email = django_filters.CharFilter(lookup_expr="icontains")
    city = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Lead
        fields = ["status", "industry", "source", "lead_list", "business_name", "email", "city"]


class LeadListView(LoginRequiredMixin, FilterView):
    model = Lead
    template_name = "leads/list.html"
    context_object_name = "leads"
    filterset_class = LeadFilter
    paginate_by = 50

    def get_queryset(self):
        return Lead.objects.select_related("lead_list").prefetch_related("tags").order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["total_count"] = Lead.objects.count()
        ctx["lists"] = LeadList.objects.all()
        return ctx


class LeadDetailView(LoginRequiredMixin, DetailView):
    model = Lead
    template_name = "leads/detail.html"
    context_object_name = "lead"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["email_logs"] = self.object.email_logs.select_related("campaign","sequence_step").order_by("-queued_at")[:20]
        return ctx


class LeadCreateView(LoginRequiredMixin, CreateView):
    model = Lead
    template_name = "leads/form.html"
    fields = ["business_name","email","phone","website","address","city","postal_code","contact_person","position","industry","source","lead_list","tags"]
    success_url = reverse_lazy("leads:list")

    def form_valid(self, form):
        messages.success(self.request, "Lead added.")
        return super().form_valid(form)


class LeadUpdateView(LoginRequiredMixin, UpdateView):
    model = Lead
    template_name = "leads/form.html"
    fields = ["business_name","email","phone","website","address","city","postal_code","contact_person","position","industry","status","lead_list","tags"]
    success_url = reverse_lazy("leads:list")


class LeadDeleteView(LoginRequiredMixin, DeleteView):
    model = Lead
    template_name = "leads/confirm_delete.html"
    success_url = reverse_lazy("leads:list")


@login_required
def import_csv_view(request):
    if request.method == "POST":
        csv_file = request.FILES.get("csv_file")
        lead_list_id = request.POST.get("lead_list")
        if not csv_file:
            messages.error(request, "No file uploaded.")
            return redirect("leads:import")
        try:
            lead_list = LeadList.objects.get(pk=lead_list_id) if lead_list_id else None
            content = csv_file.read().decode("utf-8")
            result = import_leads_from_csv(content, lead_list=lead_list)
            messages.success(request, f"Imported {result['created']} leads. Skipped {result['skipped']} (duplicates). Rejected {result['rejected']} (personal emails).")
        except Exception as e:
            messages.error(request, f"Import failed: {e}")
        return redirect("leads:list")
    lists = LeadList.objects.all()
    return render(request, "leads/import.html", {"lists": lists})


@login_required
def export_csv_view(request):
    qs = Lead.objects.all()
    status_filter = request.GET.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="leads_export.csv"'
    response.write("\ufeff")  # BOM for Excel
    writer = csv.writer(response)
    writer.writerow(["business_name","email","phone","website","city","postal_code","industry","status","source","contact_person","created_at"])
    for lead in qs:
        writer.writerow([lead.business_name,lead.email,lead.phone,lead.website,lead.city,lead.postal_code,lead.industry,lead.status,lead.source,lead.contact_person,lead.created_at.strftime("%Y-%m-%d")])
    return response


class LeadListListView(LoginRequiredMixin, ListView):
    model = LeadList
    template_name = "leads/lists.html"
    context_object_name = "lead_lists"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        for lst in ctx["lead_lists"]:
            lst.count = lst.leads.count()
        return ctx


class LeadListCreateView(LoginRequiredMixin, CreateView):
    model = LeadList
    template_name = "leads/list_form.html"
    fields = ["name","description"]
    success_url = reverse_lazy("leads:lead-lists")
