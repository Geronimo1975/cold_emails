import logging
from urllib.parse import unquote
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils import timezone
from .models import EmailLog, TrackingEvent

logger = logging.getLogger(__name__)

TRANSPARENT_PIXEL = (
    b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff"
    b"\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00"
    b"\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"
)


def track_open(request, tracking_id):
    try:
        log = EmailLog.objects.get(tracking_id=tracking_id)
        if log.opened_at is None:
            log.opened_at = timezone.now()
            log.status = EmailLog.Status.OPENED
            log.save(update_fields=["opened_at", "status"])
        TrackingEvent.objects.create(
            email_log=log,
            event_type=TrackingEvent.EventType.OPEN,
            ip_address=_get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        )
        _fire_n8n_webhook(log, "open")
    except EmailLog.DoesNotExist:
        pass
    return HttpResponse(TRANSPARENT_PIXEL, content_type="image/gif")


def track_click(request, tracking_id, encoded_url):
    try:
        url = unquote(encoded_url)
        log = EmailLog.objects.get(tracking_id=tracking_id)
        if log.clicked_at is None:
            log.clicked_at = timezone.now()
            log.status = EmailLog.Status.CLICKED
            log.save(update_fields=["clicked_at", "status"])
        TrackingEvent.objects.create(
            email_log=log,
            event_type=TrackingEvent.EventType.CLICK,
            ip_address=_get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            url_clicked=url[:2000],
        )
        _fire_n8n_webhook(log, "click")
        return HttpResponseRedirect(url)
    except EmailLog.DoesNotExist:
        return HttpResponseRedirect("/")


def unsubscribe(request, tracking_id):
    try:
        log = EmailLog.objects.select_related("lead").get(tracking_id=tracking_id)
        lead = log.lead
        if not lead.unsubscribed:
            lead.unsubscribe()
            log.status = EmailLog.Status.UNSUBSCRIBED
            log.save(update_fields=["status"])
            TrackingEvent.objects.create(
                email_log=log,
                event_type=TrackingEvent.EventType.UNSUBSCRIBE,
                ip_address=_get_client_ip(request),
            )
            _fire_n8n_webhook(log, "unsubscribe")
        return render(request, "tracking/unsubscribe_confirm.html", {"lead": lead, "unsubscribed": True})
    except EmailLog.DoesNotExist:
        return render(request, "tracking/unsubscribe_confirm.html", {"lead": None, "unsubscribed": False})


def _get_client_ip(request):
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _fire_n8n_webhook(log, event_type):
    from django.conf import settings
    import threading, requests
    url = settings.N8N_WEBHOOK_URL
    if not url:
        return
    payload = {
        "event": event_type,
        "tracking_id": str(log.tracking_id),
        "lead_email": log.lead.email,
        "lead_id": log.lead.pk,
        "campaign_id": log.campaign.pk,
        "campaign_name": log.campaign.name,
    }
    secret = settings.N8N_WEBHOOK_SECRET
    def send():
        try:
            headers = {"X-Webhook-Secret": secret} if secret else {}
            requests.post(url, json=payload, headers=headers, timeout=5)
        except Exception as e:
            logger.warning(f"[Webhook] n8n notification failed: {e}")
    threading.Thread(target=send, daemon=True).start()
