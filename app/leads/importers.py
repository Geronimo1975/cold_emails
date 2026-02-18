import csv
import io
import logging
from typing import Optional
from .models import Lead, LeadList

logger = logging.getLogger(__name__)


def import_leads_from_csv(content: str, lead_list: Optional[LeadList] = None, source: str = "csv_import") -> dict:
    """
    Import leads from CSV string.
    Expected columns: business_name, email, phone, website, city, postal_code, industry, contact_person
    Returns: {"created": int, "skipped": int, "rejected": int, "errors": list}
    """
    result = {"created": 0, "skipped": 0, "rejected": 0, "errors": []}
    reader = csv.DictReader(io.StringIO(content))

    for row_num, row in enumerate(reader, start=2):
        email = (row.get("email") or row.get("Email") or "").strip().lower()
        business_name = (row.get("business_name") or row.get("Business Name") or row.get("name") or "").strip()

        if not email or not business_name:
            result["skipped"] += 1
            continue

        # DSGVO filter: reject personal emails
        if not Lead.is_generic_b2b_email(email):
            logger.info(f"[Import] Rejected personal email: {email}")
            result["rejected"] += 1
            continue

        # Check duplicate
        if Lead.objects.filter(email=email).exists():
            result["skipped"] += 1
            continue

        industry = _normalize_industry(row.get("industry") or row.get("Industry") or "")

        try:
            Lead.objects.create(
                business_name=business_name,
                email=email,
                phone=(row.get("phone") or row.get("Phone") or "").strip(),
                website=(row.get("website") or row.get("Website") or "").strip(),
                address=(row.get("address") or row.get("Address") or "").strip(),
                city=(row.get("city") or row.get("City") or "Hamburg").strip(),
                postal_code=(row.get("postal_code") or row.get("Postal Code") or "").strip(),
                contact_person=(row.get("contact_person") or row.get("Contact") or "").strip(),
                position=(row.get("position") or row.get("Position") or "").strip(),
                industry=industry,
                source=source,
                lead_list=lead_list,
            )
            result["created"] += 1
        except Exception as e:
            result["errors"].append(f"Row {row_num}: {e}")
            logger.error(f"[Import] Row {row_num} error: {e}")

    return result


def import_leads_from_dataforseo(data: list, lead_list: Optional[LeadList] = None) -> dict:
    """
    Import leads from DataforSEO API response format.
    Expects list of dicts with keys: title, email, phone, address, city, etc.
    """
    result = {"created": 0, "skipped": 0, "rejected": 0, "errors": []}

    for item in data:
        email = (item.get("email") or "").strip().lower()
        business_name = (item.get("title") or item.get("business_name") or "").strip()

        if not email or not business_name:
            result["skipped"] += 1
            continue

        if not Lead.is_generic_b2b_email(email):
            result["rejected"] += 1
            continue

        if Lead.objects.filter(email=email).exists():
            result["skipped"] += 1
            continue

        city = item.get("city") or item.get("address_city") or "Hamburg"
        industry = _detect_industry_from_categories(item.get("categories", []))

        try:
            Lead.objects.create(
                business_name=business_name,
                email=email,
                phone=item.get("phone", ""),
                website=item.get("url", ""),
                address=item.get("address", ""),
                city=city,
                postal_code=item.get("zip", ""),
                industry=industry,
                source="dataforseo",
                lead_list=lead_list,
                extra_data=item,
            )
            result["created"] += 1
        except Exception as e:
            result["errors"].append(str(e))

    return result


def _normalize_industry(raw: str) -> str:
    raw = raw.lower().strip()
    if any(x in raw for x in ["hausverwaltung", "haus verwaltung", "verwaltung"]):
        return "hausverwaltung"
    if any(x in raw for x in ["immobil", "real estate"]):
        return "immobilien"
    if any(x in raw for x in ["facility", "gebäude"]):
        return "facility_management"
    if any(x in raw for x in ["gewerbe", "office", "büro"]):
        return "gewerbe"
    return "other"


def _detect_industry_from_categories(categories: list) -> str:
    joined = " ".join(categories).lower()
    return _normalize_industry(joined)
