import logging
import email
from typing import Optional

import imapclient

logger = logging.getLogger(__name__)

BOUNCE_INDICATORS = [
    "delivery status notification",
    "undeliverable",
    "mail delivery failed",
    "mailer-daemon",
    "delivery failure",
    "returned mail",
    "bounce",
    "permanent failure",
    "5.1.1",
    "5.4.1",
    "user unknown",
    "mailbox not found",
    "no such user",
]


def check_bounces(smtp_account) -> int:
    """
    Connect to IMAP, check for bounce emails, update lead statuses.
    Returns number of bounces found.
    """
    if not smtp_account.imap_host or not smtp_account.imap_username:
        return 0

    bounce_count = 0
    try:
        client = imapclient.IMAPClient(
            smtp_account.imap_host,
            port=smtp_account.imap_port,
            ssl=True,
            timeout=30,
        )
        client.login(smtp_account.imap_username, smtp_account.imap_password)
        client.select_folder("INBOX")

        # Search for unseen messages from MAILER-DAEMON
        messages = client.search(["UNSEEN", "FROM", "MAILER-DAEMON"])
        if not messages:
            messages = client.search(["UNSEEN", "SUBJECT", "Undeliverable"])

        if messages:
            response = client.fetch(messages, ["RFC822"])
            for uid, data in response.items():
                raw = data[b"RFC822"]
                msg = email.message_from_bytes(raw)
                bounced_email = _extract_bounced_email(msg)
                if bounced_email:
                    _mark_lead_bounced(bounced_email, smtp_account)
                    bounce_count += 1

            # Mark as seen
            client.set_flags(messages, [imapclient.SEEN])

        client.logout()
    except Exception as e:
        logger.error(f"[Bounce] IMAP error for {smtp_account.email_address}: {e}")

    if bounce_count >= 3:
        smtp_account.health_status = "warning"
        smtp_account.save(update_fields=["health_status"])
        logger.warning(f"[Bounce] {smtp_account.email_address} has {bounce_count} bounces — flagged as warning")

    return bounce_count


def _extract_bounced_email(msg) -> Optional[str]:
    """Try to extract the original recipient from a bounce message."""
    import re
    # Check headers
    for header in ["X-Failed-Recipients", "X-Original-To", "Final-Recipient"]:
        val = msg.get(header, "")
        if val:
            email_match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", val)
            if email_match:
                return email_match.group(0).lower()

    # Check body for email addresses
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() in ("text/plain", "message/delivery-status"):
                try:
                    body += part.get_payload(decode=True).decode("utf-8", errors="ignore")
                except Exception:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
        except Exception:
            pass

    email_match = re.search(r"Final-Recipient:.*?rfc822;\s*([\w.+-]+@[\w.-]+\.\w+)", body, re.IGNORECASE)
    if email_match:
        return email_match.group(1).lower()

    return None


def _mark_lead_bounced(email_address: str, smtp_account) -> None:
    from leads.models import Lead
    from tracking.models import EmailLog
    from django.utils import timezone

    leads = Lead.objects.filter(email__iexact=email_address)
    for lead in leads:
        lead.status = Lead.Status.BOUNCED
        lead.save(update_fields=["status"])
        EmailLog.objects.filter(lead=lead, status__in=["sent", "queued"]).update(
            status="bounced",
            bounced_at=timezone.now(),
        )
        logger.info(f"[Bounce] Marked {email_address} as bounced")

    smtp_account.consecutive_bounces += 1
    smtp_account.save(update_fields=["consecutive_bounces"])
