#!/usr/bin/env python3
"""
Email Validator — Validare multiplă prin Sintaxă, DNS, SMTP și Disposable Check.
Procesare asincronă pentru verificări paralele rapide.
Citește CSV-ul generat de apollo_scraper.py și produce un raport de validare.
"""

import argparse
import asyncio
import csv
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiodns
import aiosmtplib
from dotenv import load_dotenv
from email_validator import EmailNotValidError, validate_email
from tqdm import tqdm

# ── Configurare ──────────────────────────────────────────────────────────────

load_dotenv()

SMTP_TIMEOUT: int = int(os.getenv("SMTP_TIMEOUT", "10"))
BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "20"))
SKIP_DISPOSABLE: bool = os.getenv("SKIP_DISPOSABLE", "false").lower() == "true"

# ── Logging ──────────────────────────────────────────────────────────────────

def setup_logging(log_file: str = "email_validation.log") -> logging.Logger:
    """Configurează logging dual: consolă + fișier."""
    logger = logging.getLogger("email_validator")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


log = setup_logging()

# ── Disposable Email Domains ─────────────────────────────────────────────────

DISPOSABLE_DOMAINS: set[str] = {
    "10minutemail.com", "tempmail.com", "throwaway.email", "guerrillamail.com",
    "guerrillamail.net", "sharklasers.com", "grr.la", "guerrillamailblock.com",
    "mailinator.com", "maildrop.cc", "dispostable.com", "yopmail.com",
    "yopmail.fr", "temp-mail.org", "fakeinbox.com", "trashmail.com",
    "trashmail.me", "trashmail.net", "mailnesia.com", "mailcatch.com",
    "getnada.com", "tempail.com", "tempr.email", "discard.email",
    "mohmal.com", "burnermail.io", "inboxkitten.com", "harakirimail.com",
    "33mail.com", "mailsac.com", "mytemp.email", "20minutemail.com",
    "anonaddy.me", "emailondeck.com", "crazymailing.com", "tmail.ws",
    "tmpmail.net", "tmpmail.org", "moakt.co", "emailfake.com",
    "generator.email", "guerrillamail.de", "grr.la", "safetymail.info",
}

# ── Validare funcții ─────────────────────────────────────────────────────────

def validate_syntax(email: str) -> tuple[bool, str]:
    """Validează sintaxa emailului folosind regex + email-validator."""
    if not email or not isinstance(email, str):
        return False, "Email gol sau invalid"

    # Regex de bază
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email.strip()):
        return False, "Format invalid (regex)"

    try:
        validate_email(email.strip(), check_deliverability=False)
        return True, "OK"
    except EmailNotValidError as exc:
        return False, str(exc)


def check_disposable(domain: str) -> bool:
    """Verifică dacă domeniul e un serviciu de email temporar."""
    return domain.lower() in DISPOSABLE_DOMAINS


async def check_dns_mx(domain: str) -> tuple[bool, list[str]]:
    """Verifică existența MX records pentru domeniu (async)."""
    resolver = aiodns.DNSResolver()
    try:
        mx_records = await resolver.query(domain, "MX")
        hosts = sorted(mx_records, key=lambda r: r.priority)
        return True, [r.host for r in hosts]
    except aiodns.error.DNSError:
        # Fallback: verifică A record
        try:
            await resolver.query(domain, "A")
            return True, [domain]
        except aiodns.error.DNSError:
            return False, []


async def check_smtp(email: str, mx_hosts: list[str], timeout: int = SMTP_TIMEOUT) -> tuple[str, str]:
    """
    Verificare SMTP soft — se conectează la MX și verifică mailbox-ul
    fără a trimite email (RCPT TO).
    Returnează (status, smtp_response).
    """
    if not mx_hosts:
        return "UNKNOWN", "Fără MX hosts"

    for mx_host in mx_hosts[:3]:  # Încearcă primele 3 MX records
        try:
            smtp = aiosmtplib.SMTP(hostname=mx_host, port=25, timeout=timeout)
            await smtp.connect()

            # EHLO/HELO
            code, msg = await smtp.ehlo()
            if code >= 400:
                await smtp.quit()
                continue

            # MAIL FROM cu adresă neutră
            code, msg = await smtp.execute_command(b"MAIL FROM:<verify@example.com>")
            if code >= 400:
                await smtp.quit()
                return "RISKY", f"MAIL FROM respins: {code} {msg}"

            # RCPT TO — verificarea propriu-zisă
            code, msg = await smtp.execute_command(f"RCPT TO:<{email}>".encode())

            try:
                # RSET și QUIT curățenie
                await smtp.execute_command(b"RSET")
                await smtp.quit()
            except Exception:
                pass

            if code == 250:
                return "VALID", f"SMTP OK: {code}"
            elif code == 550:
                return "INVALID", f"Mailbox inexistent: {code} {msg}"
            elif code in (450, 451, 452):
                return "RISKY", f"Temporar indisponibil: {code} {msg}"
            else:
                return "RISKY", f"Răspuns necunoscut: {code} {msg}"

        except asyncio.TimeoutError:
            continue
        except aiosmtplib.SMTPException as exc:
            log.debug("SMTP error pentru %s via %s: %s", email, mx_host, exc)
            continue
        except OSError as exc:
            log.debug("Conexiune eșuată la %s: %s", mx_host, exc)
            continue

    return "UNKNOWN", "Toate MX hosts indisponibile"


async def validate_single_email(email: str) -> dict:
    """Pipeline complet de validare pentru un singur email."""
    result = {
        "email": email,
        "status_validare": "UNKNOWN",
        "motiv_invalidare": "",
        "mx_records_found": "",
        "smtp_response": "",
        "timestamp_verificare": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 1. Validare sintaxă
    syntax_ok, syntax_msg = validate_syntax(email)
    if not syntax_ok:
        result["status_validare"] = "INVALID"
        result["motiv_invalidare"] = f"Sintaxă: {syntax_msg}"
        return result

    domain = email.split("@")[1].lower()

    # 2. Check disposable
    if not SKIP_DISPOSABLE and check_disposable(domain):
        result["status_validare"] = "DISPOSABLE"
        result["motiv_invalidare"] = "Domeniu de email temporar/disposable"
        return result

    # 3. Validare DNS/MX
    mx_ok, mx_hosts = await check_dns_mx(domain)
    result["mx_records_found"] = ", ".join(mx_hosts[:5]) if mx_hosts else "NONE"

    if not mx_ok:
        result["status_validare"] = "INVALID"
        result["motiv_invalidare"] = "Fără MX sau A records — domeniu inexistent"
        return result

    # 4. Verificare SMTP
    smtp_status, smtp_response = await check_smtp(email, mx_hosts)
    result["status_validare"] = smtp_status
    result["smtp_response"] = smtp_response
    if smtp_status != "VALID":
        result["motiv_invalidare"] = smtp_response

    return result

# ── Procesare batch asincronă ────────────────────────────────────────────────

async def validate_batch(emails: list[str]) -> list[dict]:
    """Validează un batch de emailuri în paralel."""
    tasks = [validate_single_email(email) for email in emails]
    return await asyncio.gather(*tasks)

# ── I/O funcții ──────────────────────────────────────────────────────────────

def load_input_csv(input_path: str) -> list[dict]:
    """Citește CSV-ul de input și returnează lista de rânduri."""
    path = Path(input_path)
    if not path.exists():
        log.error("Fișierul nu există: %s", input_path)
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    log.info("Încărcate %d rânduri din %s", len(rows), input_path)
    return rows


def write_output(
    results: list[dict],
    original_rows: list[dict],
    output_path: str,
    failed_path: str,
) -> None:
    """Scrie raportul de validare în CSV-uri (complet + failed)."""
    # Combinăm datele originale cu rezultatele validării
    email_to_result = {r["email"]: r for r in results}

    validation_fields = ["status_validare", "motiv_invalidare", "mx_records_found", "smtp_response", "timestamp_verificare"]

    if original_rows:
        original_fields = list(original_rows[0].keys())
    else:
        original_fields = ["email"]

    all_fields = original_fields + [f for f in validation_fields if f not in original_fields]

    combined = []
    failed = []

    for row in original_rows:
        email = row.get("email", "").strip()
        vr = email_to_result.get(email, {})
        merged = {**row, **vr}
        combined.append(merged)

        if merged.get("status_validare") in ("INVALID", "DISPOSABLE"):
            failed.append(merged)

    # Scrie raport complet
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(combined)

    # Scrie emailuri invalide separat
    with open(failed_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(failed)

    log.info("Raport complet: %s (%d rânduri)", output_path, len(combined))
    log.info("Emailuri invalide: %s (%d rânduri)", failed_path, len(failed))

# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validare emailuri prin Sintaxă, DNS, SMTP și Disposable Check",
    )
    parser.add_argument("input", help="Fișier CSV cu emailuri (coloana 'email' obligatorie)")
    parser.add_argument("-o", "--output", default="validated_emails.csv", help="Fișier CSV output (default: validated_emails.csv)")
    parser.add_argument("--failed", default="failed_emails.csv", help="Fișier CSV cu emailuri invalide (default: failed_emails.csv)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help=f"Emailuri procesate simultan (default: {BATCH_SIZE})")
    parser.add_argument("--timeout", type=int, default=SMTP_TIMEOUT, help=f"Timeout SMTP în secunde (default: {SMTP_TIMEOUT})")
    parser.add_argument("--skip-disposable", action="store_true", help="Sari peste verificarea de disposable emails")
    args = parser.parse_args()

    # Suprascrie globals din argumente
    global SMTP_TIMEOUT, BATCH_SIZE, SKIP_DISPOSABLE
    SMTP_TIMEOUT = args.timeout
    BATCH_SIZE = args.batch_size
    if args.skip_disposable:
        SKIP_DISPOSABLE = True

    log.info("═" * 60)
    log.info("Email Validator — Start")
    log.info("Input: %s | Output: %s", args.input, args.output)
    log.info("Batch size: %d | SMTP timeout: %ds", BATCH_SIZE, SMTP_TIMEOUT)
    log.info("Skip disposable: %s", SKIP_DISPOSABLE)
    log.info("═" * 60)

    rows = load_input_csv(args.input)
    emails = [row.get("email", "").strip() for row in rows if row.get("email", "").strip()]

    if not emails:
        log.error("Niciun email găsit în fișierul de input.")
        sys.exit(1)

    # Deduplică
    unique_emails = list(dict.fromkeys(emails))
    log.info("Total emailuri unice: %d (din %d rânduri)", len(unique_emails), len(rows))

    all_results: list[dict] = []
    stats = {"VALID": 0, "INVALID": 0, "RISKY": 0, "DISPOSABLE": 0, "UNKNOWN": 0}

    pbar = tqdm(total=len(unique_emails), desc="Validare", unit="email")

    # Procesare pe batch-uri
    for i in range(0, len(unique_emails), BATCH_SIZE):
        batch = unique_emails[i : i + BATCH_SIZE]

        try:
            batch_results = asyncio.run(validate_batch(batch))
        except KeyboardInterrupt:
            log.info("Întrerupt de utilizator.")
            pbar.close()
            break

        all_results.extend(batch_results)

        for r in batch_results:
            status = r.get("status_validare", "UNKNOWN")
            stats[status] = stats.get(status, 0) + 1

        pbar.update(len(batch))
        pbar.set_postfix(
            valid=stats["VALID"],
            invalid=stats["INVALID"],
            risky=stats["RISKY"],
            disp=stats["DISPOSABLE"],
        )

    pbar.close()

    # Scrie rezultatele
    write_output(all_results, rows, args.output, args.failed)

    # Raport final
    total = sum(stats.values())
    log.info("═" * 60)
    log.info("FINALIZAT — Raport validare")
    log.info("Total procesate: %d", total)
    log.info("  VALID:      %d (%.1f%%)", stats["VALID"], stats["VALID"] / max(total, 1) * 100)
    log.info("  INVALID:    %d (%.1f%%)", stats["INVALID"], stats["INVALID"] / max(total, 1) * 100)
    log.info("  RISKY:      %d (%.1f%%)", stats["RISKY"], stats["RISKY"] / max(total, 1) * 100)
    log.info("  DISPOSABLE: %d (%.1f%%)", stats["DISPOSABLE"], stats["DISPOSABLE"] / max(total, 1) * 100)
    log.info("  UNKNOWN:    %d (%.1f%%)", stats["UNKNOWN"], stats["UNKNOWN"] / max(total, 1) * 100)
    log.info("═" * 60)


if __name__ == "__main__":
    main()
