#!/usr/bin/env python3
"""
Apollo.io Email Scraper
Extrage emailuri din profile LinkedIn și website-uri folosind API-ul Apollo.io.
Salvează rezultatele în CSV cu checkpoint recovery pentru procesări lungi.
"""

import argparse
import csv
import json
import logging
import os
import pickle
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from tqdm import tqdm

# ── Configurare ──────────────────────────────────────────────────────────────

load_dotenv()

APOLLO_API_KEY: str = os.getenv("APOLLO_API_KEY", "")
APOLLO_BASE_URL: str = "https://api.apollo.io/v1"
RATE_LIMIT_REQUESTS: int = int(os.getenv("APOLLO_RATE_LIMIT", "5"))  # req/sec
CHECKPOINT_FILE: str = "scraper_checkpoint.pkl"

OUTPUT_COLUMNS: list[str] = [
    "email", "nume", "companie", "pozitie", "sursa", "linkedin_url",
    "website", "telefon", "oras", "tara", "data_extragere",
]

# ── Logging ──────────────────────────────────────────────────────────────────

def setup_logging(log_file: str = "apollo_scraping.log") -> logging.Logger:
    """Configurează logging dual: consolă + fișier."""
    logger = logging.getLogger("apollo_scraper")
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

# ── Rate Limiting & Retry ────────────────────────────────────────────────────

class RateLimiter:
    """Limitează requesturile la un anumit număr pe secundă."""

    def __init__(self, max_per_second: int = RATE_LIMIT_REQUESTS) -> None:
        self.min_interval = 1.0 / max_per_second
        self.last_call = 0.0

    def wait(self) -> None:
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()


rate_limiter = RateLimiter()


def api_request(
    method: str,
    endpoint: str,
    payload: Optional[dict] = None,
    max_retries: int = 5,
) -> dict:
    """
    Execută un request la API-ul Apollo.io cu exponential backoff.
    Returnează JSON-ul sau dict gol în caz de eșec permanent.
    """
    url = f"{APOLLO_BASE_URL}/{endpoint.lstrip('/')}"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": APOLLO_API_KEY,
    }

    for attempt in range(1, max_retries + 1):
        rate_limiter.wait()
        try:
            if method.upper() == "GET":
                resp = requests.get(
                    url, headers=headers, params=payload or {}, timeout=30,
                )
            else:
                resp = requests.post(
                    url, headers=headers, json=payload or {}, timeout=30,
                )

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code == 429:
                wait = 2 ** attempt
                log.warning("Rate limit atins. Aștept %ds (tentativa %d/%d)", wait, attempt, max_retries)
                time.sleep(wait)
                continue

            if resp.status_code >= 500:
                wait = 2 ** attempt
                log.warning("Server error %d. Retry în %ds (tentativa %d/%d)", resp.status_code, wait, attempt, max_retries)
                time.sleep(wait)
                continue

            log.error("Request eșuat: %d — %s", resp.status_code, resp.text[:300])
            return {}

        except requests.RequestException as exc:
            wait = 2 ** attempt
            log.warning("Eroare conexiune: %s. Retry în %ds (%d/%d)", exc, wait, attempt, max_retries)
            time.sleep(wait)

    log.error("Toate tentativele eșuate pentru %s", endpoint)
    return {}

# ── Checkpoint Recovery ──────────────────────────────────────────────────────

def save_checkpoint(processed_indices: set, output_file: str) -> None:
    """Salvează progresul curent pe disc."""
    with open(CHECKPOINT_FILE, "wb") as f:
        pickle.dump({"processed": processed_indices, "output": output_file}, f)


def load_checkpoint() -> tuple[set, str | None]:
    """Încarcă checkpoint-ul anterior dacă există."""
    if not Path(CHECKPOINT_FILE).exists():
        return set(), None
    try:
        with open(CHECKPOINT_FILE, "rb") as f:
            data = pickle.load(f)
        log.info("Checkpoint încărcat: %d intrări deja procesate", len(data["processed"]))
        return data["processed"], data["output"]
    except Exception:
        return set(), None


def clear_checkpoint() -> None:
    """Șterge fișierul checkpoint după finalizare."""
    Path(CHECKPOINT_FILE).unlink(missing_ok=True)

# ── Extragere funcții ────────────────────────────────────────────────────────

def extract_person_data(person: dict, source: str) -> dict:
    """Extrage câmpurile relevante din răspunsul Apollo pentru o persoană."""
    org = person.get("organization") or {}
    return {
        "email": person.get("email", ""),
        "nume": f'{person.get("first_name", "")} {person.get("last_name", "")}'.strip(),
        "companie": org.get("name") or person.get("organization_name", ""),
        "pozitie": person.get("title", ""),
        "sursa": source,
        "linkedin_url": person.get("linkedin_url", ""),
        "website": org.get("website_url", ""),
        "telefon": (person.get("phone_numbers") or [{}])[0].get("sanitized_number", "") if person.get("phone_numbers") else "",
        "oras": person.get("city", ""),
        "tara": person.get("country", ""),
        "data_extragere": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def search_person_by_linkedin(linkedin_url: str) -> list[dict]:
    """Caută o persoană pe Apollo.io după URL-ul LinkedIn."""
    log.debug("Caut persoană: %s", linkedin_url)

    # Enrichment endpoint — cel mai precis pentru LinkedIn URLs
    data = api_request("POST", "people/match", {"linkedin_url": linkedin_url, "reveal_personal_emails": True})

    if data and data.get("person"):
        person = data["person"]
        if person.get("email"):
            return [extract_person_data(person, "LinkedIn")]
        log.info("Persoană găsită fără email: %s", linkedin_url)
    return []


def search_company_employees(linkedin_company_url: str, limit: int = 50) -> list[dict]:
    """Caută angajații unei companii pornind de la pagina LinkedIn a companiei."""
    log.debug("Caut angajați companie: %s", linkedin_company_url)

    # Găsim organizația
    org_data = api_request("GET", "organizations/enrich", {"domain": "", "linkedin_url": linkedin_company_url})
    org = org_data.get("organization")
    if not org:
        log.warning("Companie negăsită: %s", linkedin_company_url)
        return []

    org_id = org.get("id")
    log.info("Companie găsită: %s (id=%s)", org.get("name"), org_id)

    # Căutăm angajați
    results = []
    page = 1
    while len(results) < limit:
        data = api_request("POST", "mixed_people/search", {
            "organization_ids": [org_id],
            "page": page,
            "per_page": min(25, limit - len(results)),
        })
        people = data.get("people", [])
        if not people:
            break

        for person in people:
            if person.get("email"):
                results.append(extract_person_data(person, "LinkedIn-Company"))

        page += 1
        if page > data.get("pagination", {}).get("total_pages", 1):
            break

    log.info("Găsite %d emailuri pentru companie: %s", len(results), org.get("name"))
    return results


def search_by_domain(domain: str) -> list[dict]:
    """Caută persoane asociate cu un domeniu web."""
    log.debug("Caut persoane pentru domeniu: %s", domain)

    results = []
    page = 1
    while True:
        data = api_request("POST", "mixed_people/search", {
            "q_organization_domains": domain,
            "page": page,
            "per_page": 25,
        })
        people = data.get("people", [])
        if not people:
            break

        for person in people:
            if person.get("email"):
                results.append(extract_person_data(person, f"Website:{domain}"))

        page += 1
        if page > data.get("pagination", {}).get("total_pages", 1) or page > 10:
            break

    log.info("Găsite %d emailuri pentru domeniu: %s", len(results), domain)
    return results

# ── Clasificare URL ──────────────────────────────────────────────────────────

def classify_url(url: str) -> str:
    """Clasifică un URL ca LinkedIn profile, LinkedIn company sau website."""
    url_lower = url.lower()
    if "linkedin.com/in/" in url_lower:
        return "linkedin_person"
    if "linkedin.com/company/" in url_lower:
        return "linkedin_company"
    return "website"


def extract_domain(url: str) -> str:
    """Extrage domeniul dintr-un URL."""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    domain = parsed.netloc or parsed.path.split("/")[0]
    return domain.removeprefix("www.")

# ── Procesare input ──────────────────────────────────────────────────────────

def load_input(input_path: str) -> list[dict]:
    """
    Încarcă datele de input din CSV sau JSON.
    Formatul așteptat: fiecare rând/obiect trebuie să aibă cel puțin un câmp 'url'.
    """
    path = Path(input_path)
    if not path.exists():
        log.error("Fișierul input nu există: %s", input_path)
        sys.exit(1)

    if path.suffix.lower() == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else [data]

    # CSV
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def process_entry(entry: dict) -> list[dict]:
    """Procesează o intrare din input (un URL) și returnează emailurile găsite."""
    url = entry.get("url", "").strip()
    if not url:
        log.warning("Intrare fără URL, skip: %s", entry)
        return []

    url_type = classify_url(url)

    if url_type == "linkedin_person":
        return search_person_by_linkedin(url)
    elif url_type == "linkedin_company":
        limit = int(entry.get("limit", 50))
        return search_company_employees(url, limit=limit)
    else:
        domain = extract_domain(url)
        return search_by_domain(domain)

# ── Scriere rezultate ────────────────────────────────────────────────────────

def write_results(results: list[dict], output_path: str, mode: str = "a") -> None:
    """Scrie rezultatele în fișierul CSV (append sau overwrite)."""
    file_exists = Path(output_path).exists() and mode == "a"
    with open(output_path, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        if not file_exists or mode == "w":
            writer.writeheader()
        writer.writerows(results)

# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extrage emailuri din LinkedIn și website-uri folosind Apollo.io",
    )
    parser.add_argument("input", help="Fișier CSV sau JSON cu URL-urile de procesat")
    parser.add_argument("-o", "--output", default="apollo_results.csv", help="Fișier CSV output (default: apollo_results.csv)")
    parser.add_argument("--resume", action="store_true", help="Reia de la ultimul checkpoint")
    parser.add_argument("--company-limit", type=int, default=50, help="Nr. max angajați de extras per companie (default: 50)")
    args = parser.parse_args()

    if not APOLLO_API_KEY:
        log.error("APOLLO_API_KEY lipsește. Setează-l în .env sau ca variabilă de environment.")
        sys.exit(1)

    log.info("═" * 60)
    log.info("Apollo.io Email Scraper — Start")
    log.info("Input: %s | Output: %s", args.input, args.output)
    log.info("═" * 60)

    entries = load_input(args.input)
    log.info("Total intrări de procesat: %d", len(entries))

    # Checkpoint recovery
    processed_indices, checkpoint_output = load_checkpoint()
    if args.resume and processed_indices:
        log.info("Reiau de la checkpoint: %d deja procesate", len(processed_indices))
        if checkpoint_output:
            args.output = checkpoint_output
    else:
        processed_indices = set()
        write_results([], args.output, mode="w")  # Scrie header-ul

    total_emails = 0
    stats = {"linkedin_person": 0, "linkedin_company": 0, "website": 0, "errors": 0}

    pbar = tqdm(total=len(entries), initial=len(processed_indices), desc="Procesare", unit="url")

    for idx, entry in enumerate(entries):
        if idx in processed_indices:
            continue

        try:
            if "limit" not in entry:
                entry["limit"] = args.company_limit

            results = process_entry(entry)

            if results:
                write_results(results, args.output)
                total_emails += len(results)

                url_type = classify_url(entry.get("url", ""))
                stats[url_type] = stats.get(url_type, 0) + len(results)

            processed_indices.add(idx)
            save_checkpoint(processed_indices, args.output)

        except KeyboardInterrupt:
            log.info("Întrerupt de utilizator. Checkpoint salvat.")
            save_checkpoint(processed_indices, args.output)
            pbar.close()
            sys.exit(0)
        except Exception as exc:
            log.error("Eroare la procesarea intrării #%d: %s", idx, exc)
            stats["errors"] += 1

        pbar.set_postfix(emails=total_emails, erori=stats["errors"])
        pbar.update(1)

    pbar.close()
    clear_checkpoint()

    log.info("═" * 60)
    log.info("FINALIZAT")
    log.info("Total emailuri extrase: %d", total_emails)
    log.info("  LinkedIn profil:   %d", stats["linkedin_person"])
    log.info("  LinkedIn companie: %d", stats["linkedin_company"])
    log.info("  Website/domeniu:   %d", stats["website"])
    log.info("  Erori:             %d", stats["errors"])
    log.info("Rezultate salvate în: %s", args.output)
    log.info("═" * 60)


if __name__ == "__main__":
    main()
