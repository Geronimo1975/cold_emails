"""
Management command: python manage.py seed_templates

Creates the 3 German email sequence steps for cold outreach, using the
North Cleaning Services professional HTML email template.
"""
from django.core.management.base import BaseCommand
from leads.models import LeadList
from campaigns.models import Campaign, SequenceStep


# ---------------------------------------------------------------------------
# BASE HTML WRAPPER — adapted from sendy_email_ncs_complete.html
# The content block is replaced per step. Jinja2 variables used throughout.
# ---------------------------------------------------------------------------

HTML_WRAPPER_START = """\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html lang="de" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<meta http-equiv="X-UA-Compatible" content="IE=edge"/>
<title>North Cleaning Services</title>
<style type="text/css">
body { margin:0; padding:0; font-family:Calibri,Arial,sans-serif; font-size:11pt; line-height:1.4; color:#000000; background-color:#ffffff; }
table { border-spacing:0; mso-table-lspace:0pt; mso-table-rspace:0pt; }
img { border:0; height:auto; line-height:100%; outline:none; text-decoration:none; -ms-interpolation-mode:bicubic; }
a { color:#0563C1; text-decoration:underline; }
</style>
</head>
<body style="margin:0;padding:0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;background-color:#ffffff;">
<table border="0" cellpadding="0" cellspacing="0" role="presentation" style="background-color:#ffffff;" width="100%">
<tbody><tr><td align="center" style="padding:20px 10px;">
<table border="0" cellpadding="0" cellspacing="0" role="presentation" style="max-width:650px;" width="650">
<tbody><tr>
<td style="padding:0;font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.4;color:#000000;">
"""

HTML_SIGNATURE = """\
<!-- CLOSING -->
<p style="margin:25pt 0 0 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">Mit freundlichen Grüßen</p>
<!-- SIGNATURE -->
<table border="0" cellpadding="0" cellspacing="0" role="presentation" style="margin-top:15px;padding-top:15px;border-top:1px solid #e1e1e1;" width="100%">
<tbody><tr><td style="padding:0;">
<p style="margin:0 0 2px 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;font-weight:bold;color:#000000;">Sebastian George Cucuiet</p>
<p style="margin:0 0 15px 0;font-family:Calibri,Arial,sans-serif;font-size:10pt;color:#000000;">Projekt Manager - Automatisierung und Entwicklung</p>
<table border="0" cellpadding="0" cellspacing="0" role="presentation" style="margin:15px 0;" width="100%">
<tbody><tr>
<td style="padding:0;" width="120" valign="top">
<img alt="North Cleaning Services" height="120" src="https://sendy.north-cleaning.de/uploads/signature/ncs-logo.png" style="display:block;width:120px;height:120px;max-width:120px;" width="120" />
</td>
<td style="padding:0;" align="right" valign="top">
<img alt="QR Code - North Cleaning Services Magazin" height="70" src="https://sendy.north-cleaning.de/uploads/signature/qr-magazin.png" style="display:block;width:70px;height:70px;max-width:70px;" width="70" />
</td>
</tr></tbody>
</table>
<p style="margin:0 0 3px 0;font-family:Calibri,Arial,sans-serif;font-size:9pt;color:#000000;line-height:1.3;"><strong>North Cleaning Services GmbH</strong> | Neue Stra&szlig;e 1 | 21244 Buchholz idN | Germany</p>
<p style="margin:0 0 3px 0;font-family:Calibri,Arial,sans-serif;font-size:9pt;color:#000000;line-height:1.3;"><strong>Tel</strong> +49(0)40 3336 4450 | <strong>Direct</strong> +49(0)162 4532 111 | <strong>Fax</strong> +49(0)40 2261 1861</p>
<p style="margin:0 0 15px 0;font-family:Calibri,Arial,sans-serif;font-size:9pt;color:#000000;line-height:1.3;"><strong>E-mail</strong> <a href="mailto:service@north-cleaning.de" style="color:#0563C1;text-decoration:underline;">service@north-cleaning.de</a> | <a href="https://hamburger-gebaeudereinigung24.de" style="color:#0563C1;text-decoration:underline;">hamburger-gebaeudereinigung24.de</a></p>
<p style="margin:0 0 15px 0;font-family:Calibri,Arial,sans-serif;font-size:8pt;color:#666666;line-height:1.3;">Legal entity: North Cleaning Services Hamburg - Registered Office: Hamburg - Commercial Register: Amtsgericht Hamburg HRA 116971 - Managing Director: Elias Malyar This E-Mail may contain confidential and/or privileged information. If you are not the intended recipient please notify the sender immediately and destroy this E-Mail. Any unauthorized copying, disclosure or distribution is strictly forbidden.</p>
<!-- CERTIFICATIONS -->
<table border="0" cellpadding="0" cellspacing="0" role="presentation" style="margin:15px 0 5px 0;">
<tbody><tr>
<td style="padding:0 5px 0 0;"><img alt="ISO 9001" height="70" src="https://sendy.north-cleaning.de/uploads/signature/iso-9001.jpg" style="display:block;width:40px;height:70px;" width="40" /></td>
<td style="padding:0 5px 0 0;"><img alt="ISO 14001" height="70" src="https://sendy.north-cleaning.de/uploads/signature/iso-14001.jpg" style="display:block;width:40px;height:70px;" width="40" /></td>
<td style="padding:0 5px 0 0;"><img alt="ISO 45001" height="70" src="https://sendy.north-cleaning.de/uploads/signature/iso-45001.jpg" style="display:block;width:40px;height:70px;" width="40" /></td>
<td style="padding:0 5px 0 0;"><img alt="PQ VOB" height="70" src="https://sendy.north-cleaning.de/uploads/signature/pq-vob.jpg" style="display:block;width:160px;height:70px;" width="60" /></td>
<td style="padding:0 5px 0 0;"><img alt="Die Gebäudedienstleister" height="60" src="https://sendy.north-cleaning.de/uploads/signature/landesinnung-new.jpg" style="display:block;width:110px;height:60px;" width="60" /></td>
<td style="padding:0;"><img alt="Handelskammer Hamburg" height="60" src="https://sendy.north-cleaning.de/uploads/signature/handelskammer.jpg" style="display:block;width:110px;height:60px;" width="60" /></td>
</tr></tbody>
</table>
<p style="margin:15px 0 0 0;font-family:Calibri,Arial,sans-serif;font-size:9pt;color:#2e7d32;">Bitte denken Sie an die Umwelt... bevor Sie diese E-Mail ausdrucken.</p>
</td></tr></tbody>
</table>
</td></tr>
"""

HTML_FOOTER = """\
<!-- DSGVO UNSUBSCRIBE FOOTER -->
<tr>
<td style="padding:30px 0 20px 0;border-top:1px solid #e1e1e1;">
<table border="0" cellpadding="0" cellspacing="0" role="presentation" width="100%">
<tbody><tr>
<td align="center" style="font-family:Calibri,Arial,sans-serif;font-size:9pt;color:#888888;line-height:1.4;">
<p style="margin:0 0 5px 0;">Diese E-Mail wurde Ihnen auf Basis eines berechtigten Interesses gem&auml;&szlig; Art.&nbsp;6 Abs.&nbsp;1 lit.&nbsp;f DSGVO zugesandt (B2B-Gesch&auml;ftsinteresse).</p>
<p style="margin:0;"><a href="{{ unsubscribe_url }}" style="color:#666666;text-decoration:underline;">Abmelden</a> | <a href="https://www.north-cleaning.de/datenschutz" style="color:#666666;text-decoration:underline;">Datenschutzerkl&auml;rung</a></p>
</td>
</tr></tbody>
</table>
</td>
</tr>
"""

HTML_WRAPPER_END = """\
</tbody>
</table>
</td></tr></tbody>
</table>
</body>
</html>
"""


def make_email_html(content_html: str) -> str:
    return (
        HTML_WRAPPER_START
        + content_html
        + HTML_SIGNATURE
        + HTML_FOOTER
        + HTML_WRAPPER_END
    )


# ---------------------------------------------------------------------------
# Step 1 — Initial outreach (same content as the sendy template)
# ---------------------------------------------------------------------------
STEP1_CONTENT = """\
<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">Sehr geehrte Damen und Herren,</p>

<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">ich kontaktiere Sie im Rahmen der Optimierung wiederkehrender Kosten im Bereich Reinigung und Facility Management &ndash; mit Fokus auf operative Effizienz, Standardisierung und Kostenkontrolle bei <strong>{{ business_name }}</strong>.</p>

<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;"><strong>Die Herausforderung</strong></p>

<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">In {{ industry_text }}en wie dem Ihren ist die Reinigung in der Regel der gr&ouml;&szlig;te wiederkehrende Kostenfaktor im Bereich der Supportleistungen. Wenn die Reinigung vorwiegend operativ gesteuert wird, entstehen schnell:</p>

<ul style="margin:0 0 12pt 0;padding-left:20pt;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">
<li style="margin-bottom:6pt;">Qualit&auml;tsschwankungen zwischen Standorten / Teams</li>
<li style="margin-bottom:6pt;">Kosten, die mit der Zeit steigen, ohne klare Begr&uuml;ndung</li>
<li style="margin-bottom:6pt;">Fehlende Korrelation zwischen Kosten &ndash; Frequenz &ndash; Ergebnis</li>
</ul>

<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;"><strong>Unser Ansatz</strong></p>

<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">Wir sind ein Reinigungsunternehmen mit &uuml;ber 15 Jahren Erfahrung in Deutschland. Im Jahr 2026 haben wir das klassische Ausf&uuml;hrungsmodell um Robotisierung + strategisches Service-Management erweitert, um die Vorhersehbarkeit zu erh&ouml;hen, Verluste zu reduzieren und die Leistungserbringung zu standardisieren.</p>

<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;"><strong>Wir positionieren uns als operativer Partner</strong></p>

<ul style="margin:0 0 12pt 0;padding-left:20pt;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">
<li style="margin-bottom:6pt;">Standardisierte und leicht auditierbare Prozesse</li>
<li style="margin-bottom:6pt;">Monatliche Berichte und Transparenz (Aktivit&auml;ten, Frequenzen, Ergebnisse)</li>
<li style="margin-bottom:6pt;">Klare Leistungskennzahlen (SLA / KPI)</li>
<li style="margin-bottom:6pt;">Kostenkontrolle und Reduzierung der Lieferantenfragmentierung</li>
</ul>

<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">Falls Sie es f&uuml;r relevant halten, schlage ich ein unverbindliches Sondierungsgespr&auml;ch vor &ndash; um zu bewerten, ob unser Ansatz den Anforderungen Ihrer Organisation in {{ city }} entspricht.</p>
"""

# ---------------------------------------------------------------------------
# Step 2 — Follow-up after 3 days
# ---------------------------------------------------------------------------
STEP2_CONTENT = """\
<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">Sehr geehrte Damen und Herren,</p>

<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">vor einigen Tagen habe ich Ihnen eine E-Mail &uuml;ber unseren Ansatz zur Optimierung der Geb&auml;udereinigung f&uuml;r <strong>{{ business_name }}</strong> gesendet.</p>

<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">Ich wollte kurz nachfragen, ob Sie die M&ouml;glichkeit hatten, diese zu lesen &ndash; und ob das Thema f&uuml;r Sie aktuell relevant ist.</p>

<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">Kurz zusammengefasst: Wir helfen {{ industry_text }}en in {{ city }}, ihre Reinigungskosten transparenter, planbarer und effizienter zu gestalten &ndash; durch standardisierte Prozesse, klare KPIs und optional durch den Einsatz von Reinigungsrobotik.</p>

<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">W&auml;re ein kurzes 20-min&uuml;tiges Gespr&auml;ch m&ouml;glich, um zu pr&uuml;fen, ob unser Modell f&uuml;r Sie passt?</p>
"""

# ---------------------------------------------------------------------------
# Step 3 — Final follow-up after 7 more days
# ---------------------------------------------------------------------------
STEP3_CONTENT = """\
<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">Sehr geehrte Damen und Herren,</p>

<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">dies ist meine letzte Nachricht in dieser Sache &ndash; ich m&ouml;chte Ihnen keine unn&ouml;tigen E-Mails schicken.</p>

<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">Ich habe mich in den vergangenen Wochen zweimal an <strong>{{ business_name }}</strong> in {{ city }} gewandt, um einen unverbindlichen Austausch &uuml;ber die M&ouml;glichkeiten zur Optimierung Ihrer Geb&auml;udereinigung vorzuschlagen.</p>

<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">Falls das Thema derzeit nicht aktuell ist, verstehe ich das selbstverst&auml;ndlich vollkommen. Sollte sich in Zukunft Bedarf ergeben, freue ich mich, wenn Sie auf mich zukommen.</p>

<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">D&uuml;rfen wir Ihnen trotzdem ein unverbindliches Angebot &uuml;bermitteln? Ein einfaches &bdquo;Ja&ldquo; gen&uuml;gt &ndash; den Rest erledigen wir.</p>

<p style="margin:0 0 12pt 0;font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;">Vielen Dank f&uuml;r Ihre Zeit und Aufmerksamkeit.</p>
"""


class Command(BaseCommand):
    help = "Seed the database with a demo campaign and 3 German email sequence steps."

    def add_arguments(self, parser):
        parser.add_argument(
            "--lead-list-name",
            default="Hamburg B2B — Demo",
            help="Name of the LeadList to create/use for the demo campaign.",
        )
        parser.add_argument(
            "--campaign-name",
            default="Hamburg Outreach 2026",
            help="Name of the demo campaign.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Delete existing steps for the campaign before seeding.",
        )

    def handle(self, *args, **options):
        lead_list, created = LeadList.objects.get_or_create(
            name=options["lead_list_name"],
            defaults={"description": "Hamburg B2B leads — Hausverwaltung, Immobilien, Facility Management"},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created LeadList: {lead_list.name}"))

        campaign, created = Campaign.objects.get_or_create(
            name=options["campaign_name"],
            defaults={
                "lead_list": lead_list,
                "from_name": "Sebastian Cucuiet | North Cleaning Services GmbH",
                "reply_to_email": "service@north-cleaning.de",
                "daily_send_limit": 50,
                "sending_days": [0, 1, 2, 3, 4],
                "status": "draft",
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created Campaign: {campaign.name}"))
        else:
            self.stdout.write(f"Using existing Campaign: {campaign.name}")

        if options["overwrite"]:
            campaign.steps.all().delete()
            self.stdout.write("Deleted existing steps.")

        steps = [
            {
                "step_number": 1,
                "subject_template": "Geb\u00e4udereinigung f\u00fcr {{ business_name }} \u2014 Optimierungspotenzial und neue Ans\u00e4tze",
                "body_template": make_email_html(STEP1_CONTENT),
                "delay_days": 0,
            },
            {
                "step_number": 2,
                "subject_template": "Kurze R\u00fcckfrage: Reinigungsangebot f\u00fcr {{ business_name }}",
                "body_template": make_email_html(STEP2_CONTENT),
                "delay_days": 3,
            },
            {
                "step_number": 3,
                "subject_template": "Letzte Frage: D\u00fcrfen wir Ihnen ein Angebot unterbreiten?",
                "body_template": make_email_html(STEP3_CONTENT),
                "delay_days": 7,
            },
        ]

        created_count = 0
        for step_data in steps:
            obj, created = SequenceStep.objects.get_or_create(
                campaign=campaign,
                step_number=step_data["step_number"],
                defaults={
                    "subject_template": step_data["subject_template"],
                    "body_template": step_data["body_template"],
                    "delay_days": step_data["delay_days"],
                    "send_only_if_no_reply": True,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  Created Step {step_data['step_number']}: {step_data['subject_template'][:60]}"))
            else:
                self.stdout.write(f"  Step {step_data['step_number']} already exists (use --overwrite to replace).")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Campaign '{campaign.name}' has {campaign.steps.count()} step(s). "
            f"Go to /admin/ or /campaigns/ to activate it."
        ))
