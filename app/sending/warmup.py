import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


def advance_warmup(smtp_account) -> None:
    """
    Called daily to advance warmup counter.
    Warmup schedule:
      Day 1-3:  5/day
      Day 4-7:  10/day
      Day 8-14: 25/day
      Day 15+:  full limit (warmup_mode = False)
    """
    if not smtp_account.warmup_mode:
        return

    today = timezone.localdate()
    if smtp_account.warmup_start_date is None:
        smtp_account.warmup_start_date = today
        smtp_account.warmup_day = 1
    else:
        smtp_account.warmup_day += 1

    if smtp_account.warmup_day > 14:
        smtp_account.warmup_mode = False
        logger.info(f"[Warmup] {smtp_account.email_address} completed warmup — now at full limit")
    else:
        limit = smtp_account.effective_daily_limit
        logger.info(f"[Warmup] {smtp_account.email_address} day {smtp_account.warmup_day} — limit: {limit}/day")

    smtp_account.save(update_fields=["warmup_mode", "warmup_day", "warmup_start_date"])


def get_warmup_status(smtp_account) -> dict:
    """Return a dict describing current warmup status."""
    if not smtp_account.warmup_mode:
        return {"active": False, "day": smtp_account.warmup_day, "limit": smtp_account.daily_limit}
    return {
        "active": True,
        "day": smtp_account.warmup_day,
        "limit": smtp_account.effective_daily_limit,
        "phase": _warmup_phase(smtp_account.warmup_day),
    }


def _warmup_phase(day: int) -> str:
    if day <= 3:
        return "Phase 1 (5/day)"
    elif day <= 7:
        return "Phase 2 (10/day)"
    elif day <= 14:
        return "Phase 3 (25/day)"
    return "Completed"
