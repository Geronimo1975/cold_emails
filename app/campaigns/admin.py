from django.contrib import admin
from .models import Campaign, SequenceStep, CampaignEnrollment


class SequenceStepInline(admin.TabularInline):
    model = SequenceStep
    extra = 0
    fields = ["step_number","subject_template","delay_days","send_only_if_no_reply"]


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ["name","status","lead_list","daily_send_limit","created_at"]
    list_filter = ["status"]
    search_fields = ["name"]
    inlines = [SequenceStepInline]


@admin.register(CampaignEnrollment)
class CampaignEnrollmentAdmin(admin.ModelAdmin):
    list_display = ["lead","campaign","current_step","status","next_send_at"]
    list_filter = ["status","campaign"]
    search_fields = ["lead__email","lead__business_name"]
    readonly_fields = ["enrolled_at"]
