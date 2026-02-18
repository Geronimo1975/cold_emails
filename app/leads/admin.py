from django.contrib import admin
from .models import Lead, LeadList, LeadTag


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ["business_name","email","city","industry","status","source","created_at","unsubscribed"]
    list_filter = ["status","industry","source","unsubscribed","lead_list"]
    search_fields = ["business_name","email","city"]
    readonly_fields = ["created_at","updated_at","unsubscribed_at","gdpr_legal_basis"]
    filter_horizontal = ["tags"]
    date_hierarchy = "created_at"


@admin.register(LeadList)
class LeadListAdmin(admin.ModelAdmin):
    list_display = ["name","lead_count","created_at"]


@admin.register(LeadTag)
class LeadTagAdmin(admin.ModelAdmin):
    list_display = ["name","color"]
