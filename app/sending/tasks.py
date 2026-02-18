import logging
import random
import time
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, queue="sending", max_retries=3, default_retry_delay=300)
def send_scheduled_emails(self):
    """
    Main Celery beat task — runs every 5 minutes.
    Finds enrollments due to send, dispatches individual send tasks.
    """
    from campaigns.models import CampaignEnrollment, Campaign
    from django.utils import timezone

    now = timezone.now()
    local_now = timezone.localtime(now)
    weekday = local_now.weekday()  # 0=Mon, 6=Sun
    current_time = local_now.time()

    # Get active campaigns
    active_campaigns = Campaign.objects.filter(status="active")

    for campaign in active_campaigns:
        # Check sending window and day
        if weekday not in campaign.sending_days:
            continue
        if not (campaign.sending_window_start <= current_time <= campaign.sending_window_end):
            continue

        # Find due enrollments
        due_enrollments = CampaignEnrollment.objects.filter(
            campaign=campaign,
            status="active",
            next_send_at__lte=now,
        ).select_related("lead", "campaign")[:campaign.daily_send_limit]

        for enrollment in due_enrollments:
            from campaigns.models import SequenceStep
            try:
                step = SequenceStep.objects.get(
                    campaign=campaign,
                    step_number=enrollment.current_step,
                )
            except SequenceStep.DoesNotExist:
                # No more steps, complete enrollment
                enrollment.status = "completed"
                enrollment.save(update_fields=["status"])
                continue

            # Dispatch with random delay (30-120 seconds between emails)
            delay = random.randint(30, 120)
            send_single_email.apply_async(
                args=[enrollment.pk, step.pk],
                countdown=delay,
                queue="sending",
            )


@shared_task(bind=True, queue="sending", max_retries=2, default_retry_delay=600)
def send_single_email(self, enrollment_id: int, step_id: int):
    """Send a single email and advance the enrollment."""
    from sending.sender import send_campaign_email
    from campaigns.models import CampaignEnrollment, SequenceStep
    from django.utils import timezone

    success = send_campaign_email(enrollment_id, step_id)

    if success:
        try:
            enrollment = CampaignEnrollment.objects.get(pk=enrollment_id)
            step = SequenceStep.objects.get(pk=step_id)

            # Advance to next step
            next_step_number = enrollment.current_step + 1
            try:
                next_step = SequenceStep.objects.get(
                    campaign=enrollment.campaign,
                    step_number=next_step_number,
                )
                if next_step.send_only_if_no_reply:
                    # Schedule next step
                    enrollment.current_step = next_step_number
                    enrollment.next_send_at = timezone.now() + timedelta(days=next_step.delay_days)
                    enrollment.save(update_fields=["current_step", "next_send_at"])
                else:
                    enrollment.current_step = next_step_number
                    enrollment.next_send_at = timezone.now() + timedelta(days=next_step.delay_days)
                    enrollment.save(update_fields=["current_step", "next_send_at"])
            except SequenceStep.DoesNotExist:
                # Final step sent
                enrollment.status = "completed"
                enrollment.save(update_fields=["status"])

        except CampaignEnrollment.DoesNotExist:
            pass
    else:
        try:
            self.retry()
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for enrollment {enrollment_id}")


@shared_task(queue="warmup")
def run_daily_warmup():
    """Advance warmup counters and reset daily send counts."""
    from sending.models import SMTPAccount
    from sending.warmup import advance_warmup

    accounts = SMTPAccount.objects.filter(is_active=True)
    for account in accounts:
        account.reset_daily_counter()
        if account.warmup_mode:
            advance_warmup(account)
    logger.info(f"[Warmup] Processed {accounts.count()} SMTP accounts")


@shared_task(queue="sending")
def check_all_bounces():
    """Check IMAP for bounce emails on all active accounts."""
    from sending.models import SMTPAccount
    from sending.bounce import check_bounces

    accounts = SMTPAccount.objects.filter(is_active=True, imap_host__isnull=False).exclude(imap_host="")
    total = 0
    for account in accounts:
        total += check_bounces(account)
    logger.info(f"[Bounce] Found {total} bounces total")


@shared_task(queue="sending")
def enroll_leads_in_campaign(campaign_id: int):
    """Enroll all eligible leads from a campaign's lead list."""
    from campaigns.models import Campaign, CampaignEnrollment, SequenceStep
    from leads.models import Lead
    from django.utils import timezone

    try:
        campaign = Campaign.objects.get(pk=campaign_id)
    except Campaign.DoesNotExist:
        return

    first_step = SequenceStep.objects.filter(campaign=campaign, step_number=1).first()
    if not first_step:
        logger.error(f"Campaign {campaign_id} has no step 1")
        return

    eligible_leads = Lead.objects.filter(
        lead_list=campaign.lead_list,
        unsubscribed=False,
        status__in=["new"],
    ).exclude(
        enrollments__campaign=campaign,
    )

    created = 0
    for lead in eligible_leads:
        CampaignEnrollment.objects.get_or_create(
            campaign=campaign,
            lead=lead,
            defaults={
                "current_step": 1,
                "status": "active",
                "next_send_at": timezone.now(),
            },
        )
        created += 1

    logger.info(f"Enrolled {created} leads in campaign {campaign.name}")
    return created
