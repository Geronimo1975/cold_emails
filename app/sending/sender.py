import logging
import random
import smtplib
import time
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
from typing import Optional
from urllib.parse import quote

from django.conf import settings
from django.utils import timezone
from jinja2 import Environment, BaseLoader, select_autoescape

logger = logging.getLogger(__name__)

jinja_env = Environment(
    loader=BaseLoader(),
    autoescape=select_autoescape(["html"]),
)


def render_template(template_str: str, context: dict) -> str:
    tpl = jinja_env.from_string(template_str)
    return tpl.render(**context)


def build_tracking_context(lead, campaign, tracking_id: uuid.UUID) -> dict:
    base_url = settings.APP_BASE_URL.rstrip("/")
    unsubscribe_url = f"{base_url}/t/unsubscribe/{tracking_id}/"
    return {
        "business_name": lead.business_name,
        "city": lead.city or "Hamburg",
        "postal_code": lead.postal_code or "",
        "industry_text": lead.get_industry_display_de(),
        "contact_person": lead.contact_person or "",
        "unsubscribe_url": unsubscribe_url,
        "tracking_id": str(tracking_id),
    }


def inject_tracking_pixel(html_body: str, tracking_id: uuid.UUID) -> str:
    base_url = settings.APP_BASE_URL.rstrip("/")
    pixel_url = f"{base_url}/t/open/{tracking_id}.png"
    pixel_tag = f'<img src="{pixel_url}" width="1" height="1" alt="" style="display:none;" />'
    if "</body>" in html_body.lower():
        return html_body.replace("</body>", f"{pixel_tag}</body>", 1)
    return html_body + pixel_tag


def rewrite_links_for_tracking(html_body: str, tracking_id: uuid.UUID) -> str:
    import re
    base_url = settings.APP_BASE_URL.rstrip("/")

    def replace_href(match):
        url = match.group(1)
        if url.startswith(base_url) or url.startswith("mailto:"):
            return match.group(0)
        encoded = quote(url, safe="")
        return f'href="{base_url}/t/click/{tracking_id}/{encoded}/"'

    return re.sub(r'href="([^"]+)"', replace_href, html_body)


DSGVO_FOOTER = """
<div style="margin-top:30px;padding-top:15px;border-top:1px solid #e0e0e0;font-size:11px;color:#888;font-family:Arial,sans-serif;">
<p>Diese E-Mail wurde Ihnen auf Basis eines berechtigten Interesses gemäß Art. 6 Abs. 1 lit. f DSGVO zugesandt.
Als B2B-Unternehmen haben wir ein legitimes Interesse, Ihnen unser Reinigungsangebot vorzustellen.</p>
<p>
<strong>North Cleaning Services GmbH</strong><br>
Geschäftsführer: [Geschäftsführer Name]<br>
Anschrift: [Straße, PLZ Hamburg]<br>
Tel: [Telefonnummer]<br>
E-Mail: info@north-cleaning.de<br>
USt-IdNr.: DE[Nummer]<br>
HRB [Nummer], Amtsgericht Hamburg
</p>
<p>Wenn Sie keine weiteren E-Mails von uns erhalten möchten, können Sie sich hier abmelden:
<a href="{{ unsubscribe_url }}" style="color:#888;">Abmelden / Unsubscribe</a></p>
</div>
"""


def build_email_message(
    from_name: str,
    from_email: str,
    reply_to: str,
    to_email: str,
    subject: str,
    html_body: str,
    tracking_id: uuid.UUID,
    track_opens: bool = True,
    track_clicks: bool = True,
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((from_name, from_email))
    msg["To"] = to_email
    msg["Reply-To"] = reply_to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=from_email.split("@")[1])

    base_url = settings.APP_BASE_URL.rstrip("/")
    unsubscribe_url = f"{base_url}/t/unsubscribe/{tracking_id}/"
    msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    if track_clicks:
        html_body = rewrite_links_for_tracking(html_body, tracking_id)
    if track_opens:
        html_body = inject_tracking_pixel(html_body, tracking_id)

    import re
    plain_text = re.sub(r"<[^>]+>", "", html_body)
    plain_text = re.sub(r"\n\s*\n", "\n\n", plain_text).strip()

    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def send_email_via_smtp(smtp_account, msg: MIMEMultipart) -> tuple:
    try:
        if smtp_account.use_ssl:
            server = smtplib.SMTP_SSL(smtp_account.smtp_host, smtp_account.smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_account.smtp_host, smtp_account.smtp_port, timeout=30)
            if smtp_account.use_tls:
                server.starttls()
        server.login(smtp_account.smtp_username, smtp_account.smtp_password)
        from_addr = smtp_account.email_address
        to_addr = msg["To"]
        server.sendmail(from_addr, to_addr, msg.as_string())
        server.quit()
        message_id = msg.get("Message-ID", "")
        return True, message_id
    except smtplib.SMTPRecipientsRefused as e:
        return False, f"Recipients refused: {e}"
    except smtplib.SMTPAuthenticationError as e:
        return False, f"Auth error: {e}"
    except Exception as e:
        return False, str(e)


def get_available_smtp_account():
    from sending.models import SMTPAccount
    accounts = SMTPAccount.objects.filter(is_active=True).exclude(health_status="error")
    for account in accounts:
        if account.can_send():
            return account
    return None


def send_campaign_email(enrollment_id: int, step_id: int) -> bool:
    from campaigns.models import CampaignEnrollment, SequenceStep
    from tracking.models import EmailLog
    from django.utils import timezone

    try:
        enrollment = CampaignEnrollment.objects.select_related("lead", "campaign").get(pk=enrollment_id)
        step = SequenceStep.objects.get(pk=step_id)
    except (CampaignEnrollment.DoesNotExist, SequenceStep.DoesNotExist):
        logger.error(f"Enrollment {enrollment_id} or step {step_id} not found")
        return False

    lead = enrollment.lead
    campaign = enrollment.campaign

    if not lead.is_generic_b2b_email(lead.email):
        logger.warning(f"Skipping personal email: {lead.email}")
        return False

    if lead.unsubscribed:
        logger.info(f"Lead {lead.email} is unsubscribed, skipping")
        return False

    smtp_account = get_available_smtp_account()
    if smtp_account is None:
        logger.warning("No available SMTP account, requeueing")
        return False

    tracking_id = uuid.uuid4()
    context = build_tracking_context(lead, campaign, tracking_id)
    # Only append DSGVO footer if the template doesn't already embed the unsubscribe link
    if "unsubscribe_url" in step.body_template:
        full_body_template = step.body_template
    else:
        full_body_template = step.body_template + DSGVO_FOOTER
    subject = render_template(step.subject_template, context)
    html_body = render_template(full_body_template, context)

    email_log = EmailLog.objects.create(
        lead=lead,
        campaign=campaign,
        sequence_step=step,
        smtp_account=smtp_account,
        enrollment=enrollment,
        tracking_id=tracking_id,
        subject=subject,
        from_email=f"{campaign.from_name} <{smtp_account.email_address}>",
        status=EmailLog.Status.QUEUED,
    )

    msg = build_email_message(
        from_name=campaign.from_name,
        from_email=smtp_account.email_address,
        reply_to=campaign.reply_to_email,
        to_email=lead.email,
        subject=subject,
        html_body=html_body,
        tracking_id=tracking_id,
        track_opens=campaign.track_opens,
        track_clicks=campaign.track_clicks,
    )

    success, result = send_email_via_smtp(smtp_account, msg)

    if success:
        email_log.status = EmailLog.Status.SENT
        email_log.message_id = result
        email_log.sent_at = timezone.now()
        email_log.save(update_fields=["status", "message_id", "sent_at"])
        smtp_account.sent_today += 1
        smtp_account.sent_this_hour += 1
        smtp_account.consecutive_bounces = 0
        smtp_account.save(update_fields=["sent_today", "sent_this_hour", "consecutive_bounces"])
        if lead.status == "new":
            lead.status = "contacted"
            lead.save(update_fields=["status"])
        logger.info(f"Sent email to {lead.email} (step {step.step_number}, tracking: {tracking_id})")
        return True
    else:
        email_log.status = EmailLog.Status.FAILED
        email_log.error_message = result
        email_log.save(update_fields=["status", "error_message"])
        smtp_account.last_error = result
        smtp_account.save(update_fields=["last_error"])
        logger.error(f"Failed to send to {lead.email}: {result}")
        return False
